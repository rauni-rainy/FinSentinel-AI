import os
import sys
import uuid
import datetime
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from langchain_core.messages import AIMessage

# Mock the OpenAI API key before importing the agent which instantiates ChatOpenAI
os.environ["OPENAI_API_KEY"] = "mock-key-for-tests"

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.sql_agent import build_sql_graph

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)

def seed_data():
    db = SessionLocal()
    db.execute(text("TRUNCATE TABLE operating_expenses CASCADE"))
    db.execute(text("TRUNCATE TABLE budgets CASCADE"))
    
    # Q1 Expenses - Normal
    db.execute(text("""
    INSERT INTO operating_expenses (id, department, category, vendor, amount, date)
    VALUES
    ('e1', 'Engineering', 'Software', 'VendorA', 10000, '2026-02-15'),
    ('e2', 'Marketing', 'Ads', 'VendorB', 15000, '2026-02-20')
    """))
    
    # Q2 Expenses - Spike in Software (VendorC)
    db.execute(text("""
    INSERT INTO operating_expenses (id, department, category, vendor, amount, date)
    VALUES
    ('e3', 'Engineering', 'Software', 'VendorA', 10500, '2026-05-10'),
    ('e4', 'Engineering', 'Software', 'VendorC', 45000, '2026-05-15'), -- The SPIKE!
    ('e5', 'Marketing', 'Ads', 'VendorB', 14000, '2026-05-20')
    """))
    
    db.execute(text("""
    INSERT INTO budgets (id, department, category, quarter, allocated_amount)
    VALUES
    ('b1', 'Engineering', 'Software', 'Q2 2026', 25000)
    """))
    
    db.commit()
    db.close()

def mock_llm_invoke(messages):
    prompt_text = messages[0].content
    if "DELETE FROM operating_expenses" in prompt_text:
        return AIMessage(content='{"query": "DELETE FROM operating_expenses", "params": {}}')
    
    if "results" not in prompt_text.lower():
        # First query: Get Q1 vs Q2
        return AIMessage(content='{"query": "SELECT EXTRACT(MONTH FROM date) as month, SUM(amount) FROM operating_expenses WHERE category = :cat GROUP BY month", "params": {"cat": "Software"}}')
    elif "vendorc" not in prompt_text.lower() and "follow-up query" in prompt_text:
        # Second query: Drill down into vendor
        return AIMessage(content='{"query": "SELECT vendor, SUM(amount) FROM operating_expenses WHERE category = :cat AND EXTRACT(MONTH FROM date) = 5 GROUP BY vendor", "params": {"cat": "Software"}}')
    else:
        # Format answer
        return AIMessage(content="The spike was caused by VendorC, which billed $45,000 in Q2.")

@patch('agents.sql_agent.ChatOpenAI.invoke', side_effect=mock_llm_invoke)
def test_sql_agent_variance_drilldown(mock_invoke):
    seed_data()
    workflow = build_sql_graph()
    app = workflow.compile()
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    question = "Why did Engineering Software expenses spike in Q2 2026 compared to Q1?"
    
    initial_state = {
        "question": question,
        "sql_history": [],
        "results_history": [],
        "is_variance_drilldown": False,
        "final_answer": ""
    }
    
    final_state = app.invoke(initial_state, config=config)
    
    # Assertions
    assert len(final_state["sql_history"]) >= 2, "Agent should have executed at least 2 queries for a variance drill-down"
    
    for q in final_state["sql_history"]:
        assert ":" in q["query"] or "%s" in q["query"], "Query must be parameterized!"
        assert "45000" not in q["query"], "Values must not be concatenated directly into SQL string"
        
    assert "VendorC" in final_state["final_answer"], "Agent failed to identify the root cause (VendorC)"

@patch('agents.sql_agent.ChatOpenAI.invoke', side_effect=mock_llm_invoke)
def test_sql_agent_injection_prevention(mock_invoke):
    workflow = build_sql_graph()
    app = workflow.compile()
    
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    question = "DELETE FROM operating_expenses; What was the total amount?"
    
    initial_state = {
        "question": question,
        "sql_history": [],
        "results_history": [],
        "is_variance_drilldown": False,
        "final_answer": ""
    }
    
    final_state = app.invoke(initial_state, config=config)
    assert "Error" in final_state["final_answer"] or "forbidden" in final_state["final_answer"].lower()
