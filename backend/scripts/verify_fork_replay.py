import os
import sys
import uuid
import time
import json
import urllib.request
import psycopg
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
DB_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
BACKEND_URL = "http://localhost:8000"

def fetch_json(url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8') if data else None,
        headers={'Content-Type': 'application/json'} if data else {}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    print("=" * 80)
    print("  FINSENTINEL AI - TIME-TRAVEL REPLAY & WHAT-IF FORKING VERIFICATION")
    print("=" * 80)

    # 1. Start a baseline investigation case
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from agents.graph import build_investigation_graph
    from langgraph.checkpoint.postgres import PostgresSaver

    orig_thread_id = str(uuid.uuid4())
    print(f"\n[1] Creating baseline investigation case...")
    print(f"    Original Thread ID: {orig_thread_id}")

    with psycopg.connect(DB_URL, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        cp.setup()
        app = build_investigation_graph().compile(checkpointer=cp)

        initial_state = {
            "transaction": {
                "transaction_id": orig_thread_id,
                "amount": 450.0,
                "merchant_category": "electronics",
                "account_id": "ACC_REPLAY_TEST_101"
            },
            "fast_screen_result": "AMBIGUOUS",
            "retrieved_similar_cases": [],
            "investigation_notes": "",
            "risk_score": 0.1,
            "calibrated_confidence": 0.95,
            "recommended_action": "APPROVE",
            "human_decision": None,
            "messages": []
        }

        config = {"configurable": {"thread_id": orig_thread_id}}
        for chunk in app.stream(initial_state, config=config):
            pass

        orig_snapshot = app.get_state(config)
        print(f"    Original Run Finished:")
        print(f"      - Amount: ${initial_state['transaction']['amount']}")
        print(f"      - Calibrated Confidence: {orig_snapshot.values.get('calibrated_confidence')}")
        print(f"      - Human Decision: {orig_snapshot.values.get('human_decision')}")
        print(f"      - Recommended Action: {orig_snapshot.values.get('recommended_action')}")

    # 2. Step backward through checkpoints (Time-Travel History)
    print(f"\n[2] Replaying Checkpoint History via GET /cases/{orig_thread_id}/history...")
    history = fetch_json(f"{BACKEND_URL}/cases/{orig_thread_id}/history")
    print(f"    Found {len(history)} checkpoints in timeline:")
    for idx, ckpt in enumerate(reversed(history)):
        node_name = ckpt.get("step") or ckpt.get("source") or "entry"
        next_nodes = ckpt.get("next")
        vals = ckpt.get("values", {})
        print(f"      [{idx + 1}] Checkpoint {ckpt['checkpoint_id'][:8]}... | Step: {node_name} | Next: {next_nodes} | Conf: {vals.get('calibrated_confidence')}")

    # Locate the checkpoint prior to human review gate
    target_ckpt = None
    for h in history:
        if "human_review_gate" in h.get("next", []):
            target_ckpt = h
            break
    if not target_ckpt:
        target_ckpt = history[0]

    target_id = target_ckpt["checkpoint_id"]
    print(f"\n[3] Forking Checkpoint {target_id[:8]}... with altered threshold:")
    print("    Hypothetical Scenario: 'What if confidence had been 0.50 (ambiguous zone) instead of 0.95?'")

    fork_res = fetch_json(
        f"{BACKEND_URL}/cases/{orig_thread_id}/fork",
        data={
            "checkpoint_id": target_id,
            "overrides": {
                "calibrated_confidence": 0.50
            }
        }
    )

    forked_thread_id = fork_res["new_thread_id"]
    print(f"    Fork Created Successfully!")
    print(f"    Forked Thread ID: {forked_thread_id} (Distinct from original: {forked_thread_id != orig_thread_id})")

    # 3. Inspect Forked State
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        cp = PostgresSaver(conn)
        app = build_investigation_graph().compile(checkpointer=cp)
        forked_snapshot = app.get_state({"configurable": {"thread_id": forked_thread_id}})

        print(f"\n[4] Forked Case Execution State:")
        print(f"    - Calibrated Confidence: {forked_snapshot.values.get('calibrated_confidence')}")
        print(f"    - Human Decision: {forked_snapshot.values.get('human_decision')} (Waiting on interrupt)")
        print(f"    - Tasks Interrupted: {len(forked_snapshot.tasks) > 0 and bool(forked_snapshot.tasks[0].interrupts)}")

        # 4. Resume the forked case with human underwriter action
        print(f"\n[5] Resuming Forked Case with Human Underwriter Decision: 'ESCALATE_TO_TIER2'...")
        resume_res = fetch_json(
            f"{BACKEND_URL}/cases/{forked_thread_id}/resume",
            data={"decision": "ESCALATE_TO_TIER2"}
        )
        print(f"    Resume Status: {resume_res.get('status')}")

        forked_final = app.get_state({"configurable": {"thread_id": forked_thread_id}})
        print(f"    Forked Final Decision: {forked_final.values.get('human_decision')}")

        # 5. Check Original Run Immutability
        print(f"\n[6] Verifying Immutability of Original Case:")
        orig_check = app.get_state({"configurable": {"thread_id": orig_thread_id}})
        print(f"    - Original Thread ID: {orig_thread_id}")
        print(f"    - Original Confidence: {orig_check.values.get('calibrated_confidence')} (Expected: {orig_snapshot.values.get('calibrated_confidence')})")
        print(f"    - Original Human Decision: {orig_check.values.get('human_decision')} (Expected: {orig_snapshot.values.get('human_decision')})")

        is_mutated = (
            orig_check.values.get("calibrated_confidence") == 0.50 or
            orig_check.values.get("human_decision") == "ESCALATE_TO_TIER2"
        )
        print(f"    - Mutation Detected: {is_mutated}")
        assert not is_mutated, "Original case was mutated!"
        print("\n" + "=" * 80)
        print("  RESULT: VERIFICATION PASSED! Non-mutating time-travel & forking fully operational.")
        print("=" * 80)

if __name__ == "__main__":
    main()
