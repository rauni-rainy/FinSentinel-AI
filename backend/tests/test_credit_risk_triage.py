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
    RiskFactorSummary,
    evaluate_credit_risk,
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
    Ensures that the RiskFactorSummary schema makes it structurally impossible
    to emit an autonomous approve/deny decision.
    """
    fields = set(RiskFactorSummary.model_fields.keys())
    
    # Check that no forbidden decision keywords exist in the field names
    for forbidden in FORBIDDEN_DECISION_KEYS:
        assert forbidden not in fields, f"Structural violation: '{forbidden}' found in RiskFactorSummary schema!"
        
    # Check nested ratio and factor fields
    ratio_fields = set(CalculatedRatios.model_fields.keys())
    for forbidden in FORBIDDEN_DECISION_KEYS:
        assert forbidden not in ratio_fields, f"Structural violation: '{forbidden}' found in CalculatedRatios schema!"
        
    factor_fields = set(RiskFactor.model_fields.keys())
    for forbidden in FORBIDDEN_DECISION_KEYS:
        assert forbidden not in factor_fields, f"Structural violation: '{forbidden}' found in RiskFactor schema!"

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

def test_macroeconomic_cross_referencing_and_risk_factors():
    """
    Verifies that macro stress indicators (interest rates, sector delinquency)
    correctly synthesize contextual risk factors for the human underwriter.
    """
    applicant = ApplicantProfile(
        applicant_id="APP-TEST-HIGH-RISK",
        applicant_name="Stressed Borrower",
        monthly_gross_income=6000.0,
        existing_monthly_debt=2800.0,
        proposed_loan_payment=900.0,
        revolving_credit_balance=18000.0,
        total_credit_limit=20000.0,
        liquid_assets=2000.0,
        employment_duration_years=0.8,
        industry_sector="Commercial Real Estate",
        stated_loan_purpose="Working Capital"
    )
    
    macro = MacroIndicators(
        benchmark_fed_funds_rate_pct=5.50,
        sector_default_rate_pct=4.8,
        cpi_inflation_yoy_pct=3.6,
        regional_unemployment_pct=4.2
    )
    
    summary = evaluate_credit_risk(applicant, macro=macro)
    
    # Back-end DTI = (2800 + 900) / 6000 = 61.67%
    assert summary.ratios.back_end_dti_pct > 50.0
    # Credit utilization = 18000 / 20000 = 90.0%
    assert summary.ratios.credit_utilization_pct >= 80.0
    # Liquidity coverage = 2000 / 3700 = 0.54 months
    assert summary.ratios.liquidity_coverage_months < 1.0
    
    # Verify risk factors generated
    elevated_factors = [f for f in summary.risk_factors if f.factor_type == "ELEVATED_RISK"]
    assert len(elevated_factors) >= 3
    
    # Confirm categories covered
    categories = {f.category for f in summary.risk_factors}
    assert "LEVERAGE" in categories
    assert "LIQUIDITY" in categories
    assert "MACRO_PRESSURE" in categories
    
    # Underwriter narrative must be present and provide contextual summary
    assert len(summary.underwriter_narrative) > 20
    assert "decision support" in summary.disclaimer.lower()

def test_audit_logging_and_chain_verification():
    """
    Verifies that every credit triage execution is recorded in the immutable audit log
    and preserves the cryptographic hash chain.
    """
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
    
    # Verify cryptographic audit chain integrity
    assert verify_audit_chain() is True

def test_api_credit_triage_endpoints():
    """
    Verifies HTTP endpoints:
    - GET /credit/macro-benchmarks
    - GET /credit/presets
    - POST /credit/triage
    """
    # 1. Macro benchmarks
    resp_macro = client.get("/credit/macro-benchmarks")
    assert resp_macro.status_code == 200
    macro_data = resp_macro.json()
    assert "benchmark_fed_funds_rate_pct" in macro_data
    assert "sector_default_rates" in macro_data

    # 2. Presets
    resp_presets = client.get("/credit/presets")
    assert resp_presets.status_code == 200
    presets = resp_presets.json()
    assert len(presets) >= 3
    
    # 3. Evaluate Triage POST
    test_applicant = presets[0]["profile"]
    resp_triage = client.post("/credit/triage", json=test_applicant)
    assert resp_triage.status_code == 200
    triage_result = resp_triage.json()
    
    # Verify required keys
    assert "ratios" in triage_result
    assert "macro_context" in triage_result
    assert "risk_factors" in triage_result
    assert "underwriter_narrative" in triage_result
    assert "disclaimer" in triage_result
    
    # Verify ZERO decision fields in JSON response payload
    for forbidden in FORBIDDEN_DECISION_KEYS:
        assert forbidden not in triage_result, f"API returned forbidden field: {forbidden}"
