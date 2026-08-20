import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from services.cost_service import (
    CostMetricsSummary,
    ScaleSimulationInput,
    ScaleSimulationOutput,
    get_cost_efficiency_metrics,
    simulate_scale_roi
)

client = TestClient(app)

def test_cost_efficiency_metrics_computation():
    """
    Verifies that cost metrics correctly calculate:
    - Fast-path deflection percentage (>85%)
    - Unit cost per 1,000 transactions scored (<$1.00 vs $20.00 naive benchmark)
    - Cost reduction percentage (>90%)
    - Route attribution breakdown
    """
    metrics = get_cost_efficiency_metrics()
    
    assert isinstance(metrics, CostMetricsSummary)
    assert metrics.total_transactions_scored > 0
    assert metrics.fast_path_deflected_count > 0
    assert metrics.llm_escalated_count >= 0
    
    # Verify deflection + escalation = 100%
    total_pct = metrics.fast_path_deflection_rate_pct + metrics.escalation_rate_pct
    assert pytest.approx(total_pct, 0.1) == 100.0
    
    # Fast path deflection rate must be disciplined (Constitution: free checks filter out the bulk)
    assert metrics.fast_path_deflection_rate_pct >= 85.0
    
    # Tiered cost per 1k transactions must show dramatic efficiency over naive $20/1k
    assert metrics.actual_cost_per_1k_usd < 1.00
    assert metrics.naive_cost_per_1k_usd == 20.00
    assert metrics.cost_reduction_pct >= 95.0
    
    # Route attribution must cover Fast-Path and Escalated graph
    routes = [r["route_name"] for r in metrics.route_attribution]
    assert any("Fast-Path" in r for r in routes)
    assert any("Escalated" in r for r in routes)

def test_scale_roi_simulation_math():
    """
    Verifies the mathematical accuracy of the enterprise scale simulator.
    """
    # 10 Million transactions/mo, 95% deflection, $0.015 per LLM call vs $0.02 naive
    sim_input = ScaleSimulationInput(
        monthly_transaction_volume=10000000,
        fast_path_deflection_rate_pct=95.0,
        llm_cost_per_call_usd=0.015,
        naive_cost_per_call_usd=0.020
    )
    
    sim_output = simulate_scale_roi(sim_input)
    
    # 5% of 10M = 500,000 escalated calls
    assert sim_output.escalated_monthly_calls == 500000
    
    # FinSentinel Spend = 500,000 * $0.015 = $7,500.00
    assert pytest.approx(sim_output.finsentinel_monthly_spend_usd, 0.01) == 7500.00
    
    # Naive Spend = 10,000,000 * $0.020 = $200,000.00
    assert pytest.approx(sim_output.naive_monthly_spend_usd, 0.01) == 200000.00
    
    # Monthly Savings = $192,500.00
    assert pytest.approx(sim_output.monthly_savings_usd, 0.01) == 192500.00
    
    # Annual Savings = 192,500 * 12 = $2,310,000.00
    assert pytest.approx(sim_output.annual_savings_usd, 0.01) == 2310000.00
    
    # Efficiency multiplier = 200000 / 7500 = 26.7x
    assert pytest.approx(sim_output.efficiency_multiplier, 0.1) == 26.7
    
    # FinSentinel cost per 1k = $0.75 / 1k txns vs $20.00 / 1k txns
    assert pytest.approx(sim_output.finsentinel_cost_per_1k_usd, 0.01) == 0.75
    assert pytest.approx(sim_output.naive_cost_per_1k_usd, 0.01) == 20.00

def test_api_cost_efficiency_endpoints():
    """
    Verifies HTTP GET /metrics/cost-efficiency and POST /metrics/cost-simulate.
    """
    # 1. GET /metrics/cost-efficiency
    resp_get = client.get("/metrics/cost-efficiency")
    assert resp_get.status_code == 200
    data = resp_get.json()
    assert "actual_cost_per_1k_usd" in data
    assert "fast_path_deflection_rate_pct" in data
    assert "route_attribution" in data
    assert "time_series_trend" in data
    
    # 2. POST /metrics/cost-simulate
    sim_payload = {
        "monthly_transaction_volume": 5000000,
        "fast_path_deflection_rate_pct": 92.0,
        "llm_cost_per_call_usd": 0.012,
        "naive_cost_per_call_usd": 0.020
    }
    resp_post = client.post("/metrics/cost-simulate", json=sim_payload)
    assert resp_post.status_code == 200
    sim_data = resp_post.json()
    assert sim_data["monthly_transaction_volume"] == 5000000
    assert "annual_savings_usd" in sim_data
    assert sim_data["annual_savings_usd"] > 0
