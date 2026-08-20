from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import os
from services.ingestion import clean_transaction_data
from sqlalchemy import create_engine
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

async def escalation_sweep():
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    
    def _sync_db_check():
        window_minutes = int(os.getenv("ESCALATION_WINDOW_MINUTES", "30"))
        escalations = []
        try:
            with psycopg.connect(db_url, autocommit=True) as conn:
                cp = PostgresSaver(conn)
                workflow = build_investigation_graph()
                app_graph = workflow.compile(checkpointer=cp)
                
                try:
                    states = list(cp.list(None))
                except Exception:
                    states = []
                
                seen_threads = set()
                for s in states:
                    thread_id = s.config["configurable"]["thread_id"]
                    if thread_id in seen_threads:
                        continue
                    seen_threads.add(thread_id)
                    
                    snapshot = app_graph.get_state({"configurable": {"thread_id": thread_id}})
                    if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
                        state_dict = snapshot.values
                        escalated_at = state_dict.get("escalated_at")
                        
                        if not escalated_at and snapshot.created_at:
                            now = datetime.now(timezone.utc)
                            # snapshot.created_at is a string like '2026-08-17T20:27:44.828566+00:00'
                            created_dt = datetime.fromisoformat(snapshot.created_at)
                            if not created_dt.tzinfo:
                                created_dt = created_dt.replace(tzinfo=timezone.utc)
                            
                            if (now - created_dt).total_seconds() > (window_minutes * 60):
                                print(f"SWEEP: Escalating stale thread {thread_id}")
                                app_graph.update_state(
                                    {"configurable": {"thread_id": thread_id}}, 
                                    {"escalated_at": now.isoformat()},
                                    as_node="human_review_gate"
                                )
                                escalations.append(thread_id)
        except Exception as e:
            print(f"Sweep DB error: {e}")
        return escalations

    while True:
        await asyncio.sleep(5)  # Wait for startup to complete
        try:
            escalations = await asyncio.to_thread(_sync_db_check)
            for thread_id in escalations:
                await manager.broadcast({"event": "escalation", "thread_id": thread_id})
        except Exception as e:
            print(f"Sweep error: {e}")
        await asyncio.sleep(55)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(escalation_sweep())

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

class WebhookPayload(BaseModel):
    thread_id: str
    confidence: float
    amount: float

@app.post("/webhooks/interrupt")
async def handle_interrupt_webhook(payload: WebhookPayload):
    print(f"STUB: Sent slack notification for thread {payload.thread_id} - Conf: {payload.confidence}, Amount: ${payload.amount}")
    await manager.broadcast({"event": "new_interrupt", "thread_id": payload.thread_id})
    return {"status": "ok"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "backend"}

def background_anomaly_sweep(transactions: list):
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        cp.setup()
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=cp)
        
        for txn in transactions:
            thread_id = f"sweep_{txn['id']}_{uuid.uuid4().hex[:4]}"
            config = {"configurable": {"thread_id": thread_id}}
            
            initial_state = {
                "transaction": {
                    "transaction_id": txn["id"],
                    "account_id": txn.get("account_id", "ACC-UNKNOWN"),
                    "amount": float(txn.get("amount", 0.0)) if pd.notna(txn.get("amount")) else 0.0,
                    "merchant_category": txn.get("merchant_category", "Unknown"),
                    "merchant_id": txn.get("merchant_id", "M-UNKNOWN"),
                    "timestamp": str(txn.get("timestamp", "2026-01-01T00:00:00")),
                    "device_id": txn.get("device_id", "DEV-UNKNOWN"),
                    "geo": txn.get("geo", "US-NY")
                }
            }
            
            try:
                list(app.stream(initial_state, config))
            except Exception as e:
                print(f"Background graph exception for {txn['id']}: {e}")

@app.post("/upload-transactions")
async def upload_transactions(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(('.csv', '.xlsx')):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported.")
    
    contents = await file.read()
    
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")
        
    try:
        # Clean with DuckDB
        cleaned_df = clean_transaction_data(df)
        
        # We need an 'id' column for the schema if it's not present
        if 'id' not in cleaned_df.columns:
            cleaned_df['id'] = [str(uuid.uuid4()) for _ in range(len(cleaned_df))]
            
        # Optional: ensure raw_source_row exists
        if 'raw_source_row' not in cleaned_df.columns:
            cleaned_df['raw_source_row'] = None
            
        # Bulk insert to DB
        db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
        engine = create_engine(db_url)
        
        cleaned_df.to_sql('transactions', engine, if_exists='append', index=False)
        
        # Trigger the asynchronous anomaly sweep via LangGraph
        transactions_dict = cleaned_df.to_dict('records')
        background_tasks.add_task(background_anomaly_sweep, transactions_dict)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during ingestion: {str(e)}")
        
    return {"message": "Successfully ingested transactions", "rows_inserted": len(cleaned_df)}

@app.get("/metrics/trust")
def get_trust_metrics():
    from sqlalchemy.orm import sessionmaker
    from models import ModelTrustScore
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        scores = db.query(ModelTrustScore).order_by(ModelTrustScore.timestamp.asc()).all()
        if not scores:
            return []
            
        return [
            {
                "timestamp": s.timestamp,
                "precision": s.precision,
                "recall": s.recall,
                "false_positive_rate": s.false_positive_rate,
                "sample_size": s.sample_size
            }
            for s in scores
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/reports/executive_summary")
def get_executive_summary(session_id: str):
    from agents.reporting import generate_executive_report
    from fastapi.responses import StreamingResponse
    import io
    
    try:
        zip_bytes = generate_executive_report(session_id)
        if not zip_bytes:
            raise HTTPException(status_code=404, detail="No data found for this session_id")
            
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=executive_report_{session_id}.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/redteam_latest")
def get_redteam_latest():
    import os
    import glob
    import json
    
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "reports", "redteam")
    if not os.path.exists(reports_dir):
        return {"status": "no_run"}
        
    files = glob.glob(os.path.join(reports_dir, "redteam_results_*.json"))
    if not files:
        return {"status": "no_run"}
        
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, "r") as f:
        data = json.load(f)
        
    return {"status": "success", "data": data}

@app.get("/cases/pending")
def get_pending_cases():
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=cp)
        
        try:
            states = list(cp.list(None))
        except Exception:
            states = []
            
        pending = []
        seen_threads = set()
        
        for s in states:
            thread_id = s.config["configurable"]["thread_id"]
            if thread_id in seen_threads:
                continue
            seen_threads.add(thread_id)
            
            try:
                # get_state WITHOUT checkpoint_id returns the LATEST StateSnapshot for the thread
                snapshot = app.get_state({"configurable": {"thread_id": thread_id}})
                # NOTE: task.interrupts is () in stored checkpoints — it's only populated during
                # live graph execution. The reliable signal is snapshot.next containing the
                # interrupt node name ('human_review_gate').
                is_paused = (
                    "human_review_gate" in (snapshot.next or [])
                    or (snapshot.tasks and any(t.interrupts for t in snapshot.tasks))
                )
                if is_paused:
                    state_dict = snapshot.values
                    txn = state_dict.get("transaction", {})
                    pending.append({
                        "thread_id": thread_id,
                        "account": txn.get("account_id", "Unknown"),
                        "amount": txn.get("amount", 0.0),
                        "calibrated_confidence": state_dict.get("calibrated_confidence", 0.0),
                        "risk_score": state_dict.get("risk_score", 0.0),
                        "summary": state_dict.get("investigation_notes", ""),
                        "recommended_action": state_dict.get("recommended_action", "APPROVE"),
                        "escalated_at": state_dict.get("escalated_at")
                    })
            except Exception:
                continue
                
        # Sort by confidence descending, then amount descending
        pending.sort(key=lambda x: (x["calibrated_confidence"], x["amount"]), reverse=True)
        return pending

@app.get("/cases/{thread_id}")
def get_case_details(thread_id: str):
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=cp)
        
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state_snapshot = app.get_state(config)
            if not state_snapshot or not state_snapshot.values:
                raise HTTPException(status_code=404, detail="Case not found")
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Case not found: {str(e)}")
            
        state_dict = state_snapshot.values
        txn = state_dict.get("transaction", {})
        cases = state_dict.get("retrieved_similar_cases", [])
        
        # Build React Flow Nodes and Edges artificially from similar cases
        nodes = [
            {"id": "root", "position": {"x": 250, "y": 50}, "data": {"label": f"Txn: {txn.get('transaction_id', 'Root')[:8]}", "isRoot": True}},
            {"id": "account", "position": {"x": 100, "y": 150}, "data": {"label": f"Acct: {txn.get('account_id', 'Unknown')}"}},
            {"id": "merchant", "position": {"x": 400, "y": 150}, "data": {"label": f"Merch: {txn.get('merchant_id', 'Unknown')}"}}
        ]
        edges = [
            {"id": "e_root_acct", "source": "root", "target": "account", "animated": True},
            {"id": "e_root_merch", "source": "root", "target": "merchant", "animated": True}
        ]
        
        for idx, case in enumerate(cases):
            node_id = f"case_{idx}"
            full_text = case.get('summary', 'Linked Case')
            nodes.append({
                "id": node_id,
                "position": {"x": 100 + (idx * 280), "y": 250 + (idx % 2 * 50)},
                "data": {"label": f"Past Txn: {full_text}", "fullText": full_text, "isFraud": case.get("is_fraud", False)}
            })
            target_link = "account" if idx % 2 == 0 else "merchant"
            edges.append({
                "id": f"e_{target_link}_{node_id}",
                "source": target_link,
                "target": node_id,
                "animated": False
            })
            
        return {
            "thread_id": thread_id,
            "transaction": txn,
            "calibrated_confidence": state_dict.get("calibrated_confidence", 0.0),
            "risk_score": state_dict.get("risk_score", 0.0),
            "summary": state_dict.get("investigation_notes", ""),
            "recommended_action": state_dict.get("recommended_action", "APPROVE"),
            "network": {"nodes": nodes, "edges": edges}
        }

from pydantic import BaseModel
class ResumeRequest(BaseModel):
    decision: str

@app.post("/cases/{thread_id}/resume")
def resume_case(thread_id: str, payload: ResumeRequest):
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.types import Command
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=cp)
        
        config = {"configurable": {"thread_id": thread_id}}
        try:
            for chunk in app.stream(Command(resume=payload.decision), config=config):
                pass
            return {"status": "success", "decision": payload.decision}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/cases/{thread_id}/history")
def get_case_history(thread_id: str):
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    with psycopg.connect(db_url, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        workflow = build_investigation_graph()
        app_graph = workflow.compile(checkpointer=cp)
        
        config = {"configurable": {"thread_id": thread_id}}
        try:
            history = list(app_graph.get_state_history(config))
            result = []
            for h in history:
                result.append({
                    "checkpoint_id": h.config["configurable"].get("checkpoint_id"),
                    "created_at": h.created_at,
                    "step": h.metadata.get("step"),
                    "source": h.metadata.get("source"),
                    "next": h.next,
                    "values": h.values
                })
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

class ForkRequest(BaseModel):
    checkpoint_id: str
    overrides: dict

@app.post("/cases/{thread_id}/fork")
async def fork_case(thread_id: str, payload: ForkRequest):
    import psycopg
    import uuid
    import asyncio
    from langgraph.checkpoint.postgres import PostgresSaver
    from agents.graph import build_investigation_graph
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    
    def _fork_sync():
        with psycopg.connect(db_url, autocommit=True) as conn:
            cp = PostgresSaver(conn)
            workflow = build_investigation_graph()
            app_graph = workflow.compile(checkpointer=cp)
            
            old_config = {"configurable": {"thread_id": thread_id, "checkpoint_id": payload.checkpoint_id}}
            old_state = app_graph.get_state(old_config)
            
            new_thread_id = str(uuid.uuid4())
            new_config = {"configurable": {"thread_id": new_thread_id}}
            
            new_values = old_state.values.copy()
            new_values.update(payload.overrides)
            
            # Determine which node produced this state to pretend it just finished
            as_node = old_state.metadata.get("source")
            if as_node in ("loop", "update"):
                writes = old_state.metadata.get("writes", {})
                if writes and isinstance(writes, dict):
                    as_node = list(writes.keys())[0]
                else:
                    # Deduce from next
                    next_nodes = old_state.next
                    if "human_review_gate" in next_nodes:
                        as_node = "calibrate"
                    elif "calibrate" in next_nodes:
                        as_node = "investigate"
                    elif "investigate" in next_nodes:
                        as_node = "retrieve_similar_cases"
                    elif "retrieve_similar_cases" in next_nodes:
                        as_node = "intake"
                    elif "finalize" in next_nodes:
                        as_node = "human_review_gate"
                    else:
                        as_node = None
                
            # If still None or missing, default to input
            if not as_node or as_node == "input":
                app_graph.update_state(new_config, new_values)
            else:
                app_graph.update_state(new_config, new_values, as_node=as_node)
            
            for chunk in app_graph.stream(None, new_config):
                pass
                
            return new_thread_id
            
    try:
        new_id = await asyncio.to_thread(_fork_sync)
        return {"status": "success", "new_thread_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# Credit Risk Triage (Decision Support System)
# ==========================================

from services.credit_triage import (
    ApplicantProfile,
    MacroIndicators,
    RiskFactorSummary,
    StressScenarioInput,
    StressScenarioOutput,
    MemoRequest,
    UnderwriterCreditMemo,
    evaluate_credit_risk,
    calculate_stress_scenario,
    generate_credit_memo,
    get_macro_benchmarks,
    get_preset_applicants
)

@app.get("/credit/macro-benchmarks")
def get_macro_indicators():
    """Returns current macroeconomic benchmarks and sector default rates."""
    return get_macro_benchmarks()

@app.get("/credit/presets")
def get_credit_presets():
    """Returns sample applicant profiles for underwriting demonstration."""
    return get_preset_applicants()

@app.post("/credit/triage", response_model=RiskFactorSummary)
def post_credit_triage(applicant: ApplicantProfile):
    """
    Evaluates applicant financial metrics, calculates DTI and revolving utilization,
    cross-references against macroeconomic benchmarks, surfaces risk factors,
    generates stress sensitivity scenarios, and extracts FCRA adverse action codes.
    
    GUARANTEE (Constitution Rule #6):
    The returned RiskFactorSummary contains NO autonomous approve/deny decisions.
    """
    try:
        summary = evaluate_credit_risk(applicant)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credit triage calculation failed: {str(e)}")

class CustomStressRequest(BaseModel):
    applicant: ApplicantProfile
    scenario: StressScenarioInput

@app.post("/credit/stress-test", response_model=StressScenarioOutput)
def post_custom_stress_test(payload: CustomStressRequest):
    """Calculates borrower DTI and liquidity resilience under custom macro shock parameters."""
    try:
        return calculate_stress_scenario(payload.applicant, payload.scenario)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stress scenario calculation failed: {str(e)}")

@app.post("/credit/export-memo", response_model=UnderwriterCreditMemo)
def post_export_memo(payload: MemoRequest):
    """
    Generates a structured institutional credit memorandum with verified ratios,
    macro stress matrix, FCRA factors, and human underwriter notes with SHA-256 audit reference.
    """
    try:
        summary = evaluate_credit_risk(payload.applicant)
        memo = generate_credit_memo(
            applicant=payload.applicant,
            summary=summary,
            underwriter_name=payload.underwriter_name,
            underwriter_notes=payload.underwriter_notes,
            checklist_verifications=payload.checklist_verifications
        )
        return memo
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Credit memo generation failed: {str(e)}")

from services.cost_service import (
    CostMetricsSummary,
    ScaleSimulationInput,
    ScaleSimulationOutput,
    get_cost_efficiency_metrics,
    simulate_scale_roi
)

@app.get("/metrics/cost-efficiency", response_model=CostMetricsSummary)
def get_cost_metrics():
    """
    Returns unit economics telemetry, $/1,000 transactions scored,
    fast-path deflection rate vs LLM escalation rate, and cumulative cost savings.
    """
    try:
        return get_cost_efficiency_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cost metrics calculation failed: {str(e)}")

@app.post("/metrics/cost-simulate", response_model=ScaleSimulationOutput)
def post_simulate_scale(payload: ScaleSimulationInput):
    """
    Calculates projected monthly and annual cloud/LLM spend savings
    under custom volume and deflection scaling parameters.
    """
    try:
        return simulate_scale_roi(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scale simulation failed: {str(e)}")


