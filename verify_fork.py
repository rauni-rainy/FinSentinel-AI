import urllib.request
import json
import time
import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

DB_URL = "postgresql://user:password@localhost:5432/finsentinel"

def fetch_json(url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8') if data else None,
        headers={'Content-Type': 'application/json'} if data else {}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code}")
        print(f"Response: {e.read().decode()}")
        raise

import sys
sys.path.append('backend')
from agents.graph import build_investigation_graph

print("Connecting to DB to find a completed thread...")
with psycopg.connect(DB_URL, autocommit=True) as conn:
    cp = PostgresSaver(conn)
    app = build_investigation_graph().compile(checkpointer=cp)
    states = list(cp.list(None))
    
    # Group by thread
    threads = {}
    for s in states:
        tid = s.config['configurable']['thread_id']
        threads.setdefault(tid, []).append(s)
        
    completed_thread = None
    original_final_state = None
    
    for tid, thread_states in threads.items():
        # A completed thread has a state with no next tasks and 'human_decision' in values
        snapshot = app.get_state({"configurable": {"thread_id": tid}})
        if snapshot.values.get("human_decision"):
            completed_thread = tid
            original_final_state = snapshot.values
            break

if not completed_thread:
    print("Could not find a completed thread.")
    exit(1)

print(f"Found completed thread: {completed_thread}")
print(f"Original confidence: {original_final_state.get('calibrated_confidence')}")
print(f"Original decision: {original_final_state.get('human_decision')}")

print("\nFetching history...")
history = fetch_json(f"http://localhost:8000/cases/{completed_thread}/history")
print(f"History length: {len(history)}")

# Find checkpoint right before human_review_gate
target_ckpt = None
for h in history:
    if "human_review_gate" in h.get("next", []):
        target_ckpt = h
        break

if not target_ckpt:
    # Fallback to the first available node
    target_ckpt = history[-1]

print(f"Selected checkpoint where next is: {target_ckpt.get('next')}")

print("\nForking with new confidence: 0.99 (forced escalation)")
fork_res = fetch_json(
    f"http://localhost:8000/cases/{completed_thread}/fork",
    data={
        "checkpoint_id": target_ckpt["checkpoint_id"],
        "overrides": {"calibrated_confidence": 0.6}
    }
)

new_thread_id = fork_res["new_thread_id"]
print(f"Fork successful. New thread ID: {new_thread_id}")

print("Waiting for new thread to process...")
time.sleep(5)

new_history = fetch_json(f"http://localhost:8000/cases/{new_thread_id}/history")
latest_new_ckpt = new_history[0] if new_history else None

if latest_new_ckpt:
    print(f"\nNew thread confidence: {latest_new_ckpt['values'].get('calibrated_confidence')}")
    print(f"New thread decision: {latest_new_ckpt['values'].get('human_decision')}")
    print("Is different thread ID?", new_thread_id != completed_thread)
    
    # Check original thread again to ensure it wasn't mutated
    with psycopg.connect(DB_URL, autocommit=True) as conn2:
        cp2 = PostgresSaver(conn2)
        app2 = build_investigation_graph().compile(checkpointer=cp2)
        current_orig = app2.get_state({"configurable": {"thread_id": completed_thread}})
        print("\nOriginal thread confidence still:", current_orig.values.get("calibrated_confidence"))
        print("Original thread mutated?", current_orig.values.get("calibrated_confidence") == 0.99)
else:
    print("New thread has no history yet.")

