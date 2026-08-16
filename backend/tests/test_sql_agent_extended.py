import os
import sys
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from dotenv import load_dotenv
from langchain_core.messages import AIMessage

# Mock the OpenAI API key before importing the agent
os.environ["OPENAI_API_KEY"] = "mock-key-for-tests"

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from agents.sql_agent import build_sql_graph

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

def mock_llm_extended(messages):
    prompt_text = messages[0].content
    
    # 1. Total budget for Engineering Software
    if "total budget for engineering software" in prompt_text.lower():
        return AIMessage(content='{"query": "SELECT SUM(allocated_amount) FROM budgets WHERE department = :dept AND category = :cat", "params": {"dept": "Engineering", "cat": "Software"}}')
        
    # 2. Ads spent in Marketing
    elif "spent on ads in marketing" in prompt_text.lower():
        return AIMessage(content='{"query": "SELECT SUM(amount) FROM operating_expenses WHERE department = :dept AND category = :cat", "params": {"dept": "Marketing", "cat": "Ads"}}')
        
    # 3. Highest paid vendor
    elif "vendor was paid the most" in prompt_text.lower():
        return AIMessage(content='{"query": "SELECT vendor, SUM(amount) as total FROM operating_expenses GROUP BY vendor ORDER BY total DESC LIMIT 1", "params": {}}')
        
    # 4. Variance question
    elif "why did operating expenses drop" in prompt_text.lower():
        if "results" not in prompt_text.lower():
            return AIMessage(content='{"query": "SELECT EXTRACT(MONTH FROM date) as month, SUM(amount) FROM operating_expenses GROUP BY month", "params": {}}')
        else:
            return AIMessage(content='{"query": "SELECT category, SUM(amount) FROM operating_expenses WHERE EXTRACT(MONTH FROM date) = 8 GROUP BY category", "params": {}}')
            
    # 5. Injection Attempt 1 (DROP)
    elif "drop table" in prompt_text.lower():
        return AIMessage(content='{"query": "DROP TABLE operating_expenses;", "params": {}}')
        
    # 6. Injection Attempt 2 (UPDATE)
    elif "update budgets" in prompt_text.lower():
        return AIMessage(content='{"query": "UPDATE budgets SET allocated_amount = 99999 WHERE id = :id", "params": {"id": "b1"}}')

    else:
        # Default fallback for format_answer node
        return AIMessage(content="Simulated Answer.")

@patch('agents.sql_agent.ChatOpenAI.invoke', side_effect=mock_llm_extended)
def test_6_varied_questions(mock_invoke):
    workflow = build_sql_graph()
    app = workflow.compile()
    
    questions = [
        # Normal questions
        ("What is the total budget for Engineering Software?", True, False),
        ("How much was spent on Ads in Marketing?", True, False),
        ("Which vendor was paid the most in Q1?", True, False),
        # Variance question
        ("Why did operating expenses drop in Q3?", True, True),
        # Malicious Injections
        ("DROP TABLE operating_expenses; --", False, False),
        ("SELECT * FROM operating_expenses WHERE category = 'Software'; UPDATE budgets SET allocated_amount = 99999", False, False)
    ]
    
    for q, should_succeed, is_variance in questions:
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        initial_state = {
            "question": q,
            "sql_history": [],
            "results_history": [],
            "is_variance_drilldown": False,
            "final_answer": ""
        }
        
        final_state = app.invoke(initial_state, config=config)
        
        print(f"\nQ: {q}")
        print(f"Final Answer: {final_state['final_answer']}")
        
        if should_succeed:
            assert "Error" not in final_state["final_answer"], f"Failed on valid question: {q}"
            for sql_obj in final_state["sql_history"]:
                assert "query" in sql_obj and "params" in sql_obj, "Not properly parameterized JSON!"
            
            if is_variance:
                assert len(final_state["sql_history"]) >= 2, "Variance drilldown failed to loop"
        else:
            assert "Error" in final_state["final_answer"] or "forbidden" in final_state["final_answer"].lower(), f"Failed to block injection: {q}"
