import os
import sys
import uuid
import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.graph import build_investigation_graph
from models import ModelTrustScore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

validation_set = [
    {"txn": {"amount": 50.0, "merchant_category": "retail"}, "is_fraud": False, "fast_screen_result": "PASS"},
    {"txn": {"amount": 25000.0, "merchant_category": "crypto"}, "is_fraud": True, "fast_screen_result": "HIGH_CONFIDENCE_FLAG"},
    {"txn": {"amount": 105.0, "merchant_category": "retail"}, "is_fraud": False, "fast_screen_result": "AMBIGUOUS"},
    {"txn": {"amount": 15000.0, "merchant_category": "crypto"}, "is_fraud": True, "fast_screen_result": "AMBIGUOUS"},
]

def run_eval():
    print("Starting Scheduled Eval Job against validation set...")
    
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    from langgraph.checkpoint.memory import MemorySaver
    
    for item in validation_set:
        txn = item["txn"]
        txn["transaction_id"] = str(uuid.uuid4())
        
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": txn["transaction_id"]}}
        
        initial_state = {
            "transaction": txn,
            "fast_screen_result": item["fast_screen_result"],
            "retrieved_similar_cases": [],
            "investigation_notes": "",
            "risk_score": 0.0,
            "calibrated_confidence": 0.0,
            "recommended_action": "",
            "human_decision": None,
            "messages": []
        }
        
        for _ in app.stream(initial_state, config=config):
            pass
            
        state = app.get_state(config).values
        action = state.get("recommended_action", "")
        if not action:
            action = "APPROVE"
            
        model_pred_fraud = (action == "DENY")
        actual_fraud = item["is_fraud"]
        
        if model_pred_fraud and actual_fraud:
            true_positives += 1
        elif model_pred_fraud and not actual_fraud:
            false_positives += 1
        elif not model_pred_fraud and not actual_fraud:
            true_negatives += 1
        elif not model_pred_fraud and actual_fraud:
            false_negatives += 1

    total = len(validation_set)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 1.0
    fpr = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0.0
    
    print(f"Eval complete! Precision: {precision:.2f}, Recall: {recall:.2f}, FPR: {fpr:.2f}")
    
    db = SessionLocal()
    score = ModelTrustScore(
        id=str(uuid.uuid4()),
        timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        precision=precision,
        recall=recall,
        false_positive_rate=fpr,
        sample_size=total
    )
    db.add(score)
    db.commit()
    db.close()
    print("Logged to model_trust_scores.")

if __name__ == "__main__":
    run_eval()
