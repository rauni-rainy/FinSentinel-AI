import sys
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agents.audit import log_audit, verify_audit_chain, CryptographicTamperError, db_url
from models import AuditLog

def test_audit_chain_tamper_detection():
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    
    db = SessionLocal()
    # 1. Clear the table for a clean test
    db.execute(text("TRUNCATE TABLE audit_logs CASCADE"))
    db.commit()
    
    # 2. Insert 3 valid rows
    print("\nInserting 3 valid audit log entries...")
    log_audit("exec-1", "node-A", "test", {"msg": "row1"}, {"status": "ok"})
    log_audit("exec-1", "node-B", "test", {"msg": "row2"}, {"status": "ok"})
    log_audit("exec-1", "node-C", "test", {"msg": "row3"}, {"status": "ok"})
    
    # 3. Verify they are mathematically sound
    print("Verifying intact chain...")
    assert verify_audit_chain() is True
    
    # 4. Maliciously tamper with row 2 bypassing the SHA256 logic
    logs = db.query(AuditLog).order_by(AuditLog.seq_id.asc()).all()
    assert len(logs) == 3
    
    row2 = logs[1]
    print(f"Maliciously tampering with seq_id {row2.seq_id} directly in SQL...")
    # Update the raw JSON payload in the DB directly
    db.execute(
        text(f"UPDATE audit_logs SET payload = '{{\"msg\": \"TAMPERED\"}}' WHERE seq_id = {row2.seq_id}")
    )
    db.commit()
    db.close()
    
    # 5. Verify the chain catches the corruption
    print("Verifying tampered chain...")
    try:
        with pytest.raises(CryptographicTamperError) as exc:
            verify_audit_chain()
            
        print(f"Successfully caught tamper attempt: {exc.value}")
        assert "Data corruption detected" in str(exc.value)
    finally:
        # Clean up tampered rows so subsequent tests have a valid state
        db_cleanup = SessionLocal()
        db_cleanup.execute(text("TRUNCATE TABLE audit_logs CASCADE"))
        db_cleanup.commit()
        db_cleanup.close()

