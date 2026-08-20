import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from services.credit_triage import (
    ApplicantProfile,
    MacroIndicators,
    CalculatedRatios,
    RiskFactor,
    AdverseActionFactor,
    StressScenarioInput,
    StressScenarioOutput,
    UnderwriterCreditMemo,
    RiskFactorSummary,
    evaluate_credit_risk,
    calculate_stress_scenario,
    generate_credit_memo,
    extract_adverse_action_factors,
    get_macro_benchmarks,
    get_preset_applicants
)
from agents.audit import verify_audit_chain

client = TestClient(app)

FORBIDDEN_DECISION_KEYS = {
    "decision",
    "approved",
    "approve",
    "deny",
    "denied",
    "recommendation",
    "recommended_action",
    "action",
    "disposition",
    "underwriting_decision",
    "approval_status",
    "verdict"
}

def test_schema_structural_guarantee_no_decision_fields():
    """
    CONSTITUTION RULE #6 ENFORCEMENT:
    Ensures that ALL Credit Triage schemas (Summary, Ratios, Risk Factors,
    Stress Outputs, Adverse Action Codes, Credit Memos) make it structurally impossible
    to emit an autonomous approve/deny decision.
    """
    models_to_check = [
        RiskFactorSummary,
        CalculatedRatios,
        RiskFactor,
        AdverseActionFactor,
        StressScenarioOutput,
        UnderwriterCreditMemo
    ]
    
    for model in models_to_check:
        fields = set(model.model_fields.keys())
        for forbidden in FORBIDDEN_DECISION_KEYS:
            assert forbidden not in fields, f"Structural violation: '{forbidden}' found in {model.__name__} schema!"

def test_dti_and_utilization_calculations():
    """
    Verifies accurate mathematical computation of:
    - Front-End DTI
    - Back-End DTI
    - Revolving Credit Utilization
    - Payment-to-Income (PTI)
    - Liquidity Coverage
    """
    applicant = ApplicantProfile(
        applicant_id="APP-TEST-001",
        applicant_name="Jane Doe",
        monthly_gross_income=10000.0,
        existing_monthly_debt=2000.0,
        proposed_loan_payment=1500.0,
        revolving_credit_balance=6000.0,
        total_credit_limit=20000.0,
        liquid_assets=35000.0,
        employment_duration_years=5.5,
        industry_sector="Healthcare",
        stated_loan_purpose="Debt Consolidation"
    )
    
    summary = evaluate_credit_risk(applicant)
    ratios = summary.ratios
    
    # Front-end DTI = (1500 / 10000) * 100 = 15.0%
    assert pytest.approx(ratios.front_end_dti_pct, 0.01) == 15.0
    # Back-end DTI = ((2000 + 1500) / 10000) * 100 = 35.0%
    assert pytest.approx(ratios.back_end_dti_pct, 0.01) == 35.0
    # Credit utilization = (6000 / 20000) * 100 = 30.0%
    assert pytest.approx(ratios.credit_utilization_pct, 0.01) == 30.0
    # Payment to income = (1500 / 10000) * 100 = 15.0%
    assert pytest.approx(ratios.payment_to_income_pct, 0.01) == 15.0
    # Liquidity coverage = 35000 / (2000 + 1500) = 10.0 months
    assert pytest.approx(ratios.liquidity_coverage_months, 0.01) == 10.0

def test_stress_testing_simulation_math():
    """
    Verifies the mathematical sensitivity calculations for interest rate shock,
    income haircuts, and expense inflation.
    """
    applicant = ApplicantProfile(
        applicant_id="APP-STRESS-001",
        applicant_name="Stress Test Borrower",
        monthly_gross_income=10000.0,
        existing_monthly_debt=2000.0,
        proposed_loan_payment=2000.0,
        revolving_credit_balance=12000.0,
        total_credit_limit=24000.0,
        liquid_assets=24000.0,
        employment_duration_years=4.0,
        industry_sector="Technology",
        stated_loan_purpose="Expansion"
    )
    
    # Scenario: +200 bps rate hike, 10% income haircut, 5% inflation
    shock = StressScenarioInput(
        scenario_name="Adverse Scenario",
        rate_shock_bps=200.0,
        income_haircut_pct=10.0,
        inflation_expense_shock_pct=5.0
    )
    
    result = calculate_stress_scenario(applicant, shock)
    
    # Stressed income = 10000 * 0.9 = 9000.0
    assert result.stressed_monthly_income == 9000.0
    
    # Extra revolving monthly interest = (12000 * 0.02) / 12 = $20.0
    # Proposed payment shock = 2000 * (1 + 0.02 * 0.4) = 2000 * 1.008 = $2016.0
    # Existing debt inflation = 2000 * 1.05 = $2100.0
    # Stressed total monthly debt = 2100 + 2016 + 20 = $4136.0
    assert pytest.approx(result.stressed_monthly_debt, 1.0) == 4136.0
    
    # Stressed back-end DTI = 4136.0 / 9000.0 = 45.96%
    assert pytest.approx(result.stressed_back_end_dti_pct, 0.1) == 45.96
    
    # Stressed residual income = 9000 - 4136 = 4864.0
    assert pytest.approx(result.stressed_residual_income, 1.0) == 4864.0
    
    # Stressed liquidity coverage = 24000 / 4136 = 5.8 months
    assert pytest.approx(result.stressed_liquidity_coverage_months, 0.1) == 5.80

def test_fcra_ecoa_adverse_action_factor_extraction():
    """
    Verifies that FCRA/ECOA principal contributing factors are ranked and generated
    accurately based on risk metrics without emitting autonomous decisions.
    """
    applicant = ApplicantProfile(
        applicant_id="APP-FCRA-001",
        applicant_name="Adverse Factor Candidate",
        monthly_gross_income=5000.0,
        existing_monthly_debt=2200.0,
        proposed_loan_payment=800.0,
        revolving_credit_balance=18000.0,
        total_credit_limit=20000.0,
        liquid_assets=1500.0,
        employment_duration_years=0.5,
        industry_sector="Retail & Consumer",
        stated_loan_purpose="Working Capital"
    )
    
    summary = evaluate_credit_risk(applicant)
    factors = summary.adverse_action_factors
    
    assert len(factors) >= 3
    # First factor must have rank 1
    assert factors[0].rank == 1
    
    codes = [f.factor_code for f in factors]
    assert "FCRA-DTI-01" in codes
    assert "FCRA-UTIL-02" in codes
    assert "FCRA-LIQ-03" in codes

def test_underwriter_credit_memo_generation():
    """
    Verifies that the Underwriter Credit Memo renders formatted markdown,
    includes the audit hash reference, stress table, checklist, and institutional disclaimer.
    """
    applicant = ApplicantProfile(
        applicant_id="APP-MEMO-001",
        applicant_name="Jane Doe",
        monthly_gross_income=12000.0,
        existing_monthly_debt=1500.0,
        proposed_loan_payment=1500.0,
        revolving_credit_balance=3000.0,
        total_credit_limit=30000.0,
        liquid_assets=50000.0,
        employment_duration_years=6.0,
        industry_sector="Healthcare",
        stated_loan_purpose="Residential Mortgage"
    )
    
    summary = evaluate_credit_risk(applicant)
    memo = generate_credit_memo(
        applicant=applicant,
        summary=summary,
        underwriter_name="Senior Underwriter John Smith",
        underwriter_notes="Verified 2 years tax returns. Compensating factor: substantial liquid reserves ($50k).",
        checklist_verifications={"income_w2": True, "liquid_assets": True, "credit_bureau": True}
    )
    
    assert memo.memo_id.startswith("MEMO-")
    assert "Senior Underwriter John Smith" in memo.formatted_markdown
    assert "Verified 2 years tax returns" in memo.formatted_markdown
    assert "Macro Stress-Testing" in memo.formatted_markdown
    assert summary.audit_id in memo.formatted_markdown
    assert "DECISION SUPPORT ONLY" in memo.disclaimer

def test_audit_logging_and_chain_verification():
    """
    Verifies that every credit triage execution is recorded in the immutable audit log
    and preserves the cryptographic hash chain.
    """
    from sqlalchemy import create_engine, text
    from agents.audit import db_url
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE audit_logs CASCADE"))

    applicant = ApplicantProfile(
        applicant_id="APP-TEST-AUDIT-001",
        applicant_name="Audit Verification Candidate",
        monthly_gross_income=8500.0,
        existing_monthly_debt=1200.0,
        proposed_loan_payment=800.0,
        revolving_credit_balance=3000.0,
        total_credit_limit=15000.0,
        liquid_assets=18000.0,
        employment_duration_years=3.0,
        industry_sector="Technology",
        stated_loan_purpose="Home Improvement"
    )
    
    summary = evaluate_credit_risk(applicant)
    assert summary.audit_id is not None
    assert verify_audit_chain() is True

def test_api_credit_triage_endpoints():
    """
    Verifies HTTP endpoints:
    - GET /credit/macro-benchmarks
    - GET /credit/presets
    - POST /credit/triage
    - POST /credit/stress-test
    - POST /credit/export-memo
    """
    # 1. Macro benchmarks
    resp_macro = client.get("/credit/macro-benchmarks")
    assert resp_macro.status_code == 200
    macro_data = resp_macro.json()
    assert "benchmark_fed_funds_rate_pct" in macro_data

    # 2. Presets
    resp_presets = client.get("/credit/presets")
    assert resp_presets.status_code == 200
    presets = resp_presets.json()
    assert len(presets) >= 4
    
    # 3. Evaluate Triage POST
    test_applicant = presets[0]["profile"]
    resp_triage = client.post("/credit/triage", json=test_applicant)
    assert resp_triage.status_code == 200
    triage_result = resp_triage.json()
    
    # Verify required keys & stress scenarios
    assert "ratios" in triage_result
    assert "macro_context" in triage_result
    assert "risk_factors" in triage_result
    assert "adverse_action_factors" in triage_result
    assert "stress_scenarios" in triage_result
    assert "disclaimer" in triage_result
    
    # 4. Custom stress test POST
    stress_payload = {
        "applicant": test_applicant,
        "scenario": {
            "scenario_name": "Custom Severe Hike",
            "rate_shock_bps": 250.0,
            "income_haircut_pct": 15.0,
            "inflation_expense_shock_pct": 5.0
        }
    }
    resp_stress = client.post("/credit/stress-test", json=stress_payload)
    assert resp_stress.status_code == 200
    stress_data = resp_stress.json()
    assert stress_data["scenario_name"] == "Custom Severe Hike"
    assert "stressed_back_end_dti_pct" in stress_data

    # 5. Export Memo POST
    memo_payload = {
        "applicant": test_applicant,
        "underwriter_name": "Auditor Sarah",
        "underwriter_notes": "All ratios reviewed.",
        "checklist_verifications": {"w2": True}
    }
    resp_memo = client.post("/credit/export-memo", json=memo_payload)
    assert resp_memo.status_code == 200
    memo_data = resp_memo.json()
    assert "formatted_markdown" in memo_data
    assert "Auditor Sarah" in memo_data["formatted_markdown"]

    # Verify ZERO decision fields in JSON response payload
    for forbidden in FORBIDDEN_DECISION_KEYS:
        assert forbidden not in triage_result, f"API returned forbidden field: {forbidden}"
        assert forbidden not in stress_data, f"Stress API returned forbidden field: {forbidden}"
        assert forbidden not in memo_data, f"Memo API returned forbidden field: {forbidden}"
