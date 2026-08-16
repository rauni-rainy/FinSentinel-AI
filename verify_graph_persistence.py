import os
import sys
import uuid

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.agents.graph import build_investigation_graph
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
import psycopg
from dotenv import load_dotenv

load_dotenv('.env')
db_url = os.environ.get("DATABASE_URL")

def start_graph():
    thread_id = str(uuid.uuid4())
    print(f"=== Process 1: Starting NEW graph execution ===")
    print(f"Thread ID: {thread_id}")
    
    with psycopg.connect(db_url, autocommit=True) as conn:
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": thread_id}}
        txn = {
            "transaction_id": thread_id,
            "amount": 25000.0,  # Known anomaly
            "merchant_category": "crypto"
        }
        
        initial_state = {
            "transaction": txn,
            "fast_screen_result": "HIGH_CONFIDENCE_FLAG",
            "retrieved_similar_cases": [],
            "investigation_notes": "",
            "risk_score": 0.0,
            "calibrated_confidence": 0.0,
            "recommended_action": "",
            "human_decision": None,
            "messages": []
        }
        
        print("Invoking graph...")
        for chunk in app.stream(initial_state, config=config):
            print(f"  -> Node executed: {list(chunk.keys())[0]}")
            
        state = app.get_state(config)
        if state.tasks and state.tasks[0].interrupts:
            print(f"\n[OK] Graph safely interrupted! Payload: {state.tasks[0].interrupts[0].value}")
            with open("persistence_thread.txt", "w") as f:
                f.write(thread_id)
            print("[OK] Thread ID written to persistence_thread.txt.")
            print("Process 1 will now exit. The state is strictly in the database.")
        else:
            print("Error: Graph did not interrupt!")
            sys.exit(1)

def resume_graph():
    try:
        with open("persistence_thread.txt", "r") as f:
            thread_id = f.read().strip()
    except FileNotFoundError:
        print("Run 'start' first.")
        sys.exit(1)
        
    print(f"=== Process 2: Re-hydrating graph ===")
    print(f"Thread ID: {thread_id}")
    
    with psycopg.connect(db_url, autocommit=True) as conn:
        checkpointer = PostgresSaver(conn)
        workflow = build_investigation_graph()
        app = workflow.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": thread_id}}
        
        state = app.get_state(config)
        if not state.tasks or not state.tasks[0].interrupts:
            print("Error: Could not find suspended state in database!")
            sys.exit(1)
            
        print("[OK] Successfully read suspended state from DB.")
        print("Resuming with Command(resume='DENY')...")
        
        final_output = None
        for chunk in app.stream(Command(resume="DENY"), config=config):
            print(f"  -> Node executed: {list(chunk.keys())[0]}")
            if "finalize" in chunk:
                final_output = chunk["finalize"]
                
        if final_output and final_output.get("human_decision") == "DENY":
            print("\n[SUCCESS] Persistence proven! Graph resumed from DB and completed!")
        else:
            print("\n[FAILED] Finalize did not output correctly.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "resume":
        resume_graph()
    else:
        start_graph()
