import sys
import os
import uuid
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.graph import build_investigation_graph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
import psycopg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

def test_investigation_graph_interrupt_and_resume():
    workflow = build_investigation_graph()
    
    db_url = os.environ.get("DATABASE_URL")
    # For LangGraph 0.2 PostgresSaver, we must use psycopg 3 sync connection with autocommit
    with psycopg.connect(db_url, autocommit=True) as conn:
        checkpointer = PostgresSaver(conn)
        # Ensure checkpoint tables exist
        checkpointer.setup()
        
        app = workflow.compile(checkpointer=checkpointer)
        
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        txn = {
            "transaction_id": thread_id,
            "amount": 15000.0,
            "merchant_category": "crypto"
        }
        
        initial_state = {
            "transaction": txn,
            "fast_screen_result": "AMBIGUOUS",
            "retrieved_similar_cases": [],
            "investigation_notes": "",
            "risk_score": 0.0,
            "calibrated_confidence": 0.0,
            "recommended_action": "",
            "human_decision": None,
            "messages": []
        }
        
        # 1. Run the graph; it should pause at human_review_gate
        print("\n--- Starting graph execution ---")
        for chunk in app.stream(initial_state, config=config):
            pass
            
        state_snapshot = app.get_state(config)
        
        assert len(state_snapshot.tasks) > 0
        assert state_snapshot.tasks[0].interrupts
        print(f"Graph paused successfully. Interrupt payload: {state_snapshot.tasks[0].interrupts[0].value}")
        
        # 2. Simulate delay (in real life, the agent dies here and resumes hours later)
        import time
        time.sleep(1)
        
        # 3. Resume the graph with a human decision from the checkpoint!
        human_decision = "DENY"
        print(f"--- Resuming graph with decision: {human_decision} ---")
        
        final_output = None
        for chunk in app.stream(Command(resume=human_decision), config=config):
            if "finalize" in chunk:
                final_output = chunk["finalize"]
                
        # Verify the human decision made it to the final state
        assert final_output is not None
        assert final_output["human_decision"] == human_decision
        print("Graph resumed and completed successfully via PostgresSaver!")
