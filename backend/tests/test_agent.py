import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.graph import build_investigation_graph
from langgraph.checkpoint.memory import MemorySaver
import uuid

def test_safe_transaction_bypasses_llm():
    # Transaction well below LLM and HITL threshold (fast-screen PASS)
    txn = {
        "transaction_id": str(uuid.uuid4()),
        "amount": 25.0,
        "merchant_category": "groceries"
    }
    
    workflow = build_investigation_graph()
    app = workflow.compile()
    
    initial_state = {
        "transaction": txn,
        "fast_screen_result": "PASS",
        "retrieved_similar_cases": [],
        "investigation_notes": "",
        "risk_score": 0.0,
        "calibrated_confidence": 0.0,
        "recommended_action": "",
        "human_decision": None,
        "messages": []
    }
    
    final_state = app.invoke(initial_state)
    assert final_state.get("fast_screen_result") == "PASS"
    assert final_state.get("human_decision") is None or final_state.get("human_decision") == "AUTO_RESOLVED"

