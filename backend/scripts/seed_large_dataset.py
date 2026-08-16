import os
import sys
import uuid
import random
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.graph import build_investigation_graph
from models import AuditLog, ModelTrustScore, Transaction
from agents.audit import log_audit
from agents.reporting import generate_executive_report
from dotenv import load_dotenv
import zipfile
import io

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)

def run():
    session_id = "paysim-scale-demo"
    db = SessionLocal()
    
    from models import HistoricalCase
    from langchain_ollama import OllamaEmbeddings

    # 1. Clean previous run
    db.query(AuditLog).filter(AuditLog.session_id == session_id).delete()
    db.query(ModelTrustScore).filter(ModelTrustScore.sample_size == 12345).delete() # marker
    db.query(HistoricalCase).delete()
    db.commit()
    
    # Generate historical cases with nomic-embed-text via Ollama
    print("Generating pgvector embeddings for historical cases...")
    embedder = OllamaEmbeddings(model="nomic-embed-text")
    case_templates = [
        {"summary": "Account Takeover (ATO): high velocity transfers to external merchants following IP location change.", "is_fraud": True},
        {"summary": "Structuring: multiple rapid transactions just below reporting thresholds to retail categories.", "is_fraud": True},
        {"summary": "Velocity Spike: rapid consecutive purchases at electronics retailers.", "is_fraud": True},
        {"summary": "Normal variance: slightly elevated hardware spend within historical departmental limits.", "is_fraud": False},
        {"summary": "Normal variance: recurring vendor payment clearing at month end.", "is_fraud": False}
    ]
    
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=1)
        ollama_running = True
    except Exception:
        ollama_running = False
        print("Warning: Ollama not running locally. Using fallback deterministic vectors.")
    
    for idx, c in enumerate(case_templates):
        if ollama_running:
            try:
                emb = embedder.embed_query(c["summary"])
            except Exception:
                emb = [0.0] * 768
                emb[idx] = 1.0
        else:
            emb = [0.0] * 768
            emb[idx] = 1.0
            
        hc = HistoricalCase(
            id=str(uuid.uuid4()),
            transaction_id=f"hist_{idx}",
            summary=c["summary"],
            is_fraud=c["is_fraud"],
            embedding=emb
        )
        db.add(hc)
    db.commit()
    
    # 2. Fetch ~150 real PaySim transactions. 
    # Get 120 normal and 30 high-value to ensure flags.
    txns = db.query(Transaction).filter(Transaction.amount < 1000).limit(120).all()
    txns += db.query(Transaction).filter(Transaction.amount >= 5000).limit(30).all()
    random.shuffle(txns)
    
    print(f"Processing {len(txns)} transactions through the core LangGraph...")
    
    workflow = build_investigation_graph()
    
    import psycopg
    from langgraph.checkpoint.postgres import PostgresSaver
    
    with psycopg.connect(db_url, autocommit=True) as conn:
        # Initialize pgvector extension if not exists
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        cp = PostgresSaver(conn)
        cp.setup()
        app = workflow.compile(checkpointer=cp)
        
        for t in txns:
            # Reformat row to dict
            txn_dict = {
                "transaction_id": t.id,
                "account_id": t.account_id,
                "amount": float(t.amount),
                "merchant_category": t.merchant_category,
                "merchant_id": t.merchant_id,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None
            }
            
            initial_state = {
                "transaction": txn_dict,
                "fast_screen_result": "PASS" if txn_dict["amount"] < 1000 else "AMBIGUOUS",
                "retrieved_similar_cases": [],
                "investigation_notes": "",
                "risk_score": 0.0,
                "calibrated_confidence": 0.0,
                "recommended_action": "",
                "human_decision": None,
                "session_id": session_id,
                "messages": []
            }
            
            config = {"configurable": {"thread_id": t.id}}
            try:
                app.invoke(initial_state, config=config)
            except Exception as e:
                if "interrupt" not in str(e).lower():
                    pass # ignore normal langgraph interrupt exceptions since we aren't resuming

    # 3. Add variance queries
    log_audit(
        execution_id=str(uuid.uuid4())[:8],
        node_name="sql_agent",
        action_type="variance_analysis",
        payload={"sql_history": []},
        result={"final_answer": "Hardware costs spiked by 14% due to a massive renewal with VendorA."},
        prompt="Why did Hardware expenses spike in Q2?",
        response="Hardware costs spiked by 14% due to a massive renewal with VendorA.",
        session_id=session_id,
        record_type="variance_query"
    )
    
    log_audit(
        execution_id=str(uuid.uuid4())[:8],
        node_name="sql_agent",
        action_type="variance_analysis",
        payload={"sql_history": []},
        result={"final_answer": "Suspicious clustering of small-value transactions observed in North Region."},
        prompt="Are there any geographic anomalies this month?",
        response="Suspicious clustering of small-value transactions observed in North Region.",
        session_id=session_id,
        record_type="variance_query"
    )

    # 4. Spread timestamps over 30 days
    logs = db.query(AuditLog).filter(AuditLog.session_id == session_id).all()
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    for log in logs:
        days_back = random.randint(0, 30)
        hours_back = random.randint(0, 23)
        log.timestamp = now - datetime.timedelta(days=days_back, hours=hours_back)
    
    db.commit()
    
    # 5. Generate Trust Scores over 6 weeks
    for i in range(6, 0, -1):
        ts_time = now - datetime.timedelta(days=i*5)
        score = ModelTrustScore(
            id=str(uuid.uuid4()),
            timestamp=ts_time,
            precision=0.85 + (random.random() * 0.1), # 0.85 - 0.95
            recall=0.88 + (random.random() * 0.1),
            false_positive_rate=0.08 - (random.random() * 0.05), # 0.03 - 0.08
            sample_size=12345
        )
        db.add(score)
    db.commit()
    db.close()
    
    print("Generating Executive Report V3...")
    zip_bytes = generate_executive_report(session_id)
    
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "demo_reports_v4")
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(out_dir)
        
    print(f"Success! Scaled reports extracted to {out_dir}")

if __name__ == "__main__":
    run()
