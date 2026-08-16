from fastapi import FastAPI, UploadFile, File, HTTPException
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

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "backend"}

@app.post("/upload-transactions")
async def upload_transactions(file: UploadFile = File(...)):
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
        
        # We only insert columns that exist in the DB.
        # SQLAlchemy and pandas to_sql will handle this, but let's be safe.
        # In a real app we'd map columns explicitly.
        
        cleaned_df.to_sql('transactions', engine, if_exists='append', index=False)
        
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
                if snapshot.tasks and any(t.interrupts for t in snapshot.tasks):
                    state_dict = snapshot.values
                    txn = state_dict.get("transaction", {})
                    pending.append({
                        "thread_id": thread_id,
                        "account": txn.get("account_id", "Unknown"),
                        "amount": txn.get("amount", 0.0),
                        "calibrated_confidence": state_dict.get("calibrated_confidence", 0.0),
                        "risk_score": state_dict.get("risk_score", 0.0),
                        "summary": state_dict.get("investigation_notes", ""),
                        "recommended_action": state_dict.get("recommended_action", "APPROVE")
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
