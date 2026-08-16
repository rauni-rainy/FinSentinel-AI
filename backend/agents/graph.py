from langgraph.graph import StateGraph, END
from agents.state import InvestigationState
from agents.nodes import (
    intake_node, 
    retrieve_similar_cases_node, 
    investigate_node, 
    calibrate_node, 
    human_review_gate_node, 
    finalize_node
)

def build_investigation_graph():
    workflow = StateGraph(InvestigationState)
    
    workflow.add_node("intake", intake_node)
    workflow.add_node("retrieve_similar_cases", retrieve_similar_cases_node)
    workflow.add_node("investigate", investigate_node)
    workflow.add_node("calibrate", calibrate_node)
    workflow.add_node("human_review_gate", human_review_gate_node)
    workflow.add_node("finalize", finalize_node)
    
    workflow.set_entry_point("intake")
    
    def route_after_intake(state: InvestigationState) -> str:
        if state.get("fast_screen_result") == "PASS":
            return "finalize"
        return "retrieve_similar_cases"

    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "retrieve_similar_cases": "retrieve_similar_cases",
            "finalize": "finalize"
        }
    )
    
    workflow.add_edge("retrieve_similar_cases", "investigate")
    workflow.add_edge("investigate", "calibrate")
    workflow.add_edge("calibrate", "human_review_gate")
    workflow.add_edge("human_review_gate", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow
