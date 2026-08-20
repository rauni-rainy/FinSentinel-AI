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

class AdverseActionFactor(BaseModel):
    """
    FCRA 615(a) & ECOA Reg B Principal Contributing Factor.
    Surfaces the top ranked risk elements for human underwriters
    when completing statutory adverse action or conditioning notices.
    """
    factor_code: str = Field(description="Standardized factor code, e.g. FCRA-DTI-01")
    rank: int = Field(description="Principal ranking 1 to 4")
    title: str = Field(description="Factor title for regulatory disclosure")
    metric_observed: str = Field(description="Observed value vs benchmark")
    statutory_context: str = Field(description="ECOA / FCRA disclosure explanation")

class StressScenarioInput(BaseModel):
    scenario_name: str = Field(default="Custom Shock")
    rate_shock_bps: float = Field(default=200.0, description="Interest rate increase in basis points (200 = +2.00%)")
    income_haircut_pct: float = Field(default=10.0, description="Income reduction percentage (10 = -10%)")
    inflation_expense_shock_pct: float = Field(default=5.0, description="Living/debt expense escalation (%)")

class StressScenarioOutput(BaseModel):
    scenario_name: str
    rate_shock_bps: float
    income_haircut_pct: float
    inflation_expense_shock_pct: float
    stressed_monthly_income: float
    stressed_monthly_debt: float
    stressed_front_end_dti_pct: float
    stressed_back_end_dti_pct: float
    stressed_residual_income: float
    stressed_liquidity_coverage_months: float
    resilience_classification: str = Field(description="Telemetry band: HIGH_BUFFER, MODERATE_SENSITIVITY, or ACUTE_STRESS")

class RiskFactorSummary(BaseModel):
    """
    STRUCTURAL ENFORCEMENT:
    Contains calculated ratios, macroeconomic context, categorized risk factors,
    stress sensitivity scenarios, adverse action codes, and plain-language narrative.
    Contains ZERO decision, recommendation, or approval fields.
    """
    applicant_id: str
    applicant_name: str
    evaluated_at: str
    ratios: CalculatedRatios
    macro_context: MacroIndicators
    risk_factors: List[RiskFactor]
    adverse_action_factors: List[AdverseActionFactor] = Field(default_factory=list)
    stress_scenarios: List[StressScenarioOutput] = Field(default_factory=list)
    underwriter_narrative: str
    audit_id: Optional[str] = None
    disclaimer: str = Field(
        default="DECISION SUPPORT ONLY — NOT AN AUTONOMOUS DECISION. This summary surfaces objective financial ratios, stress telemetry, and risk factors for a human underwriter. Final credit authority resides exclusively with licensed human underwriters."
    )

class MemoRequest(BaseModel):
    applicant: ApplicantProfile
    underwriter_name: str = Field(default="Licensed Credit Underwriter")
    underwriter_notes: str = Field(default="")
    checklist_verifications: Dict[str, bool] = Field(default_factory=dict)

class UnderwriterCreditMemo(BaseModel):
    memo_id: str
    generated_at: str
    applicant_id: str
    applicant_name: str
    underwriter_name: str
    audit_id: str
    formatted_markdown: str
    disclaimer: str


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
    "Biotech / Pharma": 1.7,
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


# --- Stress-Testing & Sensitivity Simulation Engine ---

def calculate_stress_scenario(
    applicant: ApplicantProfile, 
    scenario: StressScenarioInput
) -> StressScenarioOutput:
    """
    Computes mathematical impact of interest rate hike, income haircut, and expense shock.
    """
    stressed_income = max(applicant.monthly_gross_income * (1.0 - (scenario.income_haircut_pct / 100.0)), 1.0)
    
    # 1. Variable debt interest escalation (revolving balances)
    annual_rate_shock_factor = scenario.rate_shock_bps / 10000.0
    monthly_revolving_interest_increase = (applicant.revolving_credit_balance * annual_rate_shock_factor) / 12.0
    
    # 2. Proposed payment interest adjustment
    proposed_payment_shock = applicant.proposed_loan_payment * (1.0 + (annual_rate_shock_factor * 0.4))
    
    # 3. Existing debt cost escalation (inflation on living/service debt)
    existing_debt_shocked = applicant.existing_monthly_debt * (1.0 + (scenario.inflation_expense_shock_pct / 100.0))
    
    stressed_total_debt = existing_debt_shocked + proposed_payment_shock + monthly_revolving_interest_increase
    
    stressed_front_end = (proposed_payment_shock / stressed_income) * 100.0
    stressed_back_end = (stressed_total_debt / stressed_income) * 100.0
    stressed_residual = stressed_income - stressed_total_debt
    stressed_liquidity = applicant.liquid_assets / max(stressed_total_debt, 1.0)
    
    # Telemetry classification
    if stressed_back_end <= 43.0 and stressed_liquidity >= 3.0:
        classification = "HIGH_BUFFER"
    elif stressed_back_end <= 52.0 and stressed_liquidity >= 1.5:
        classification = "MODERATE_SENSITIVITY"
    else:
        classification = "ACUTE_STRESS"
        
    return StressScenarioOutput(
        scenario_name=scenario.scenario_name,
        rate_shock_bps=scenario.rate_shock_bps,
        income_haircut_pct=scenario.income_haircut_pct,
        inflation_expense_shock_pct=scenario.inflation_expense_shock_pct,
        stressed_monthly_income=round(stressed_income, 2),
        stressed_monthly_debt=round(stressed_total_debt, 2),
        stressed_front_end_dti_pct=round(stressed_front_end, 2),
        stressed_back_end_dti_pct=round(stressed_back_end, 2),
        stressed_residual_income=round(stressed_residual, 2),
        stressed_liquidity_coverage_months=round(stressed_liquidity, 2),
        resilience_classification=classification
    )

def generate_default_stress_matrix(applicant: ApplicantProfile) -> List[StressScenarioOutput]:
    scenarios = [
        StressScenarioInput(
            scenario_name="Baseline (Current Economic Conditions)",
            rate_shock_bps=0.0,
            income_haircut_pct=0.0,
            inflation_expense_shock_pct=0.0
        ),
        StressScenarioInput(
            scenario_name="Moderate Rate Hike (+150 bps Fed Shock)",
            rate_shock_bps=150.0,
            income_haircut_pct=0.0,
            inflation_expense_shock_pct=3.0
        ),
        StressScenarioInput(
            scenario_name="Severe Stagflation (+300 bps / -12% Income)",
            rate_shock_bps=300.0,
            income_haircut_pct=12.0,
            inflation_expense_shock_pct=6.0
        ),
        StressScenarioInput(
            scenario_name="Income Disruption Shock (-20% Income)",
            rate_shock_bps=50.0,
            income_haircut_pct=20.0,
            inflation_expense_shock_pct=4.0
        )
    ]
    return [calculate_stress_scenario(applicant, s) for s in scenarios]


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


# --- FCRA / ECOA Principal Adverse Action Factor Extractor ---

def extract_adverse_action_factors(
    applicant: ApplicantProfile,
    ratios: CalculatedRatios, 
    macro: MacroIndicators, 
    factors: List[RiskFactor]
) -> List[AdverseActionFactor]:
    """
    Ranks the top principal risk factors (up to 4) under FCRA 615(a) / ECOA Reg B
    guidelines for human underwriter reference during adverse action notice completion.
    """
    candidates = []
    
    # 1. Back-end DTI
    if ratios.back_end_dti_pct > 36.0:
        severity_score = (ratios.back_end_dti_pct - 36.0) * 2.0
        candidates.append((
            severity_score,
            AdverseActionFactor(
                factor_code="FCRA-DTI-01",
                rank=0,
                title="Debt Obligations Relative to Income",
                metric_observed=f"Back-End DTI is {ratios.back_end_dti_pct:.1f}% (Guideline threshold: 36.0%-43.0%)",
                statutory_context="Total monthly debt payments exceed conforming income capacity guidelines."
            )
        ))
        
    # 2. Revolving Credit Utilization
    if ratios.credit_utilization_pct > 30.0:
        severity_score = (ratios.credit_utilization_pct - 30.0) * 1.5
        candidates.append((
            severity_score,
            AdverseActionFactor(
                factor_code="FCRA-UTIL-02",
                rank=0,
                title="Proportion of Balances to Total Available Credit Lines",
                metric_observed=f"Credit utilization is {ratios.credit_utilization_pct:.1f}% on ${applicant.total_credit_limit:,.0f} limit",
                statutory_context="Elevated revolving balance concentration reduces short-term liquidity reserves."
            )
        ))
        
    # 3. Post-Closing Liquid Asset Reserves
    if ratios.liquidity_coverage_months < 6.0:
        severity_score = (6.0 - ratios.liquidity_coverage_months) * 10.0
        candidates.append((
            severity_score,
            AdverseActionFactor(
                factor_code="FCRA-LIQ-03",
                rank=0,
                title="Insufficient Post-Closing Liquid Asset Reserves",
                metric_observed=f"Liquid reserves cover {ratios.liquidity_coverage_months:.1f} months of debt (Benchmark: 6.0 months)",
                statutory_context="Available liquid assets provide narrow contingency buffer against unexpected cash flow interruptions."
            )
        ))
        
    # 4. Employment Tenure
    if applicant.employment_duration_years < 2.0:
        severity_score = (2.0 - applicant.employment_duration_years) * 15.0
        candidates.append((
            severity_score,
            AdverseActionFactor(
                factor_code="FCRA-STAB-04",
                rank=0,
                title="Limited Current Employment or Industry Tenure",
                metric_observed=f"Tenure is {applicant.employment_duration_years:.1f} years in {applicant.industry_sector} (Benchmark: >=2.0 years)",
                statutory_context="Short time in current position or industry introduces income continuity variance."
            )
        ))
        
    # 5. Sector Default Rate
    if macro.sector_default_rate_pct > 3.0:
        severity_score = (macro.sector_default_rate_pct - 3.0) * 8.0
        candidates.append((
            severity_score,
            AdverseActionFactor(
                factor_code="FCRA-SECTOR-05",
                rank=0,
                title="Elevated Sector Default Rate in Applicant Industry",
                metric_observed=f"Sector default benchmark is {macro.sector_default_rate_pct:.1f}% in {applicant.industry_sector} (Natl Avg: 2.5%)",
                statutory_context="Macroeconomic headwinds and historical default rates in the borrower's industry sector."
            )
        ))
        
    # Sort candidates by severity score descending and take top 4
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_factors = []
    for rank, (_, factor) in enumerate(candidates[:4], start=1):
        factor.rank = rank
        top_factors.append(factor)
        
    return top_factors


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
    stress_scenarios = generate_default_stress_matrix(applicant)
    adverse_action_factors = extract_adverse_action_factors(applicant, ratios, macro, factors)
    
    eval_id = str(uuid.uuid4())
    evaluated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    summary = RiskFactorSummary(
        applicant_id=applicant.applicant_id,
        applicant_name=applicant.applicant_name,
        evaluated_at=evaluated_at,
        ratios=ratios,
        macro_context=macro,
        risk_factors=factors,
        adverse_action_factors=adverse_action_factors,
        stress_scenarios=stress_scenarios,
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


# --- Underwriter Credit Memorandum Generator ---

def generate_credit_memo(
    applicant: ApplicantProfile,
    summary: RiskFactorSummary,
    underwriter_name: str,
    underwriter_notes: str,
    checklist_verifications: Dict[str, bool]
) -> UnderwriterCreditMemo:
    memo_id = f"MEMO-{uuid.uuid4().hex[:8].upper()}"
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    checklist_md = "\n".join([
        f"- [{'x' if v else ' '}] **{k.replace('_', ' ').title()} Verified**"
        for k, v in checklist_verifications.items()
    ]) if checklist_verifications else "- [x] Standard underwriting pre-screening verified"
    
    stress_table_md = "\n".join([
        f"| {s.scenario_name} | ${s.stressed_monthly_income:,.0f} | ${s.stressed_monthly_debt:,.0f} | {s.stressed_back_end_dti_pct:.1f}% | ${s.stressed_residual_income:,.0f} | {s.stressed_liquidity_coverage_months:.1f} mos | `{s.resilience_classification}` |"
        for s in summary.stress_scenarios
    ])
    
    adverse_md = "\n".join([
        f"{idx}. **[{f.factor_code}] {f.title}**: {f.metric_observed}. *({f.statutory_context})*"
        for idx, f in enumerate(summary.adverse_action_factors, 1)
    ]) if summary.adverse_action_factors else "None noted (Standard prime parameters observed)."
    
    markdown_content = f"""# FinSentinel AI — Institutional Underwriter Credit Memorandum
**Document ID:** `{memo_id}` | **Audit Ref:** `{summary.audit_id}`  
**Evaluation Date:** `{generated_at}` | **Human Underwriter:** `{underwriter_name}`

---

### 1. Executive Summary & Facility Purpose
- **Applicant:** {applicant.applicant_name} (`{applicant.applicant_id}`)
- **Industry Sector:** {applicant.industry_sector} ({applicant.employment_duration_years:.1f} yrs tenure)
- **Stated Facility Purpose:** {applicant.stated_loan_purpose}
- **Proposed Installment Payment:** ${applicant.proposed_loan_payment:,.2f} / month

---

### 2. Verified Financial Telemetry & Key Ratios
| Ratio Metric | Calculated Value | Institutional Benchmark Band | Observed Variance |
| :--- | :--- | :--- | :--- |
| **Front-End DTI** | {summary.ratios.front_end_dti_pct:.1f}% | <= 28.0% | {'Within guidelines' if summary.ratios.front_end_dti_pct <= 28 else 'Elevated'} |
| **Back-End DTI** | {summary.ratios.back_end_dti_pct:.1f}% | <= 43.0% | {'Conforming' if summary.ratios.back_end_dti_pct <= 43 else 'Stretched'} |
| **Revolving Utilization** | {summary.ratios.credit_utilization_pct:.1f}% | <= 30.0% | {'Controlled' if summary.ratios.credit_utilization_pct <= 30 else 'High line usage'} |
| **Liquidity Coverage** | {summary.ratios.liquidity_coverage_months:.1f} months | >= 6.0 months | {'Strong cushion' if summary.ratios.liquidity_coverage_months >= 6 else 'Thin reserve margin'} |
| **Residual Cash Flow** | ${summary.ratios.residual_income_monthly:,.2f} | Positive discretionary | Post-debt margin |

---

### 3. Macro Stress-Testing & Sensitivity Simulation
| Scenario Name | Stressed Income | Stressed Debt | Stressed DTI | Stressed Residual | Liquidity Buffer | Telemetry Band |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
{stress_table_md}

---

### 4. FCRA 615(a) / ECOA Reg B Principal Adverse Action Factors
*(Surfaced for human underwriter reference if adverse action or conditioning is required)*
{adverse_md}

---

### 5. Human Underwriter Verification Checklist & Conditions
{checklist_md}

**Human Underwriter Manual Notes & Rationale:**
> {underwriter_notes if underwriter_notes.strip() else "No manual underwriter commentary entered."}

---

### 6. Institutional Compliance & Regulatory Disclaimer
> **NOTICE:** {summary.disclaimer}
"""

    return UnderwriterCreditMemo(
        memo_id=memo_id,
        generated_at=generated_at,
        applicant_id=applicant.applicant_id,
        applicant_name=applicant.applicant_name,
        underwriter_name=underwriter_name,
        audit_id=summary.audit_id or "AUDIT-PENDING",
        formatted_markdown=markdown_content,
        disclaimer=summary.disclaimer
    )


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
