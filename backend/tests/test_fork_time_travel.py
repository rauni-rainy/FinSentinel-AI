import sys
import os
import uuid
import pytest
import psycopg
from dotenv import load_dotenv
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from agents.graph import build_investigation_graph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
DB_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")

@pytest.fixture
def client():
    return TestClient(app)

def test_checkpoint_history_and_fork_without_mutation(client):
    """
    Verifies that:
    1. An investigation graph creates a checkpoint history in PostgresSaver.
    2. A reviewer can step backward through past checkpoints via GET /cases/{thread_id}/history.
    3. A reviewer can fork the case with an altered threshold via POST /cases/{thread_id}/fork.
    4. The forked execution produces a different, traceable outcome.
    5. The original case state and checkpoints remain completely unmutated.
    """
    workflow = build_investigation_graph()
    
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        graph_app = workflow.compile(checkpointer=checkpointer)
        
        orig_thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": orig_thread_id}}
        
        # Initial transaction that will auto-resolve (e.g., small amount, low ambiguity)
        initial_state = {
            "transaction": {
                "transaction_id": orig_thread_id,
                "amount": 250.0,
                "merchant_category": "groceries",
                "account_id": "ACC_TEST_FORK_001"
            },
            "fast_screen_result": "AMBIGUOUS",
            "retrieved_similar_cases": [],
            "investigation_notes": "",
            "risk_score": 0.1,
            "calibrated_confidence": 0.95,  # > 0.8 => Auto resolves
            "recommended_action": "APPROVE",
            "human_decision": None,
            "messages": []
        }
        
        # 1. Run original graph to completion
        for chunk in graph_app.stream(initial_state, config=config):
            pass
            
        orig_final_snapshot = graph_app.get_state(config)
        assert orig_final_snapshot.values.get("human_decision") == "AUTO_RESOLVED"
        orig_conf = orig_final_snapshot.values.get("calibrated_confidence")
        
        # 2. Query History via API
        resp_history = client.get(f"/cases/{orig_thread_id}/history")
        assert resp_history.status_code == 200
        history = resp_history.json()
        assert len(history) >= 3
        
        # Checkpoint stepping verification
        checkpoint_steps = [h.get("step") or h.get("source") for h in history]
        print(f"\nOriginal case checkpoints: {checkpoint_steps}")
        
        # Find the checkpoint before human_review_gate (or calibrate node)
        target_ckpt = None
        for h in history:
            if "human_review_gate" in h.get("next", []):
                target_ckpt = h
                break
        if not target_ckpt:
            target_ckpt = history[-1]
            
        assert target_ckpt is not None
        target_ckpt_id = target_ckpt["checkpoint_id"]
        
        # 3. Fork with modified threshold: change calibrated_confidence to 0.55 (forcing human review gate interrupt)
        fork_payload = {
            "checkpoint_id": target_ckpt_id,
            "overrides": {
                "calibrated_confidence": 0.55  # 0.3 <= conf <= 0.8 triggers interrupt
            }
        }
        
        fork_resp = client.post(f"/cases/{orig_thread_id}/fork", json=fork_payload)
        assert fork_resp.status_code == 200
        fork_data = fork_resp.json()
        assert "new_thread_id" in fork_data
        new_thread_id = fork_data["new_thread_id"]
        assert new_thread_id != orig_thread_id
        
        # 4. Verify Forked State & Outcome
        new_snapshot = graph_app.get_state({"configurable": {"thread_id": new_thread_id}})
        assert new_snapshot.values.get("calibrated_confidence") == 0.55
        # It must be interrupted (waiting for human review), human_decision is None
        assert new_snapshot.values.get("human_decision") is None
        assert len(new_snapshot.tasks) > 0
        assert new_snapshot.tasks[0].interrupts
        
        # 5. Verify Original State is Completely Unmutated
        orig_current_snapshot = graph_app.get_state(config)
        assert orig_current_snapshot.values.get("calibrated_confidence") == orig_conf
        assert orig_current_snapshot.values.get("human_decision") == "AUTO_RESOLVED"
        
        # 6. Resume the forked thread with a human decision to ensure complete traceability
        resume_resp = client.post(f"/cases/{new_thread_id}/resume", json={"decision": "DENIED_ON_FORK"})
        assert resume_resp.status_code == 200
        
        forked_final_snapshot = graph_app.get_state({"configurable": {"thread_id": new_thread_id}})
        assert forked_final_snapshot.values.get("human_decision") == "DENIED_ON_FORK"
        assert forked_final_snapshot.values.get("calibrated_confidence") == 0.55
        
        # Original thread is STILL unmutated
        orig_after_resume = graph_app.get_state(config)
        assert orig_after_resume.values.get("human_decision") == "AUTO_RESOLVED"
        assert orig_after_resume.values.get("calibrated_confidence") == orig_conf
