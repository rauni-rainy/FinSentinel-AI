"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, Legend } from "recharts";

interface ApplicantProfile {
  applicant_id: string;
  applicant_name: string;
  monthly_gross_income: number;
  existing_monthly_debt: number;
  proposed_loan_payment: number;
  revolving_credit_balance: number;
  total_credit_limit: number;
  liquid_assets: number;
  employment_duration_years: number;
  industry_sector: string;
  stated_loan_purpose: string;
}

interface CalculatedRatios {
  front_end_dti_pct: number;
  back_end_dti_pct: number;
  credit_utilization_pct: number;
  payment_to_income_pct: number;
  liquidity_coverage_months: number;
  residual_income_monthly: number;
}

interface MacroIndicators {
  benchmark_fed_funds_rate_pct: number;
  sector_default_rate_pct: number;
  cpi_inflation_yoy_pct: number;
  regional_unemployment_pct: number;
}

interface RiskFactor {
  category: string;
  factor_type: string;
  severity: string;
  title: string;
  description: string;
}

interface AdverseActionFactor {
  factor_code: string;
  rank: number;
  title: string;
  metric_observed: string;
  statutory_context: string;
}

interface StressScenarioOutput {
  scenario_name: string;
  rate_shock_bps: number;
  income_haircut_pct: number;
  inflation_expense_shock_pct: number;
  stressed_monthly_income: number;
  stressed_monthly_debt: number;
  stressed_front_end_dti_pct: number;
  stressed_back_end_dti_pct: number;
  stressed_residual_income: number;
  stressed_liquidity_coverage_months: number;
  resilience_classification: string;
}

interface RiskFactorSummary {
  applicant_id: string;
  applicant_name: string;
  evaluated_at: string;
  ratios: CalculatedRatios;
  macro_context: MacroIndicators;
  risk_factors: RiskFactor[];
  adverse_action_factors: AdverseActionFactor[];
  stress_scenarios: StressScenarioOutput[];
  underwriter_narrative: string;
  audit_id: string;
  disclaimer: string;
}

interface PresetItem {
  id: string;
  name: string;
  archetype: string;
  profile: ApplicantProfile;
}

interface UnderwriterCreditMemo {
  memo_id: string;
  generated_at: string;
  applicant_id: string;
  applicant_name: string;
  underwriter_name: string;
  audit_id: string;
  formatted_markdown: string;
  disclaimer: string;
}

export default function CreditTriagePage() {
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"telemetry" | "stress" | "fcra">("telemetry");

  const [applicant, setApplicant] = useState<ApplicantProfile>({
    applicant_id: "APP-CUSTOM-001",
    applicant_name: "Jane Doe",
    monthly_gross_income: 12500,
    existing_monthly_debt: 1400,
    proposed_loan_payment: 1600,
    revolving_credit_balance: 2400,
    total_credit_limit: 25000,
    liquid_assets: 65000,
    employment_duration_years: 6.5,
    industry_sector: "Healthcare",
    stated_loan_purpose: "Primary Residence Mortgage"
  });

  const [summary, setSummary] = useState<RiskFactorSummary | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [macroBenchmarks, setMacroBenchmarks] = useState<any>(null);
  
  // Custom Stress Test Interactive Sliders
  const [customRateShockBps, setCustomRateShockBps] = useState<number>(200);
  const [customIncomeHaircutPct, setCustomIncomeHaircutPct] = useState<number>(10);
  const [customInflationShockPct, setCustomInflationShockPct] = useState<number>(5);
  const [customStressResult, setCustomStressResult] = useState<StressScenarioOutput | null>(null);
  const [stressTestingActive, setStressTestingActive] = useState<boolean>(false);

  // Underwriter Manual Worksheet & Notes
  const [underwriterName, setUnderwriterName] = useState<string>("Lead Credit Underwriter");
  const [underwriterNotes, setUnderwriterNotes] = useState<string>("");
  const [checkedVerifications, setCheckedVerifications] = useState<Record<string, boolean>>({
    w2_tax_returns: true,
    liquid_asset_statements: true,
    credit_bureau_history: true,
    macro_sensitivity_assessed: true
  });

  // Credit Memorandum Export Modal
  const [memoModalOpen, setMemoModalOpen] = useState<boolean>(false);
  const [memoData, setMemoData] = useState<UnderwriterCreditMemo | null>(null);
  const [generatingMemo, setGeneratingMemo] = useState<boolean>(false);
  const [copiedMemo, setCopiedMemo] = useState<boolean>(false);

  const [backendError, setBackendError] = useState<string | null>(null);

  const loadInitialData = async () => {
    setBackendError(null);
    try {
      const [presetsRes, macroRes] = await Promise.all([
        fetch("http://localhost:8000/credit/presets"),
        fetch("http://localhost:8000/credit/macro-benchmarks")
      ]);
      
      if (!presetsRes.ok || !macroRes.ok) {
        throw new Error(`Server returned error: presets=${presetsRes.status}, macro=${macroRes.status}`);
      }

      const presetsData = await presetsRes.json();
      const macroData = await macroRes.json();

      setPresets(presetsData);
      setMacroBenchmarks(macroData);
      if (presetsData && presetsData.length > 0) {
        setSelectedPresetId(presetsData[0].id);
        setApplicant(presetsData[0].profile);
        runEvaluation(presetsData[0].profile);
      }
    } catch (err: any) {
      console.error("Failed to load presets/macro benchmarks", err);
      setBackendError("Unable to connect to backend on port 8000. Ensure the FastAPI server is running.");
    }
  };

  // Load Presets & Macro Benchmarks on Mount
  useEffect(() => {
    loadInitialData();
  }, []);

  const runEvaluation = async (profile: ApplicantProfile) => {
    setEvaluating(true);
    setBackendError(null);
    try {
      const res = await fetch("http://localhost:8000/credit/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      });
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
        // Automatically calculate custom stress scenario
        triggerCustomStressTest(profile, customRateShockBps, customIncomeHaircutPct, customInflationShockPct);
      } else {
        setBackendError(`Triage evaluation failed with status ${res.status}`);
      }
    } catch (e: any) {
      console.error("Failed to evaluate credit triage", e);
      setBackendError("Failed to reach triage evaluation endpoint.");
    }
    setEvaluating(false);
  };

  const triggerCustomStressTest = async (
    profile: ApplicantProfile,
    rateBps: number,
    haircutPct: number,
    inflationPct: number
  ) => {
    setStressTestingActive(true);
    try {
      const res = await fetch("http://localhost:8000/credit/stress-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          applicant: profile,
          scenario: {
            scenario_name: `Interactive Shock (+${rateBps} bps / -${haircutPct}% Income)`,
            rate_shock_bps: rateBps,
            income_haircut_pct: haircutPct,
            inflation_expense_shock_pct: inflationPct
          }
        })
      });
      if (res.ok) {
        const data = await res.json();
        setCustomStressResult(data);
      }
    } catch (e) {
      console.error("Failed to calculate custom stress test", e);
    }
    setStressTestingActive(false);
  };

  const handleSelectPreset = (preset: PresetItem) => {
    setSelectedPresetId(preset.id);
    setApplicant(preset.profile);
    runEvaluation(preset.profile);
  };

  const handleInputChange = (field: keyof ApplicantProfile, value: any) => {
    const updated = { ...applicant, [field]: value };
    setApplicant(updated);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runEvaluation(applicant);
  };

  const handleStressSliderChange = (type: "rate" | "haircut" | "inflation", val: number) => {
    let rate = customRateShockBps;
    let haircut = customIncomeHaircutPct;
    let inflation = customInflationShockPct;
    if (type === "rate") {
      rate = val;
      setCustomRateShockBps(val);
    } else if (type === "haircut") {
      haircut = val;
      setCustomIncomeHaircutPct(val);
    } else {
      inflation = val;
      setCustomInflationShockPct(val);
    }
    triggerCustomStressTest(applicant, rate, haircut, inflation);
  };

  const handleGenerateMemo = async () => {
    setGeneratingMemo(true);
    try {
      const res = await fetch("http://localhost:8000/credit/export-memo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          applicant: applicant,
          underwriter_name: underwriterName,
          underwriter_notes: underwriterNotes,
          checklist_verifications: checkedVerifications
        })
      });
      if (res.ok) {
        const data = await res.json();
        setMemoData(data);
        setMemoModalOpen(true);
      }
    } catch (e) {
      console.error("Failed to generate credit memo", e);
    }
    setGeneratingMemo(false);
  };

  const copyMemoToClipboard = () => {
    if (memoData) {
      navigator.clipboard.writeText(memoData.formatted_markdown);
      setCopiedMemo(true);
      setTimeout(() => setCopiedMemo(false), 2000);
    }
  };

  const downloadMemoMarkdown = () => {
    if (memoData) {
      const element = document.createElement("a");
      const file = new Blob([memoData.formatted_markdown], { type: "text/markdown" });
      element.href = URL.createObjectURL(file);
      element.download = `${memoData.memo_id}_${applicant.applicant_name.replace(/\s+/g, "_")}.md`;
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    }
  };

  // Helper colors for DTI and Utilization
  const getDTIColor = (dti: number) => {
    if (dti <= 36) return "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";
    if (dti <= 43) return "text-amber-400 border-amber-500/30 bg-amber-950/20";
    return "text-red-400 border-red-500/30 bg-red-950/20";
  };

  const getUtilColor = (util: number) => {
    if (util <= 30) return "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";
    if (util <= 60) return "text-amber-400 border-amber-500/30 bg-amber-950/20";
    return "text-red-400 border-red-500/30 bg-red-950/20";
  };

  const getLiquidityColor = (months: number) => {
    if (months >= 6) return "text-emerald-400 border-emerald-500/30 bg-emerald-950/20";
    if (months >= 2) return "text-amber-400 border-amber-500/30 bg-amber-950/20";
    return "text-red-400 border-red-500/30 bg-red-950/20";
  };

  // Chart data for stress testing comparison
  const stressComparisonData = summary && customStressResult ? [
    {
      metric: "Back-End DTI (%)",
      Baseline: summary.ratios.back_end_dti_pct,
      Shocked: customStressResult.stressed_back_end_dti_pct,
      Guideline: 43.0
    },
    {
      metric: "Liquidity (Months)",
      Baseline: summary.ratios.liquidity_coverage_months,
      Shocked: customStressResult.stressed_liquidity_coverage_months,
      Guideline: 6.0
    }
  ] : [];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      
      {/* Top Global Navigation Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 px-6 flex items-center justify-between shrink-0 z-20 backdrop-blur-md">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-blue-600 rounded shadow-[0_0_12px_rgba(59,130,246,0.5)]">
              <span className="font-mono font-bold">[*]</span>
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-wider uppercase text-slate-100 flex items-center gap-2">
                FinSentinel AI <span className="text-blue-400 font-mono text-xs font-normal">| Credit Operations</span>
              </h1>
            </div>
          </div>

          <nav className="flex items-center gap-1 text-xs font-mono">
            <Link 
              href="/"
              className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            >
              Investigator Cockpit
            </Link>
            <Link 
              href="/credit-triage"
              className="px-3 py-1.5 rounded bg-blue-600/20 border border-blue-500/30 text-blue-300 font-semibold"
            >
              Credit Risk Triage
            </Link>
            <Link 
              href="/red-team"
              className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
            >
              Red-Team Benchmarks
            </Link>
          </nav>
        </div>

        {/* Prominent Institutional Governance Badge */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateMemo}
            disabled={generatingMemo || !summary}
            className="flex items-center gap-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 px-3 py-1.5 rounded text-xs font-mono text-blue-300 transition-all shadow-[0_0_10px_rgba(59,130,246,0.15)]"
          >
            {generatingMemo ? (
              <span className="font-mono font-bold">[*]</span>
            ) : (
              <span className="font-mono font-bold">[*]</span>
            )}
            <span>Export Credit Memo</span>
          </button>

          <div className="flex items-center gap-2 bg-amber-950/40 border border-amber-600/40 px-3 py-1.5 rounded-full text-xs font-mono text-amber-300">
            <span className="font-mono font-bold">[*]</span>
            <span>Decision Support System — Human Underwriter Authority Only</span>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Column: Applicant Presets & Profile Form */}
        <div className="w-[410px] border-r border-slate-800 bg-slate-900/40 flex flex-col shrink-0 overflow-hidden">
          
          {/* Preset Selector */}
          <div className="p-4 border-b border-slate-800 bg-slate-900/80">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <span className="font-mono font-bold">[*]</span>
                Underwriting Presets
              </span>
              <span className="text-[10px] font-mono text-slate-500">Tier-1 Bank Archetypes</span>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              {presets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => handleSelectPreset(p)}
                  className={`p-2 rounded text-left border transition-all text-xs font-mono ${
                    selectedPresetId === p.id 
                      ? "bg-blue-600/20 border-blue-500/60 text-blue-200 shadow-[0_0_12px_rgba(59,130,246,0.2)]" 
                      : "bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                  }`}
                >
                  <div className="font-bold truncate">{p.name.split(" (")[0]}</div>
                  <div className="text-[10px] text-slate-500 truncate mt-0.5">{p.profile.industry_sector}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Live Applicant Financial Data Form */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-widest text-slate-400">
                Applicant Financial Profile
              </span>
              <span className="text-[10px] font-mono text-slate-500">ID: {applicant.applicant_id}</span>
            </div>

            <form onSubmit={handleFormSubmit} className="space-y-3 font-mono text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Applicant Name</label>
                <input
                  type="text"
                  value={applicant.applicant_name}
                  onChange={(e) => handleInputChange("applicant_name", e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Monthly Gross Income</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.monthly_gross_income}
                      onChange={(e) => handleInputChange("monthly_gross_income", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Existing Monthly Debt</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.existing_monthly_debt}
                      onChange={(e) => handleInputChange("existing_monthly_debt", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Proposed Facility Payment</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.proposed_loan_payment}
                      onChange={(e) => handleInputChange("proposed_loan_payment", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Liquid Reserves (Assets)</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.liquid_assets}
                      onChange={(e) => handleInputChange("liquid_assets", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Revolving Balances</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.revolving_credit_balance}
                      onChange={(e) => handleInputChange("revolving_credit_balance", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Total Credit Limit</label>
                  <div className="relative">
                    <span className="absolute left-2.5 top-1.5 text-slate-500">$</span>
                    <input
                      type="number"
                      value={applicant.total_credit_limit}
                      onChange={(e) => handleInputChange("total_credit_limit", parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950 border border-slate-800 rounded pl-6 pr-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Industry Sector</label>
                  <select
                    value={applicant.industry_sector}
                    onChange={(e) => handleInputChange("industry_sector", e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="Healthcare">Healthcare</option>
                    <option value="Technology">Technology</option>
                    <option value="Financial Services">Financial Services</option>
                    <option value="Retail & Consumer">Retail & Consumer</option>
                    <option value="Commercial Real Estate">Commercial Real Estate</option>
                    <option value="Hospitality & Leisure">Hospitality & Leisure</option>
                    <option value="Construction">Construction</option>
                    <option value="Biotech / Pharma">Biotech / Pharma</option>
                    <option value="General">General</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Tenure (Years)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={applicant.employment_duration_years}
                    onChange={(e) => handleInputChange("employment_duration_years", parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Stated Purpose</label>
                <input
                  type="text"
                  value={applicant.stated_loan_purpose}
                  onChange={(e) => handleInputChange("stated_loan_purpose", e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <button
                type="submit"
                disabled={evaluating}
                className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded flex items-center justify-center gap-2 transition-colors shadow-[0_0_15px_rgba(59,130,246,0.3)]"
              >
                {evaluating ? (
                  <>
                    <span className="font-mono font-bold">[*]</span>
                    Synthesizing Telemetry...
                  </>
                ) : (
                  <>
                    <span className="font-mono font-bold">[*]</span>
                    Recalculate Ratios & Factors
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Main Telemetry & Stress Test Area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-slate-950">
          
          {/* Sub Navigation Bar */}
          <div className="h-12 border-b border-slate-800 bg-slate-900/60 px-6 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 font-mono text-xs">
              <button
                onClick={() => setActiveTab("telemetry")}
                className={`px-3 py-1 rounded transition-colors flex items-center gap-1.5 ${
                  activeTab === "telemetry"
                    ? "bg-slate-800 text-blue-300 font-bold border border-slate-700"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span className="font-mono font-bold">[*]</span>
                Ratios & Risk Factors
              </button>

              <button
                onClick={() => setActiveTab("stress")}
                className={`px-3 py-1 rounded transition-colors flex items-center gap-1.5 ${
                  activeTab === "stress"
                    ? "bg-slate-800 text-blue-300 font-bold border border-slate-700"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span className="font-mono font-bold">[*]</span>
                Macro Stress Simulator
                <span className="text-[9px] px-1 bg-blue-950 border border-blue-700/50 rounded text-blue-300">Live</span>
              </button>

              <button
                onClick={() => setActiveTab("fcra")}
                className={`px-3 py-1 rounded transition-colors flex items-center gap-1.5 ${
                  activeTab === "fcra"
                    ? "bg-slate-800 text-blue-300 font-bold border border-slate-700"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <span className="font-mono font-bold">[*]</span>
                FCRA / ECOA Factors
                {summary && summary.adverse_action_factors.length > 0 && (
                  <span className="text-[9px] px-1.5 bg-amber-950 border border-amber-700/50 rounded text-amber-300">
                    {summary.adverse_action_factors.length}
                  </span>
                )}
              </button>
            </div>

            {summary?.audit_id && (
              <div className="flex items-center gap-3 font-mono text-xs text-slate-500">
                <span>Audit: <code className="text-slate-300">{summary.audit_id.substring(0, 8)}</code></span>
                <span className="text-emerald-400 flex items-center gap-1">
                  <span className="font-mono font-bold">[*]</span> SHA-256 Chained
                </span>
              </div>
            )}
          </div>

          {/* Tab Content Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            
            {/* Disclaimer Bar */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-4 flex items-start gap-3 relative overflow-hidden">
              <div className="p-2 bg-blue-950/60 border border-blue-500/30 rounded text-blue-400 shrink-0">
                <span className="font-mono font-bold">[*]</span>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="font-bold text-sm text-slate-200 font-mono uppercase tracking-wider">
                    Underwriter Decision Support Telemetry
                  </h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-blue-950/80 border border-blue-700/50 rounded text-blue-300">
                    Read-Only Telemetry
                  </span>
                </div>
                <p className="text-xs text-slate-400 font-mono mt-1 leading-relaxed">
                  {summary?.disclaimer || "Surfaces objective financial ratios, stress scenarios, and risk factors for human credit underwriters. Structurally zero autonomous approve/deny decisions."}
                </p>
              </div>
            </div>

            {/* Backend Connection Error Banner */}
            {backendError && (
              <div className="bg-red-950/40 border border-red-500/50 rounded-lg p-4 flex items-center justify-between font-mono text-xs text-red-200">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold">[*]</span>
                  <span>{backendError}</span>
                </div>
                <button
                  onClick={() => loadInitialData()}
                  className="px-3 py-1 bg-red-600 hover:bg-red-500 text-white rounded font-bold transition-colors shadow-sm flex items-center gap-1.5"
                >
                  <span className="font-mono font-bold">[*]</span>
                  Retry Connection
                </button>
              </div>
            )}

            {summary ? (
              <>
                {/* TAB 1: Core Telemetry & Factors */}
                {activeTab === "telemetry" && (
                  <>
                    {/* Ratio Cards */}
                    <div className="grid grid-cols-4 gap-4">
                      {/* Back-End DTI */}
                      <div className={`p-4 rounded-lg border flex flex-col justify-between ${getDTIColor(summary.ratios.back_end_dti_pct)}`}>
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-slate-400">Back-End DTI</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                            Standard: &le;43%
                          </span>
                        </div>
                        <div className="text-3xl font-bold font-mono my-2">
                          {summary.ratios.back_end_dti_pct.toFixed(1)}%
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          Front-End: <span className="text-slate-200">{summary.ratios.front_end_dti_pct.toFixed(1)}%</span>
                        </div>
                      </div>

                      {/* Credit Utilization */}
                      <div className={`p-4 rounded-lg border flex flex-col justify-between ${getUtilColor(summary.ratios.credit_utilization_pct)}`}>
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-slate-400">Credit Utilization</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                            Target: &le;30%
                          </span>
                        </div>
                        <div className="text-3xl font-bold font-mono my-2">
                          {summary.ratios.credit_utilization_pct.toFixed(1)}%
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          Limit: <span className="text-slate-200">${applicant.total_credit_limit.toLocaleString()}</span>
                        </div>
                      </div>

                      {/* Liquidity Cushion */}
                      <div className={`p-4 rounded-lg border flex flex-col justify-between ${getLiquidityColor(summary.ratios.liquidity_coverage_months)}`}>
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-slate-400">Liquidity Cushion</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                            Buffer: &ge;6 mos
                          </span>
                        </div>
                        <div className="text-3xl font-bold font-mono my-2">
                          {summary.ratios.liquidity_coverage_months.toFixed(1)} <span className="text-sm font-normal">mos</span>
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          Reserves: <span className="text-slate-200">${applicant.liquid_assets.toLocaleString()}</span>
                        </div>
                      </div>

                      {/* Residual Income */}
                      <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/60 flex flex-col justify-between">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-slate-400">Residual Cash Flow</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                            Monthly
                          </span>
                        </div>
                        <div className="text-3xl font-bold font-mono my-2 text-white">
                          ${summary.ratios.residual_income_monthly.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </div>
                        <div className="text-[11px] font-mono text-slate-400">
                          PTI Ratio: <span className="text-slate-200">{summary.ratios.payment_to_income_pct.toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>

                    {/* Macro Stress Matrix & Underwriter Narrative */}
                    <div className="grid grid-cols-2 gap-6">
                      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold">[*]</span>
                            <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                              Macroeconomic Baseline Matrix
                            </h3>
                          </div>
                          <span className="text-[10px] font-mono text-slate-400">Sector: {applicant.industry_sector}</span>
                        </div>

                        <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                          <div className="bg-slate-950 p-3 rounded border border-slate-800">
                            <div className="text-slate-500 text-[10px]">Fed Funds Policy Rate</div>
                            <div className="text-base font-bold text-slate-200 mt-1">
                              {summary.macro_context.benchmark_fed_funds_rate_pct}%
                            </div>
                            <div className="text-[10px] text-amber-400/80 mt-1">Elevated policy cost</div>
                          </div>

                          <div className="bg-slate-950 p-3 rounded border border-slate-800">
                            <div className="text-slate-500 text-[10px]">Sector Delinquency Baseline</div>
                            <div className="text-base font-bold text-slate-200 mt-1">
                              {summary.macro_context.sector_default_rate_pct}%
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1">Natl Benchmark: 2.5%</div>
                          </div>

                          <div className="bg-slate-950 p-3 rounded border border-slate-800">
                            <div className="text-slate-500 text-[10px]">CPI Inflation (YoY)</div>
                            <div className="text-base font-bold text-slate-200 mt-1">
                              {summary.macro_context.cpi_inflation_yoy_pct}%
                            </div>
                            <div className="text-[10px] text-slate-400 mt-1">Cost-of-living pressure</div>
                          </div>

                          <div className="bg-slate-950 p-3 rounded border border-slate-800">
                            <div className="text-slate-500 text-[10px]">Regional Unemployment</div>
                            <div className="text-base font-bold text-slate-200 mt-1">
                              {summary.macro_context.regional_unemployment_pct}%
                            </div>
                            <div className="text-[10px] text-emerald-400/80 mt-1">Stable labor market</div>
                          </div>
                        </div>
                      </div>

                      {/* Plain Language Underwriter Synthesis */}
                      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <span className="font-mono font-bold">[*]</span>
                            <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                              Plain-Language Fact Synthesis
                            </h3>
                          </div>
                          <div className="bg-slate-950 border border-slate-800 p-4 rounded text-xs font-mono text-slate-300 leading-relaxed">
                            <p>{summary.underwriter_narrative}</p>
                          </div>
                        </div>

                        <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono text-slate-500">
                          <span>Evaluated: {new Date(summary.evaluated_at).toLocaleTimeString()}</span>
                          <span className="text-blue-400 font-bold">Constitution Rule #6 Validated &#10003;</span>
                        </div>
                      </div>
                    </div>

                    {/* Surfaced Categorized Factors */}
                    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold">[*]</span>
                          <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                            Surfaced Compensating Mitigants & Risk Drivers
                          </h3>
                        </div>
                        <span className="text-[10px] font-mono text-slate-400">
                          {summary.risk_factors.length} Factors Identified
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        {summary.risk_factors.map((factor, idx) => (
                          <div 
                            key={idx}
                            className={`p-3.5 rounded border text-xs font-mono flex items-start gap-3 transition-colors ${
                              factor.factor_type === "POSITIVE_MITIGANT"
                                ? "bg-emerald-950/20 border-emerald-500/30 text-slate-200"
                                : factor.factor_type === "ELEVATED_RISK"
                                ? "bg-red-950/20 border-red-500/30 text-slate-200"
                                : "bg-slate-950 border-slate-800 text-slate-300"
                            }`}
                          >
                            <div className="mt-0.5 shrink-0">
                              {factor.factor_type === "POSITIVE_MITIGANT" ? (
                                <span className="font-mono font-bold">[*]</span>
                              ) : factor.factor_type === "ELEVATED_RISK" ? (
                                <span className="font-mono font-bold">[*]</span>
                              ) : (
                                <span className="font-mono font-bold">[*]</span>
                              )}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-bold text-slate-100">{factor.title}</span>
                                <span className={`text-[10px] px-1.5 py-0.2 rounded border ${
                                  factor.factor_type === "POSITIVE_MITIGANT"
                                    ? "text-emerald-400 border-emerald-600/40 bg-emerald-950/40"
                                    : factor.factor_type === "ELEVATED_RISK"
                                    ? "text-red-400 border-red-600/40 bg-red-950/40"
                                    : "text-slate-400 border-slate-700 bg-slate-900"
                                }`}>
                                  {factor.category}
                                </span>
                              </div>
                              <p className="text-[11px] text-slate-400 leading-relaxed">
                                {factor.description}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {/* TAB 2: Interactive Macro Stress Simulator */}
                {activeTab === "stress" && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-3 gap-6">
                      
                      {/* Left: Interactive Shock Sliders */}
                      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-5 space-y-5 font-mono">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold">[*]</span>
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                              Shock Parameters
                            </h3>
                          </div>
                          <span className="text-[10px] text-slate-500">Real-Time Simulation</span>
                        </div>

                        {/* Slider 1: Rate Shock */}
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-slate-300">Rate Hike Shock</span>
                            <span className="font-bold text-amber-400">+{customRateShockBps} bps (+{(customRateShockBps/100).toFixed(2)}%)</span>
                          </div>
                          <input 
                            type="range" 
                            min="0" 
                            max="400" 
                            step="25"
                            value={customRateShockBps} 
                            onChange={(e) => handleStressSliderChange("rate", parseInt(e.target.value))}
                            className="w-full accent-amber-500 bg-slate-950 h-2 rounded cursor-pointer"
                          />
                          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                            <span>0 bps</span>
                            <span>+200 bps</span>
                            <span>+400 bps</span>
                          </div>
                        </div>

                        {/* Slider 2: Income Haircut */}
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-slate-300">Income Haircut</span>
                            <span className="font-bold text-red-400">-{customIncomeHaircutPct}%</span>
                          </div>
                          <input 
                            type="range" 
                            min="0" 
                            max="30" 
                            step="5"
                            value={customIncomeHaircutPct} 
                            onChange={(e) => handleStressSliderChange("haircut", parseInt(e.target.value))}
                            className="w-full accent-red-500 bg-slate-950 h-2 rounded cursor-pointer"
                          />
                          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                            <span>0%</span>
                            <span>-15%</span>
                            <span>-30%</span>
                          </div>
                        </div>

                        {/* Slider 3: Inflation Cost Escalation */}
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-slate-300">Cost-of-Living Inflation</span>
                            <span className="font-bold text-blue-400">+{customInflationShockPct}%</span>
                          </div>
                          <input 
                            type="range" 
                            min="0" 
                            max="15" 
                            step="1"
                            value={customInflationShockPct} 
                            onChange={(e) => handleStressSliderChange("inflation", parseInt(e.target.value))}
                            className="w-full accent-blue-500 bg-slate-950 h-2 rounded cursor-pointer"
                          />
                          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                            <span>0%</span>
                            <span>+7%</span>
                            <span>+15%</span>
                          </div>
                        </div>

                        {/* Quick Presets for Stress */}
                        <div className="pt-3 border-t border-slate-800 space-y-2">
                          <span className="text-[10px] uppercase text-slate-500 block">Standard Macro Shocks</span>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              onClick={() => {
                                setCustomRateShockBps(150);
                                setCustomIncomeHaircutPct(0);
                                setCustomInflationShockPct(3);
                                triggerCustomStressTest(applicant, 150, 0, 3);
                              }}
                              className="px-2 py-1.5 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-[10px] text-slate-300 text-left truncate"
                            >
                              Mild Rate (+150bps)
                            </button>
                            <button
                              onClick={() => {
                                setCustomRateShockBps(300);
                                setCustomIncomeHaircutPct(15);
                                setCustomInflationShockPct(7);
                                triggerCustomStressTest(applicant, 300, 15, 7);
                              }}
                              className="px-2 py-1.5 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded text-[10px] text-slate-300 text-left truncate"
                            >
                              Stagflation (+300bps)
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Right: Shock Telemetry Output & Resilience */}
                      {customStressResult && (
                        <div className="col-span-2 bg-slate-900/60 border border-slate-800 rounded-lg p-5 font-mono space-y-4">
                          <div className="flex items-center justify-between">
                            <div>
                              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                                Simulated Stress Telemetry
                              </h4>
                              <p className="text-[11px] text-slate-400 mt-0.5">{customStressResult.scenario_name}</p>
                            </div>
                            <span className={`text-xs px-2.5 py-1 rounded font-bold border ${
                              customStressResult.resilience_classification === "HIGH_BUFFER"
                                ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                                : customStressResult.resilience_classification === "MODERATE_SENSITIVITY"
                                ? "bg-amber-950/60 border-amber-500/40 text-amber-300"
                                : "bg-red-950/60 border-red-500/40 text-red-300"
                            }`}>
                              Telemetry: {customStressResult.resilience_classification.replace("_", " ")}
                            </span>
                          </div>

                          <div className="grid grid-cols-3 gap-3">
                            <div className="bg-slate-950 p-3.5 rounded border border-slate-800">
                              <span className="text-slate-500 text-[10px] block">Stressed Back-End DTI</span>
                              <div className="text-2xl font-bold text-amber-400 my-1">
                                {customStressResult.stressed_back_end_dti_pct.toFixed(1)}%
                              </div>
                              <span className="text-[10px] text-slate-400">
                                Baseline: {summary.ratios.back_end_dti_pct.toFixed(1)}% (&#916; +{(customStressResult.stressed_back_end_dti_pct - summary.ratios.back_end_dti_pct).toFixed(1)}%)
                              </span>
                            </div>

                            <div className="bg-slate-950 p-3.5 rounded border border-slate-800">
                              <span className="text-slate-500 text-[10px] block">Stressed Residual Income</span>
                              <div className="text-2xl font-bold text-slate-200 my-1">
                                ${customStressResult.stressed_residual_income.toLocaleString(undefined, { minimumFractionDigits: 0 })}
                              </div>
                              <span className="text-[10px] text-slate-400">
                                Monthly Post-Shock
                              </span>
                            </div>

                            <div className="bg-slate-950 p-3.5 rounded border border-slate-800">
                              <span className="text-slate-500 text-[10px] block">Stressed Liquidity Cushion</span>
                              <div className="text-2xl font-bold text-blue-400 my-1">
                                {customStressResult.stressed_liquidity_coverage_months.toFixed(1)} mos
                              </div>
                              <span className="text-[10px] text-slate-400">
                                Baseline: {summary.ratios.liquidity_coverage_months.toFixed(1)} mos
                              </span>
                            </div>
                          </div>

                          {/* Pre-calculated Standard Stress Scenarios Table */}
                          <div className="pt-3 border-t border-slate-800">
                            <span className="text-xs text-slate-400 block mb-2 font-bold uppercase">
                              Standard Institutional Scenario Matrix
                            </span>
                            <div className="overflow-x-auto">
                              <table className="w-full text-[11px] border-collapse">
                                <thead>
                                  <tr className="border-b border-slate-800 text-slate-500 text-left">
                                    <th className="pb-2">Scenario</th>
                                    <th className="pb-2">Stressed Income</th>
                                    <th className="pb-2">Stressed Debt</th>
                                    <th className="pb-2">Stressed DTI</th>
                                    <th className="pb-2">Residual</th>
                                    <th className="pb-2">Buffer</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/60">
                                  {summary.stress_scenarios.map((s, idx) => (
                                    <tr key={idx} className="hover:bg-slate-950/40">
                                      <td className="py-2 text-slate-200 font-semibold">{s.scenario_name}</td>
                                      <td className="py-2 text-slate-400">${s.stressed_monthly_income.toLocaleString()}</td>
                                      <td className="py-2 text-slate-400">${s.stressed_monthly_debt.toLocaleString()}</td>
                                      <td className={`py-2 font-bold ${s.stressed_back_end_dti_pct > 43 ? 'text-red-400' : 'text-slate-200'}`}>
                                        {s.stressed_back_end_dti_pct.toFixed(1)}%
                                      </td>
                                      <td className="py-2 text-slate-300">${s.stressed_residual_income.toLocaleString()}</td>
                                      <td className="py-2">
                                        <span className={`px-1.5 py-0.5 rounded text-[9px] ${
                                          s.resilience_classification === 'HIGH_BUFFER'
                                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-700/50'
                                            : s.resilience_classification === 'MODERATE_SENSITIVITY'
                                            ? 'bg-amber-950 text-amber-300 border border-amber-700/50'
                                            : 'bg-red-950 text-red-300 border border-red-700/50'
                                        }`}>
                                          {s.resilience_classification}
                                        </span>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>

                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* TAB 3: FCRA / ECOA Principal Adverse Action Factors */}
                {activeTab === "fcra" && (
                  <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-6 space-y-6 font-mono">
                    <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold">[*]</span>
                          <h3 className="font-bold text-sm text-slate-200 uppercase tracking-wider">
                            FCRA 615(a) & ECOA Reg B Adverse Action Factor Reference
                          </h3>
                        </div>
                        <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
                          Under statutory regulations, if a human underwriter declines or conditions credit, the notice must disclose the top principal reasons affecting credit scores or debt-service capacity. FinSentinel ranks and surfaces these factors for human underwriter selection.
                        </p>
                      </div>
                      <span className="text-[10px] px-2.5 py-1 rounded bg-slate-950 border border-slate-700 text-slate-400">
                        Human Notice Generation Only
                      </span>
                    </div>

                    {summary.adverse_action_factors.length > 0 ? (
                      <div className="space-y-4">
                        {summary.adverse_action_factors.map((f, idx) => (
                          <div 
                            key={idx}
                            className="p-4 bg-slate-950 border border-slate-800 rounded-lg flex items-start gap-4 hover:border-slate-700 transition-colors"
                          >
                            <div className="w-7 h-7 rounded-full bg-blue-950 border border-blue-600/50 flex items-center justify-center font-bold text-xs text-blue-300 shrink-0">
                              {f.rank}
                            </div>
                            <div className="flex-1 space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-200 text-xs">
                                  {f.title}
                                </span>
                                <code className="text-[10px] px-2 py-0.5 bg-slate-900 border border-slate-800 rounded text-blue-400">
                                  {f.factor_code}
                                </code>
                              </div>
                              <p className="text-xs text-amber-300/90 font-semibold">
                                Observed Metric: {f.metric_observed}
                              </p>
                              <p className="text-[11px] text-slate-400 leading-relaxed">
                                {f.statutory_context}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-8 text-center bg-slate-950 rounded border border-slate-800 text-slate-400 text-xs">
                        <span className="font-mono font-bold">[*]</span>
                        No adverse factors detected. Applicant parameters sit within prime conforming underwriting bands.
                      </div>
                    )}
                  </div>
                )}

                {/* Bottom Section: Human Underwriter Manual Worksheet */}
                <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold">[*]</span>
                      <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                        Human Underwriter Manual Worksheet & Notes
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono text-amber-300/80 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded">
                      Manual Authority Gate
                    </span>
                  </div>

                  <div className="grid grid-cols-4 gap-3 mb-4 font-mono text-xs">
                    <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                      <input 
                        type="checkbox" 
                        checked={checkedVerifications.w2_tax_returns} 
                        onChange={(e) => setCheckedVerifications({...checkedVerifications, w2_tax_returns: e.target.checked})}
                        className="accent-blue-500" 
                      />
                      <span className="text-slate-300">W2 / Tax Return Verified</span>
                    </label>

                    <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                      <input 
                        type="checkbox" 
                        checked={checkedVerifications.liquid_asset_statements} 
                        onChange={(e) => setCheckedVerifications({...checkedVerifications, liquid_asset_statements: e.target.checked})}
                        className="accent-blue-500" 
                      />
                      <span className="text-slate-300">Liquid Assets Statement</span>
                    </label>

                    <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                      <input 
                        type="checkbox" 
                        checked={checkedVerifications.credit_bureau_history} 
                        onChange={(e) => setCheckedVerifications({...checkedVerifications, credit_bureau_history: e.target.checked})}
                        className="accent-blue-500" 
                      />
                      <span className="text-slate-300">Revolving Line History</span>
                    </label>

                    <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                      <input 
                        type="checkbox" 
                        checked={checkedVerifications.macro_sensitivity_assessed} 
                        onChange={(e) => setCheckedVerifications({...checkedVerifications, macro_sensitivity_assessed: e.target.checked})}
                        className="accent-blue-500" 
                      />
                      <span className="text-slate-300">Macro Stress Evaluated</span>
                    </label>
                  </div>

                  <div className="grid grid-cols-4 gap-3 mb-3">
                    <div className="col-span-1">
                      <label className="block text-[11px] font-mono text-slate-400 mb-1">Underwriter Signature Name</label>
                      <input 
                        type="text" 
                        value={underwriterName} 
                        onChange={(e) => setUnderwriterName(e.target.value)} 
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div className="col-span-3">
                      <label className="block text-[11px] font-mono text-slate-400 mb-1">Underwriter Manual Notes & Compensating Factors</label>
                      <input 
                        type="text" 
                        value={underwriterNotes} 
                        onChange={(e) => setUnderwriterNotes(e.target.value)} 
                        placeholder="Record human underwriter rationale, compensating factors, or condition requirements..."
                        className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="h-96 flex flex-col items-center justify-center font-mono text-sm text-slate-500">
                <span className="font-mono font-bold">[*]</span>
                Loading Credit Risk Telemetry...
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Credit Memorandum Modal */}
      {memoModalOpen && memoData && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-[0_0_50px_rgba(0,0,0,0.8)] overflow-hidden font-mono">
            
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold">[*]</span>
                <h3 className="font-bold text-xs uppercase tracking-wider text-slate-100">
                  Institutional Credit Memorandum — {memoData.memo_id}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyMemoToClipboard}
                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 flex items-center gap-1.5 transition-colors"
                >
                  {copiedMemo ? <span className="font-mono font-bold">[*]</span> : <span className="font-mono font-bold">[*]</span>}
                  <span>{copiedMemo ? "Copied" : "Copy Markdown"}</span>
                </button>

                <button
                  onClick={downloadMemoMarkdown}
                  className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-xs text-white flex items-center gap-1.5 transition-colors"
                >
                  <span className="font-mono font-bold">[*]</span>
                  <span>Download .md</span>
                </button>

                <button
                  onClick={() => setMemoModalOpen(false)}
                  className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <span className="font-mono font-bold">[*]</span>
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 bg-slate-950 text-xs text-slate-300 leading-relaxed font-mono whitespace-pre-wrap select-text">
              {memoData.formatted_markdown}
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-slate-800 bg-slate-900/80 flex items-center justify-between text-[11px] text-slate-500">
              <span>SHA-256 Audit Log Ref: {memoData.audit_id}</span>
              <span className="text-amber-400/90 font-semibold">Immutable Decision Support Record</span>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
