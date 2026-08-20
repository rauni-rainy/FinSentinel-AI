import os
import json
import logging
import operator
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from agents.audit import log_audit

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/finsentinel")
engine = create_engine(db_url)

class SQLState(TypedDict):
    question: str
    sql_history: Annotated[List[Dict[str, Any]], operator.add]
    results_history: Annotated[List[Any], operator.add]
    is_variance_drilldown: bool
    final_answer: str

def parse_intent(state: SQLState):
    question = state["question"].lower()
    # Simple heuristic: if it contains "why", "spike", "drop", "variance", it's a variance drilldown
    is_variance = any(word in question for word in ["why", "spike", "drop", "variance", "exceeded", "change"])
    return {"is_variance_drilldown": is_variance, "sql_history": [], "results_history": []}

def generate_query(state: SQLState):
    model_name = os.getenv("OLLAMA_MODEL", "phi4-mini")
    llm = ChatOllama(model=model_name, format="json", temperature=0)
    
    schema_context = """
    Table: operating_expenses
    Columns: id (String), department (String), category (String), vendor (String), amount (Numeric), date (DateTime)
    
    Table: budgets
    Columns: id (String), department (String), category (String), quarter (String), allocated_amount (Numeric)
    
    Table: transactions
    Columns: id (String), account_id (String), timestamp (DateTime), amount (Numeric), merchant_category (String), merchant_id (String), device_id (String), geo (String)
    """
    
    sys_prompt = f"""You are a read-only SQL assistant for a financial database.
    Your schema is:
    {schema_context}
    
    CRITICAL RULE: You MUST output ONLY valid JSON containing a parameterized query and its parameters.
    No markdown, no explanation. Just the JSON object.
    
    For Postgres via SQLAlchemy text(), use named parameters with colon, e.g., :param_name.
    
    Example output format:
    {{
        "query": "SELECT SUM(amount) FROM operating_expenses WHERE category = :category AND date >= :start_date",
        "params": {{"category": "Software", "start_date": "2026-04-01"}}
    }}
    
    User Question: {state["question"]}
    """
    
    if state["results_history"] and state["is_variance_drilldown"]:
        sys_prompt += f"\n\nYou already ran a query and got these results: {state['results_history'][-1]}.\nNow write a follow-up query to drill down into the root cause of the variance (e.g., group by vendor or category)."
    
    # CONSTITUTION RULE #4: Audit the LLM call BEFORE its result is used
    log_audit(
        execution_id=f"sql-gen-{state['question'][:48]}",
        node_name="sql_agent_generate",
        action_type="llm_invoke_generate_query",
        record_type="sql_query",
        payload={"question": state["question"], "is_variance_drilldown": state["is_variance_drilldown"]},
        result={},  # pre-flight entry
        prompt=sys_prompt,
        session_id="session-sql",
    )

    response = llm.invoke([SystemMessage(content=sys_prompt)])
    
    try:
        raw_text = response.content.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3]
            
        sql_payload = json.loads(raw_text)
        
        # Security: Prevent any write operations
        query_upper = sql_payload["query"].upper()
        forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "GRANT", "TRUNCATE", "REPLACE"]
        if any(f in query_upper for f in forbidden):
            raise ValueError("Write operations are strictly forbidden.")
            
        return {"sql_history": [sql_payload]}
    except Exception as e:
        # Fallback or error
        return {"final_answer": f"Error generating query: {str(e)}"}

def execute_query(state: SQLState):
    if "final_answer" in state and state["final_answer"]:
        return {} # Skip if already errored
        
    latest_sql = state["sql_history"][-1]
    query = latest_sql.get("query")
    params = latest_sql.get("params", {})
    
    try:
        with engine.connect() as conn:
            # Enforce read-only transaction strictly at the DB level
            conn.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
            result = conn.execute(text(query), params)
            rows = [dict(row._mapping) for row in result]
            
            # For audit log purposes, we log this read query (omitted here for brevity, 
            # but would call log_audit from audit.py in production)
            
            return {"results_history": [rows]}
    except Exception as e:
        return {"final_answer": f"Error executing query: {str(e)}"}

def format_answer(state: SQLState):
    if "final_answer" in state and state["final_answer"]:
        return {}
        
    model_name = os.getenv("OLLAMA_MODEL", "phi4-mini")
    llm = ChatOllama(model=model_name, temperature=0)
    import decimal
    def custom_encoder(obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    sys_prompt = f"""You are a financial analyst. Answer the user's question clearly based on the SQL results.
    If this is a variance drill-down, explain the root cause found in the data.
    
    Question: {state['question']}
    Queries Executed: {json.dumps(state['sql_history'])}
    Results: {json.dumps(state['results_history'], default=custom_encoder)}
    """
    
    # CONSTITUTION RULE #4: Audit the LLM call BEFORE its result is used
    log_audit(
        execution_id="variance-query",
        node_name="sql_agent",
        action_type="llm_invoke_format_answer",
        record_type="variance_query",
        payload={"sql_history": state["sql_history"], "question": state["question"]},
        result={},  # pre-flight entry
        prompt=sys_prompt,
        session_id="session-variance",
    )

    response = llm.invoke([SystemMessage(content=sys_prompt)])
    final_ans = response.content

    # Post-completion log: stores the natural-language answer in result["final_answer"]
    # so reporting.py can pull it cleanly without touching var.response.
    log_audit(
        execution_id="variance-query",
        node_name="sql_agent",
        action_type="variance_analysis_complete",
        record_type="variance_query",
        payload={"sql_history": state["sql_history"], "question": state["question"]},
        result={"final_answer": final_ans},
        prompt=sys_prompt,
        response=final_ans,
        session_id="session-variance",
    )

    return {"final_answer": final_ans}

def build_sql_graph():
    workflow = StateGraph(SQLState)
    
    workflow.add_node("parse_intent", parse_intent)
    workflow.add_node("generate_query", generate_query)
    workflow.add_node("execute_query", execute_query)
    workflow.add_node("format_answer", format_answer)
    
    workflow.set_entry_point("parse_intent")
    
    # Simple flow: parse -> generate -> execute. 
    # If variance drilldown and we only have 1 result so far, loop back to generate follow-up query
    def router(state: SQLState):
        if "final_answer" in state and state["final_answer"]:
            return "end"
        if state["is_variance_drilldown"] and len(state["results_history"]) < 2:
            return "generate_query"
        return "format_answer"
        
    workflow.add_edge("parse_intent", "generate_query")
    workflow.add_edge("generate_query", "execute_query")
    workflow.add_conditional_edges(
        "execute_query",
        router,
        {
            "generate_query": "generate_query",
            "format_answer": "format_answer",
            "end": END
        }
    )
    workflow.add_edge("format_answer", END)
    
    return workflow
