import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.graph import run_investigation
from agents.audit import log_audit
import uuid

def test_safe_transaction_bypasses_llm():
    # Transaction well below LLM and HITL threshold
    txn = {
        "transaction_id": str(uuid.uuid4()),
        "amount": 500.0,
        "merchant_category": "retail"
    }
    
    # We run without checkpointer in tests just to verify the state transitions
    final_state = run_investigation(txn)
    
    # LLM should not have been called
    assert final_state.get("llm_reasoning") is None
    assert final_state.get("is_fraud") is None

def test_risky_transaction_hits_llm_and_interrupt():
    # High amount triggers velocity flag and requires LLM, then interrupt
    txn = {
        "transaction_id": str(uuid.uuid4()),
        "amount": 15000.0,
        "merchant_category": "crypto"
    }
    
    # To test interrupt, we need MemorySaver checkpointer
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    
    final_state = run_investigation(txn, checkpointer=checkpointer)
    
    # It should pause at hitl_interrupt
    # Actually `invoke` will return the state at the interrupt
    # We can inspect the state to verify LLM ran
    assert final_state.get("llm_reasoning") is not None
    assert final_state.get("is_fraud") is not None
    
    # LangGraph returns the state when interrupted
    # Next node to run would be 'hitl_interrupt' if resumed
