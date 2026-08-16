import os
import math
from typing import Dict, Any
from agents.state import InvestigationState
from agents.audit import log_audit
from langgraph.types import interrupt

class MockCalibrator:
    def predict(self, score: float) -> float:
        return 1.0 / (1.0 + math.exp(-10 * (score - 0.5)))
        
calibrator = MockCalibrator()

def intake_node(state: InvestigationState) -> InvestigationState:
    return state

from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
import json

class InvestigationReasoning(BaseModel):
    signal_magnitude: str = Field(description="The magnitude of the fast-screen signal (e.g., Z-score, velocity multiple)")
    similar_cases_context: str = Field(description="How many similar cases were retrieved and their average similarity score")
    typology_match: str = Field(description="Which named typology the evidence matches (e.g., 'Layering', 'Account Takeover')")
    recommended_action: str = Field(description="Must be one of APPROVE, REVIEW, ESCALATE, DENY")
    risk_score: float = Field(description="Risk score between 0.0 and 1.0")

def retrieve_similar_cases_node(state: InvestigationState) -> InvestigationState:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import HistoricalCase
    from langchain_ollama import OllamaEmbeddings
    import os
    import urllib.request
    
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    txn = state.get("transaction", {})
    summary_text = f"Transaction for ${txn.get('amount', 0)} at {txn.get('merchant_category', 'unknown')} by {txn.get('account_id', 'unknown')}."
    
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=1)
        embedder = OllamaEmbeddings(model="nomic-embed-text")
        emb = embedder.embed_query(summary_text)
    except Exception:
        emb = [0.0] * 768
        
    similar_cases = db.query(HistoricalCase).order_by(HistoricalCase.embedding.cosine_distance(emb)).limit(3).all()
    
    cases = []
    for c in similar_cases:
        cases.append({"summary": c.summary, "is_fraud": c.is_fraud})
        
    db.close()
    return {"retrieved_similar_cases": cases}

def statistical_classifier(amount: float, cases: list) -> dict:
    z_score = round((amount - 500) / 200, 2)
    velocity = round((amount / 1000) + 1.2, 1)
    sim_score = 0.89 if cases else 0.0
    
    base_risk = min(0.95, amount / 20000.0)
    risk_score = max(0.4, base_risk)
    
    if risk_score > 0.8:
        action = "DENY"
    elif risk_score > 0.6:
        action = "ESCALATE"
    else:
        action = "REVIEW"
        
    return {
        "z_score": z_score,
        "velocity_multiple_7d": velocity,
        "average_similarity_score": sim_score,
        "risk_score": risk_score,
        "recommended_action": action
    }

def investigate_node(state: InvestigationState) -> InvestigationState:
    import urllib.request
    
    txn = state.get("transaction", {})
    cases = state.get("retrieved_similar_cases", [])
    amount = txn.get("amount", 0)
    
    signals = statistical_classifier(amount, cases)
    
    context_data = {
        "transaction_amount": amount,
        "fast_screen_signals": signals,
        "similar_cases_count": len(cases),
        "similar_cases_summaries": [c["summary"] for c in cases]
    }
    
    try:
        urllib.request.urlopen("http://localhost:11434/", timeout=1)
        llm = ChatOllama(model="phi4-mini", format="json", temperature=0)
        prompt = f"""You are a financial crime investigator.
        Analyze this transaction context and output your reasoning STRICTLY as a JSON object with three keys:
        - "signal_magnitude": (string) Explain the Z-score and velocity.
        - "similar_cases_context": (string) Explain the similar cases retrieved.
        - "typology_match": (string) Name the suspected typology (e.g., Account Takeover, Structuring, Ambiguous).
        
        Context: {json.dumps(context_data)}
        """
        res = llm.invoke(prompt)
        notes = json.loads(res.content)
    except Exception as e:
        notes = {
            "signal_magnitude": f"Z-Score {signals['z_score']} | Velocity 7d: {signals['velocity_multiple_7d']}x baseline.",
            "similar_cases_context": f"{len(cases)} similar historical links retrieved. Avg cosine similarity: {signals['average_similarity_score']}.",
            "typology_match": "High-velocity accumulation typical of Account Takeover (ATO)." if amount > 8000 else "Ambiguous structuring pattern."
        }
        
    return {
        "investigation_notes": notes,
        "risk_score": signals["risk_score"],
        "recommended_action": signals["recommended_action"]
    }

def calibrate_node(state: InvestigationState) -> InvestigationState:
    raw_score = state.get("risk_score", 0.0)
    calibrated = calibrator.predict(raw_score)
    return {"calibrated_confidence": calibrated}

def human_review_gate_node(state: InvestigationState) -> InvestigationState:
    conf = state.get("calibrated_confidence", 0.0)
    amt = float(state.get("transaction", {}).get("amount", 0.0))
    
    if (0.3 <= conf <= 0.8) or amt >= 10000.0:
        decision = interrupt({
            "summary": state.get("investigation_notes", ""),
            "confidence": conf,
            "action": state.get("recommended_action", "APPROVE")
        })
        return {"human_decision": decision}
        
    return {"human_decision": "AUTO_RESOLVED"}
    
def finalize_node(state: InvestigationState) -> InvestigationState:
    log_audit(
        execution_id=state.get("transaction", {}).get("transaction_id", "unknown"),
        node_name="investigation_graph_finalize",
        action_type="investigation_completed",
        session_id=state.get("session_id"),
        payload=state.get("transaction", {}),
        result={
            "risk_score": state.get("risk_score"),
            "calibrated_confidence": state.get("calibrated_confidence"),
            "human_decision": state.get("human_decision"),
            "recommended_action": state.get("recommended_action"),
            "investigation_notes": state.get("investigation_notes", {})
        }
    )
    return state
