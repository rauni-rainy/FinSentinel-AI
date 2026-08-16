import uuid
import datetime
import os
import json
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import AuditLog
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def compute_hash(execution_id, session_id, record_type, node_name, action_type, payload, result, latency_ms, cost, prompt, response, prev_hash):
    # Standardize JSON strings for reliable hashing
    payload_str = json.dumps(payload, sort_keys=True) if payload else "{}"
    result_str = json.dumps(result, sort_keys=True) if result else "{}"
    
    raw_str = (
        f"{execution_id}|{session_id}|{record_type}|{node_name}|{action_type}|{payload_str}|{result_str}|"
        f"{latency_ms}|{cost}|{prompt}|{response}|{prev_hash}"
    )
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

def log_audit(
    execution_id: str, 
    node_name: str, 
    action_type: str, 
    payload: dict, 
    result: dict,
    latency_ms: float = None,
    cost: float = None,
    prompt: str = None,
    response: str = None,
    session_id: str = None,
    record_type: str = "investigation"
):
    db = SessionLocal()
    try:
        # Get the absolute latest row to lock in the chain
        # Using with_for_update() would strictly prevent race conditions, but for this demo a simple order_by is sufficient.
        last_log = db.query(AuditLog).order_by(AuditLog.seq_id.desc()).first()
        prev_hash = last_log.current_hash if last_log else "GENESIS"
        
        current_hash = compute_hash(
            execution_id, session_id, record_type, node_name, action_type, payload, result, 
            latency_ms, cost, prompt, response, prev_hash
        )
        
        log = AuditLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
            execution_id=execution_id,
            session_id=session_id,
            record_type=record_type,
            node_name=node_name,
            action_type=action_type,
            payload=payload,
            result=result,
            latency_ms=latency_ms,
            cost=cost,
            prompt=prompt,
            response=response,
            prev_row_hash=prev_hash,
            current_hash=current_hash
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Failed to log audit: {e}")
    finally:
        db.close()

class CryptographicTamperError(Exception):
    pass

def verify_audit_chain():
    db = SessionLocal()
    try:
        logs = db.query(AuditLog).order_by(AuditLog.seq_id.asc()).all()
        
        expected_prev_hash = "GENESIS"
        
        for i, log in enumerate(logs):
            # 1. Check prev link
            if log.prev_row_hash != expected_prev_hash:
                raise CryptographicTamperError(
                    f"Chain broken at seq_id {log.seq_id}. "
                    f"Expected prev_hash: {expected_prev_hash}, but found: {log.prev_row_hash}"
                )
            
            # 2. Recalculate current hash based on payload
            recalculated_hash = compute_hash(
                log.execution_id, log.session_id, log.record_type, log.node_name, log.action_type, log.payload, log.result,
                log.latency_ms, log.cost, log.prompt, log.response, log.prev_row_hash
            )
            
            # 3. Check current hash
            if recalculated_hash != log.current_hash:
                raise CryptographicTamperError(
                    f"Data corruption detected at seq_id {log.seq_id}. "
                    f"Stored hash: {log.current_hash}, Recalculated: {recalculated_hash}"
                )
                
            expected_prev_hash = log.current_hash
            
        print("Audit chain verified successfully! No tampering detected.")
        return True
    finally:
        db.close()
