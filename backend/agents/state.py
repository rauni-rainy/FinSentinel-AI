from typing import TypedDict, Annotated, List, Optional
import operator

class InvestigationState(TypedDict):
    transaction: dict
    fast_screen_result: str
    retrieved_similar_cases: list[dict]
    investigation_notes: str
    risk_score: float
    calibrated_confidence: float
    recommended_action: str
    human_decision: Optional[str]
    session_id: Optional[str]
    messages: Annotated[list, operator.add]
