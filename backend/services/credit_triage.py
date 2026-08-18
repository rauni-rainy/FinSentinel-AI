import uuid
import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.audit import log_audit

# --- Strict Pydantic Data Models (CONSTITUTION RULE #6: Zero Decision Fields) ---

class ApplicantProfile(BaseModel):
    applicant_id: str = Field(default_factory=lambda: f"APP-{uuid.uuid4().hex[:8].upper()}")
    applicant_name: str
    monthly_gross_income: float = Field(gt=0, description="Gross monthly income in USD")
    existing_monthly_debt: float = Field(ge=0, description="Total monthly payments on existing obligations")
    proposed_loan_payment: float = Field(ge=0, description="Expected monthly payment for the requested loan")
    revolving_credit_balance: float = Field(ge=0, description="Total outstanding revolving/credit card balances")
    total_credit_limit: float = Field(gt=0, description="Total available revolving credit limit")
    liquid_assets: float = Field(ge=0, description="Total cash, checking, savings, and liquid marketable securities")
    employment_duration_years: float = Field(ge=0, description="Years in current role or industry")
    industry_sector: str = Field(default="General", description="Employment industry sector")
    stated_loan_purpose: str = Field(default="General Credit", description="Stated purpose of the credit facility")

class MacroIndicators(BaseModel):
    benchmark_fed_funds_rate_pct: float = Field(default=5.25, description="Benchmark policy rate (Fed Funds)")
    sector_default_rate_pct: float = Field(default=2.4, description="Historical 12-month default/delinquency rate for applicant sector")
    cpi_inflation_yoy_pct: float = Field(default=3.1, description="Headline Consumer Price Index YoY change")
    regional_unemployment_pct: float = Field(default=3.9, description="Regional unemployment rate")

class CalculatedRatios(BaseModel):
    front_end_dti_pct: float = Field(description="Proposed loan payment divided by monthly gross income (%)")
    back_end_dti_pct: float = Field(description="Total monthly debt (existing + proposed) divided by monthly gross income (%)")
    credit_utilization_pct: float = Field(description="Revolving balances divided by total credit limit (%)")
    payment_to_income_pct: float = Field(description="Proposed installment payment to monthly income (%)")
    liquidity_coverage_months: float = Field(description="Liquid reserves in months of total post-loan monthly debt obligations")
    residual_income_monthly: float = Field(description="Monthly gross income remaining after all debt payments")

class RiskFactor(BaseModel):
    category: str = Field(description="Category: LEVERAGE, LIQUIDITY, MACRO_PRESSURE, STABILITY, or CREDIT_CAPACITY")
    factor_type: str = Field(description="POSITIVE_MITIGANT, NEUTRAL, or ELEVATED_RISK")
    severity: str = Field(description="LOW, MEDIUM, or HIGH")
    title: str
    description: str

class RiskFactorSummary(BaseModel):
    """
    STRUCTURAL ENFORCEMENT:
    This model contains strictly calculated ratios, macroeconomic context,
    categorized risk factors, and plain-language underwriter synthesis.
    It contains NO decision, recommendation, or approval fields.
    """
    applicant_id: str
    applicant_name: str
    evaluated_at: str
    ratios: CalculatedRatios
    macro_context: MacroIndicators
    risk_factors: List[RiskFactor]
    underwriter_narrative: str
    audit_id: Optional[str] = None
    disclaimer: str = Field(
        default="DECISION SUPPORT ONLY — NOT AN AUTONOMOUS DECISION. This summary surfaces objective financial ratios and risk factors for a human underwriter. Final credit authority resides exclusively with licensed human underwriters."
    )


# --- Sector Macro Indicators Database ---

SECTOR_DEFAULT_BENCHMARKS = {
    "Healthcare": 1.4,
    "Technology": 1.9,
    "Financial Services": 2.1,
    "Government / Education": 1.2,
    "Manufacturing": 2.8,
    "Retail & Consumer": 3.9,
    "Commercial Real Estate": 4.8,
    "Hospitality & Leisure": 4.5,
    "Construction": 4.2,
    "General": 2.5
}

def get_macro_benchmarks() -> Dict[str, Any]:
    return {
        "benchmark_fed_funds_rate_pct": 5.25,
        "prime_rate_pct": 8.50,
        "cpi_inflation_yoy_pct": 3.1,
        "national_unemployment_pct": 4.0,
        "sector_default_rates": SECTOR_DEFAULT_BENCHMARKS
    }


# --- Ratio Calculation Engine ---

def calculate_ratios(applicant: ApplicantProfile) -> CalculatedRatios:
    income = max(applicant.monthly_gross_income, 1.0)
    total_monthly_debt = applicant.existing_monthly_debt + applicant.proposed_loan_payment
    
    front_end_dti = (applicant.proposed_loan_payment / income) * 100.0
    back_end_dti = (total_monthly_debt / income) * 100.0
    
    limit = max(applicant.total_credit_limit, 1.0)
    utilization = (applicant.revolving_credit_balance / limit) * 100.0
    
    pti = (applicant.proposed_loan_payment / income) * 100.0
    
    liquidity_coverage = applicant.liquid_assets / max(total_monthly_debt, 1.0)
    residual_income = income - total_monthly_debt
    
    return CalculatedRatios(
        front_end_dti_pct=round(front_end_dti, 2),
        back_end_dti_pct=round(back_end_dti, 2),
        credit_utilization_pct=round(utilization, 2),
        payment_to_income_pct=round(pti, 2),
        liquidity_coverage_months=round(liquidity_coverage, 2),
        residual_income_monthly=round(residual_income, 2)
    )


# --- Risk Factor Synthesizer ---

def synthesize_risk_factors(
    applicant: ApplicantProfile, 
    ratios: CalculatedRatios, 
    macro: MacroIndicators
) -> List[RiskFactor]:
    factors: List[RiskFactor] = []
    
    # 1. Back-End DTI Evaluation
    if ratios.back_end_dti_pct <= 36.0:
        factors.append(RiskFactor(
            category="LEVERAGE",
            factor_type="POSITIVE_MITIGANT",
            severity="LOW",
            title="Conservative Debt-to-Income (DTI)",
            description=f"Total debt-to-income ratio of {ratios.back_end_dti_pct}% is comfortably within standard conforming guidelines (<=36%)."
        ))
    elif ratios.back_end_dti_pct <= 43.0:
        factors.append(RiskFactor(
            category="LEVERAGE",
            factor_type="NEUTRAL",
            severity="MEDIUM",
            title="Moderate Debt-to-Income (DTI)",
            description=f"Total debt-to-income ratio of {ratios.back_end_dti_pct}% sits in the standard qualified-mortgage band (36%-43%)."
        ))
    else:
        factors.append(RiskFactor(
            category="LEVERAGE",
            factor_type="ELEVATED_RISK",
            severity="HIGH" if ratios.back_end_dti_pct > 50.0 else "MEDIUM",
            title="Elevated Leverage Burden",
            description=f"Total debt-to-income ratio of {ratios.back_end_dti_pct}% exceeds typical conforming limits (>43%), reducing discretionary debt service capacity."
        ))
        
    # 2. Revolving Credit Utilization Evaluation
    if ratios.credit_utilization_pct <= 30.0:
        factors.append(RiskFactor(
            category="CREDIT_CAPACITY",
            factor_type="POSITIVE_MITIGANT",
            severity="LOW",
            title="Low Revolving Credit Utilization",
            description=f"Revolving balance utilization of {ratios.credit_utilization_pct}% demonstrates disciplined credit line management and substantial available liquidity."
        ))
    elif ratios.credit_utilization_pct <= 60.0:
        factors.append(RiskFactor(
            category="CREDIT_CAPACITY",
            factor_type="NEUTRAL",
            severity="MEDIUM",
            title="Moderate Revolving Utilization",
            description=f"Credit utilization is {ratios.credit_utilization_pct}%, indicating active revolving line reliance without acute credit exhaustion."
        ))
    else:
        factors.append(RiskFactor(
            category="CREDIT_CAPACITY",
            factor_type="ELEVATED_RISK",
            severity="HIGH" if ratios.credit_utilization_pct > 80.0 else "MEDIUM",
            title="High Revolving Credit Utilization",
            description=f"Credit line utilization at {ratios.credit_utilization_pct}% indicates heavy reliance on revolving credit and limited short-term borrowing buffer."
        ))
        
    # 3. Liquidity Coverage / Emergency Cushion
    if ratios.liquidity_coverage_months >= 6.0:
        factors.append(RiskFactor(
            category="LIQUIDITY",
            factor_type="POSITIVE_MITIGANT",
            severity="LOW",
            title="Substantial Liquidity Reserves",
            description=f"Verified liquid assets (${applicant.liquid_assets:,.0f}) provide {ratios.liquidity_coverage_months:.1f} months of total post-closing debt obligations."
        ))
    elif ratios.liquidity_coverage_months >= 2.0:
        factors.append(RiskFactor(
            category="LIQUIDITY",
            factor_type="NEUTRAL",
            severity="MEDIUM",
            title="Adequate Liquidity Cushion",
            description=f"Liquid reserves cover {ratios.liquidity_coverage_months:.1f} months of ongoing debt obligations."
        ))
    else:
        factors.append(RiskFactor(
            category="LIQUIDITY",
            factor_type="ELEVATED_RISK",
            severity="HIGH",
            title="Thin Post-Closing Liquidity",
            description=f"Liquid assets cover only {ratios.liquidity_coverage_months:.1f} months of total monthly debt service, leaving limited margin for income shocks."
        ))
        
    # 4. Employment & Sector Stability
    if applicant.employment_duration_years >= 3.0:
        factors.append(RiskFactor(
            category="STABILITY",
            factor_type="POSITIVE_MITIGANT",
            severity="LOW",
            title="Established Employment Tenure",
            description=f"{applicant.employment_duration_years:.1f} years of tenure in {applicant.industry_sector} demonstrates consistent income continuity."
        ))
    elif applicant.employment_duration_years < 1.0:
        factors.append(RiskFactor(
            category="STABILITY",
            factor_type="ELEVATED_RISK",
            severity="MEDIUM",
            title="Short Employment Tenure",
            description=f"Current tenure of {applicant.employment_duration_years:.1f} years (<1 year) introduces income transition sensitivity."
        ))
        
    # 5. Macroeconomic Environment Cross-Referencing
    if macro.sector_default_rate_pct >= 3.5:
        factors.append(RiskFactor(
            category="MACRO_PRESSURE",
            factor_type="ELEVATED_RISK",
            severity="HIGH" if macro.sector_default_rate_pct > 4.5 else "MEDIUM",
            title=f"Elevated {applicant.industry_sector} Sector Default Rate",
            description=f"Applicant's industry ({applicant.industry_sector}) exhibits an annualized default/delinquency rate of {macro.sector_default_rate_pct}%, above the national average (2.5%)."
        ))
    else:
        factors.append(RiskFactor(
            category="MACRO_PRESSURE",
            factor_type="POSITIVE_MITIGANT",
            severity="LOW",
            title=f"Resilient {applicant.industry_sector} Industry Sector",
            description=f"{applicant.industry_sector} sector default rate is low at {macro.sector_default_rate_pct}%, reflecting stable sectoral cash flows."
        ))
        
    if macro.benchmark_fed_funds_rate_pct >= 5.0 and ratios.back_end_dti_pct > 40.0:
        factors.append(RiskFactor(
            category="MACRO_PRESSURE",
            factor_type="ELEVATED_RISK",
            severity="MEDIUM",
            title="High Interest Rate Sensitivity",
            description=f"In a high benchmark rate environment ({macro.benchmark_fed_funds_rate_pct}%), combined with elevated DTI ({ratios.back_end_dti_pct}%), variable debt or debt rollover poses refinancing headwind."
        ))
        
    return factors


# --- Underwriter Narrative Synthesizer ---

def generate_underwriter_narrative(
    applicant: ApplicantProfile, 
    ratios: CalculatedRatios, 
    macro: MacroIndicators,
    factors: List[RiskFactor]
) -> str:
    positives = [f.title for f in factors if f.factor_type == "POSITIVE_MITIGANT"]
    elevated = [f.title for f in factors if f.factor_type == "ELEVATED_RISK"]
    
    lines = []
    lines.append(
        f"Applicant {applicant.applicant_name} presents a monthly gross income of ${applicant.monthly_gross_income:,.2f} "
        f"against ${applicant.existing_monthly_debt + applicant.proposed_loan_payment:,.2f} in total post-closing debt obligations, "
        f"yielding a back-end DTI of {ratios.back_end_dti_pct}% and residual monthly income of ${ratios.residual_income_monthly:,.2f}."
    )
    
    if positives:
        lines.append(f"Key Compensating Factors & Mitigants: {'; '.join(positives)}.")
    if elevated:
        lines.append(f"Noted Risk Factors & Sensitivities: {'; '.join(elevated)}.")
        
    lines.append(
        f"Macro Context: Operating in {applicant.industry_sector} (sector default baseline: {macro.sector_default_rate_pct}%) "
        f"under a {macro.benchmark_fed_funds_rate_pct}% policy rate environment."
    )
    
    return " ".join(lines)


# --- Main Triage Evaluation Function ---

def evaluate_credit_risk(
    applicant: ApplicantProfile, 
    macro: Optional[MacroIndicators] = None
) -> RiskFactorSummary:
    if macro is None:
        sector_default = SECTOR_DEFAULT_BENCHMARKS.get(applicant.industry_sector, 2.5)
        macro = MacroIndicators(
            benchmark_fed_funds_rate_pct=5.25,
            sector_default_rate_pct=sector_default,
            cpi_inflation_yoy_pct=3.1,
            regional_unemployment_pct=3.9
        )
        
    ratios = calculate_ratios(applicant)
    factors = synthesize_risk_factors(applicant, ratios, macro)
    narrative = generate_underwriter_narrative(applicant, ratios, macro, factors)
    
    eval_id = str(uuid.uuid4())
    evaluated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    summary = RiskFactorSummary(
        applicant_id=applicant.applicant_id,
        applicant_name=applicant.applicant_name,
        evaluated_at=evaluated_at,
        ratios=ratios,
        macro_context=macro,
        risk_factors=factors,
        underwriter_narrative=narrative,
        audit_id=eval_id
    )
    
    # Audit log entry (Constitution Rule #4: write before use)
    log_audit(
        execution_id=eval_id,
        node_name="credit_risk_triage",
        action_type="credit_risk_evaluation",
        record_type="credit_triage",
        payload=applicant.model_dump(),
        result=summary.model_dump()
    )
    
    return summary


# --- Sample Presets for Underwriter Demonstrations ---

def get_preset_applicants() -> List[Dict[str, Any]]:
    return [
        {
            "id": "preset_prime",
            "name": "Jane Doe (Prime Tier Homebuyer)",
            "archetype": "Low Leverage, High Liquidity, Stable Healthcare Sector",
            "profile": {
                "applicant_id": "APP-PRIME-001",
                "applicant_name": "Jane Doe",
                "monthly_gross_income": 12500.0,
                "existing_monthly_debt": 1400.0,
                "proposed_loan_payment": 1600.0,
                "revolving_credit_balance": 2400.0,
                "total_credit_limit": 25000.0,
                "liquid_assets": 65000.0,
                "employment_duration_years": 6.5,
                "industry_sector": "Healthcare",
                "stated_loan_purpose": "Primary Residence Mortgage"
            }
        },
        {
            "id": "preset_stretched",
            "name": "Marcus Vance (Stretched Small Business Owner)",
            "archetype": "High DTI, Elevated Revolving Utilization, Retail Headwinds",
            "profile": {
                "applicant_id": "APP-STR-002",
                "applicant_name": "Marcus Vance",
                "monthly_gross_income": 7200.0,
                "existing_monthly_debt": 2700.0,
                "proposed_loan_payment": 1100.0,
                "revolving_credit_balance": 18500.0,
                "total_credit_limit": 22000.0,
                "liquid_assets": 4500.0,
                "employment_duration_years": 2.0,
                "industry_sector": "Retail & Consumer",
                "stated_loan_purpose": "Commercial Equipment Refinancing"
            }
        },
        {
            "id": "preset_high_liquidity_professional",
            "name": "Dr. Sarah Chen (High-DTI / High-Liquidity Professional)",
            "archetype": "High Income & Mortgage DTI, but Massive Liquid Cushion ($220k)",
            "profile": {
                "applicant_id": "APP-HLQ-003",
                "applicant_name": "Dr. Sarah Chen",
                "monthly_gross_income": 22000.0,
                "existing_monthly_debt": 4800.0,
                "proposed_loan_payment": 5800.0,
                "revolving_credit_balance": 9000.0,
                "total_credit_limit": 50000.0,
                "liquid_assets": 220000.0,
                "employment_duration_years": 8.0,
                "industry_sector": "Biotech / Pharma",
                "stated_loan_purpose": "Jumbo Residential Facility"
            }
        },
        {
            "id": "preset_cre_contractor",
            "name": "David Miller (Commercial Real Estate Contractor)",
            "archetype": "Moderate DTI, Macro Sensitivity to Rising Rates & CRE Stress",
            "profile": {
                "applicant_id": "APP-CRE-004",
                "applicant_name": "David Miller",
                "monthly_gross_income": 9500.0,
                "existing_monthly_debt": 2900.0,
                "proposed_loan_payment": 1400.0,
                "revolving_credit_balance": 14000.0,
                "total_credit_limit": 26000.0,
                "liquid_assets": 19000.0,
                "employment_duration_years": 4.2,
                "industry_sector": "Commercial Real Estate",
                "stated_loan_purpose": "Working Capital Credit Line"
            }
        }
    ]
