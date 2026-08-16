import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from backend.agents.graph import build_investigation_graph

workflow = build_investigation_graph()
app = workflow.compile()

initial_state = {
    "transaction": {"amount": 6000},
    "fast_screen_result": "AMBIGUOUS",
    "retrieved_similar_cases": [],
    "investigation_notes": "",
    "risk_score": 0.0,
    "calibrated_confidence": 0.0,
    "recommended_action": "",
    "human_decision": None,
    "session_id": "test",
    "messages": []
}

try:
    print(app.invoke(initial_state))
except Exception as e:
    print(f"Error: {e}")
