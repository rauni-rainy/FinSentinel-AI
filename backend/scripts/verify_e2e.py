import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

from main import get_pending_cases, resume_case, ResumeRequest
import psycopg
from agents.audit import verify_audit_chain

def run_verification():
    print("1. Fetching pending cases from PostgresSaver...")
    pending = get_pending_cases()
    if not pending:
        print("[FAIL] No pending cases found. Run seed script first.")
        return
        
    print(f"[OK] Found {len(pending)} pending cases.")
    
    target_case = pending[0]
    thread_id = target_case["thread_id"]
    print(f"Targeting Thread ID: {thread_id} | Amount: ${target_case['amount']}")
    
    print("\n2. Simulating UI POST request to /cases/{thread_id}/resume with 'DENY'...")
    req = ResumeRequest(decision="DENY")
    res = resume_case(thread_id, req)
    
    print(f"[OK] Resume Response: {res}")
    
    print("\n3. Verifying the case dropped from pending queue...")
    pending_after = get_pending_cases()
    if any(p["thread_id"] == thread_id for p in pending_after):
        print("[FAIL] Case is STILL in pending queue!")
    else:
        print("[OK] Case successfully cleared from LangGraph checkpoints queue.")
        
    print("\n4. Verifying the final state landed in AuditLog...")
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    conn = psycopg.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        "SELECT action_type, result FROM audit_logs WHERE execution_id = %s AND action_type = 'investigation_completed'",
        (thread_id,)
    )
    row = cur.fetchone()
    if not row:
        print("[FAIL] No investigation_completed row found in audit_log for this thread!")
    else:
        print(f"[OK] Found finalized audit log! Result Payload:\n{row[1]}")
        assert row[1]["human_decision"] == "DENY", f"Expected human_decision DENY, got {row[1].get('human_decision')}"
        
    conn.close()
    
    print("\n5. Cryptographic verification of the AuditLog chain...")
    try:
        verify_audit_chain()
        print("[OK] AuditLog hashes are cryptographically intact!")
    except Exception as e:
        print(f"[FAIL] Cryptographic tamper exception: {e}")

if __name__ == "__main__":
    run_verification()
