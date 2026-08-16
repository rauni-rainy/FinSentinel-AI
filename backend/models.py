from sqlalchemy import Column, String, DateTime, Numeric, JSON, Boolean, Float, Integer, Identity
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Account(Base):
    __tablename__ = 'accounts'

    id = Column(String, primary_key=True)
    opened_at = Column(DateTime)
    risk_tier = Column(String)

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(String, primary_key=True)
    account_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    amount = Column(Numeric)
    merchant_category = Column(String)
    merchant_id = Column(String)
    device_id = Column(String)
    geo = Column(String)
    raw_source_row = Column(JSON)

class AuditLog(Base):
    __tablename__ = 'audit_logs'

    seq_id = Column(Integer, Identity(always=False), primary_key=True, index=True)
    id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    execution_id = Column(String, index=True)
    session_id = Column(String, index=True)
    record_type = Column(String, default="investigation", index=True)
    node_name = Column(String)
    action_type = Column(String)
    payload = Column(JSON)
    result = Column(JSON)
    latency_ms = Column(Float, nullable=True)
    cost = Column(Numeric, nullable=True)
    prompt = Column(String, nullable=True)
    response = Column(String, nullable=True)
    prev_row_hash = Column(String, nullable=True)
    current_hash = Column(String, nullable=True)

class HistoricalCase(Base):
    __tablename__ = 'historical_cases'

    id = Column(String, primary_key=True)
    transaction_id = Column(String, index=True)
    summary = Column(String)
    is_fraud = Column(Boolean)
    embedding = Column(Vector(768))

class ModelTrustScore(Base):
    __tablename__ = 'model_trust_scores'
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, index=True)
    precision = Column(Float)
    recall = Column(Float)
    false_positive_rate = Column(Float)
    sample_size = Column(Integer)

class OperatingExpense(Base):
    __tablename__ = 'operating_expenses'

    id = Column(String, primary_key=True)
    department = Column(String, index=True)
    category = Column(String, index=True)
    vendor = Column(String)
    amount = Column(Numeric)
    date = Column(DateTime, index=True)

class Budget(Base):
    __tablename__ = 'budgets'

    id = Column(String, primary_key=True)
    department = Column(String, index=True)
    category = Column(String, index=True)
    quarter = Column(String) # e.g., 'Q1 2026'
    allocated_amount = Column(Numeric)

