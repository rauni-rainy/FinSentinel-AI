"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  CreditCard, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp, 
  DollarSign, 
  PieChart as PieIcon, 
  Activity, 
  ArrowLeft, 
  FileText, 
  Layers, 
  RefreshCw,
  Info,
  Building2,
  Lock,
  ChevronRight,
  Sparkles
} from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";

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

interface RiskFactorSummary {
  applicant_id: string;
  applicant_name: string;
  evaluated_at: string;
  ratios: CalculatedRatios;
  macro_context: MacroIndicators;
  risk_factors: RiskFactor[];
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

export default function CreditTriagePage() {
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
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
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [macroBenchmarks, setMacroBenchmarks] = useState<any>(null);
  
  // Underwriter manual worksheet notes
  const [underwriterNotes, setUnderwriterNotes] = useState<string>("");
  const [checkedVerifications, setCheckedVerifications] = useState<Record<string, boolean>>({
    income: true,
    assets: true,
    credit: true,
    macro: false
  });

  // Load Presets & Macro Benchmarks on Mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch("http://localhost:8000/credit/presets").then(res => res.json()),
      fetch("http://localhost:8000/credit/macro-benchmarks").then(res => res.json())
    ])
      .then(([presetsData, macroData]) => {
        setPresets(presetsData);
        setMacroBenchmarks(macroData);
        if (presetsData.length > 0) {
          setSelectedPresetId(presetsData[0].id);
          setApplicant(presetsData[0].profile);
          // Evaluate initial preset
          runEvaluation(presetsData[0].profile);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load presets/macro benchmarks", err);
        setLoading(false);
      });
  }, []);

  const runEvaluation = async (profile: ApplicantProfile) => {
    setEvaluating(true);
    try {
      const res = await fetch("http://localhost:8000/credit/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile)
      });
      if (res.ok) {
        const data = await res.json();
        setSummary(data);
      }
    } catch (e) {
      console.error("Failed to evaluate credit triage", e);
    }
    setEvaluating(false);
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

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      
      {/* Top Global Navigation Bar */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/90 px-6 flex items-center justify-between shrink-0 z-20 backdrop-blur-md">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-blue-600 rounded">
              <CreditCard className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-wider uppercase text-slate-100 flex items-center gap-2">
                FinSentinel AI <span className="text-blue-400 font-mono text-xs font-normal">| Credit Triage</span>
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

        {/* Prominent Decision Support Badge */}
        <div className="flex items-center gap-2 bg-amber-950/40 border border-amber-600/40 px-3 py-1 rounded-full text-xs font-mono text-amber-300">
          <Lock className="w-3.5 h-3.5 text-amber-400" />
          <span>Decision Support System — Human Underwriter Authority Only</span>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Column: Applicant Presets & Profile Form */}
        <div className="w-[420px] border-r border-slate-800 bg-slate-900/40 flex flex-col shrink-0 overflow-hidden">
          
          {/* Preset Selector */}
          <div className="p-4 border-b border-slate-800 bg-slate-900/80">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                Underwriting Presets
              </span>
              <span className="text-[10px] font-mono text-slate-500">BofA / JPM Archetypes</span>
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
                Applicant Financials
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
                  <label className="block text-slate-400 mb-1">Proposed Loan Payment</label>
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
                  <label className="block text-slate-400 mb-1">Liquid Assets (Reserves)</label>
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
                <label className="block text-slate-400 mb-1">Loan Purpose</label>
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
                    <Activity className="w-4 h-4 animate-spin" />
                    Calculating Ratios...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4" />
                    Recalculate Risk Factors
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Triage Telemetry, Macro Indicators, & Underwriter Decision Support */}
        <div className="flex-1 flex flex-col overflow-y-auto bg-slate-950 p-6 space-y-6">
          
          {/* Header Disclaimer Banner */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-lg p-4 flex items-start gap-3 relative overflow-hidden">
            <div className="p-2 bg-blue-950/60 border border-blue-500/30 rounded text-blue-400 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h2 className="font-bold text-sm text-slate-200 font-mono uppercase tracking-wider">
                  Underwriter Decision Support Dashboard
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-blue-950/80 border border-blue-700/50 rounded text-blue-300">
                  Read-Only Telemetry
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-1 leading-relaxed">
                {summary?.disclaimer || "Surfaces objective credit leverage, utilization, and macro indicators for licensed human underwriters. FinSentinel structurally does not make autonomous credit decisions."}
              </p>
            </div>
            {summary?.audit_id && (
              <div className="text-right font-mono text-[10px] text-slate-500 shrink-0">
                <div>Audit Ref: {summary.audit_id.substring(0, 8)}</div>
                <div className="text-emerald-500 flex items-center justify-end gap-1 mt-0.5">
                  <CheckCircle2 className="w-3 h-3" /> Chain Verified
                </div>
              </div>
            )}
          </div>

          {summary ? (
            <>
              {/* Ratio Telemetry Cards (DTI, Utilization, Liquidity, Residual) */}
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

                {/* Liquidity Coverage Cushion */}
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
                    <span className="text-slate-400">Residual Monthly Income</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                      Post-Debt
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

              {/* Two Column Layout: Macro Matrix & Underwriter Narrative */}
              <div className="grid grid-cols-2 gap-6">
                
                {/* Macro Indicators & Sector Sensitivity */}
                <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 flex flex-col">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-blue-400" />
                      <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                        Macroeconomic Stress Matrix
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">Sector: {applicant.industry_sector}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-4 font-mono text-xs">
                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <div className="text-slate-500 text-[10px]">Fed Funds Policy Rate</div>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        {summary.macro_context.benchmark_fed_funds_rate_pct}%
                      </div>
                      <div className="text-[10px] text-amber-400/80 mt-1">Elevated benchmark cost</div>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <div className="text-slate-500 text-[10px]">Sector Delinquency Baseline</div>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        {summary.macro_context.sector_default_rate_pct}%
                      </div>
                      <div className="text-[10px] text-slate-400 mt-1">Natl Avg: 2.5%</div>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <div className="text-slate-500 text-[10px]">CPI Inflation (YoY)</div>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        {summary.macro_context.cpi_inflation_yoy_pct}%
                      </div>
                      <div className="text-[10px] text-slate-400 mt-1">Cost-of-living index</div>
                    </div>

                    <div className="bg-slate-950 p-3 rounded border border-slate-800">
                      <div className="text-slate-500 text-[10px]">Regional Unemployment</div>
                      <div className="text-base font-bold text-slate-200 mt-1">
                        {summary.macro_context.regional_unemployment_pct}%
                      </div>
                      <div className="text-[10px] text-emerald-400/80 mt-1">Stable labor market</div>
                    </div>
                  </div>

                  <div className="text-xs font-mono text-slate-400 leading-relaxed bg-slate-950/60 p-3 rounded border border-slate-800/80">
                    <span className="text-blue-400 font-bold">Underwriter Macro Cross-Reference:</span> Applicant's employment in <span className="text-slate-200">{applicant.industry_sector}</span> reflects a {summary.macro_context.sector_default_rate_pct}% default baseline against a {summary.macro_context.benchmark_fed_funds_rate_pct}% policy rate.
                  </div>
                </div>

                {/* Plain Language Underwriter Synthesis */}
                <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <FileText className="w-4 h-4 text-blue-400" />
                      <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                        Plain-Language Risk Factor Summary
                      </h3>
                    </div>
                    <div className="bg-slate-950 border border-slate-800 p-4 rounded text-xs font-mono text-slate-300 leading-relaxed space-y-2">
                      <p>{summary.underwriter_narrative}</p>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono text-slate-500">
                    <span>Evaluated: {new Date(summary.evaluated_at).toLocaleTimeString()}</span>
                    <span className="text-blue-400">Strict Non-Autonomous Compliance &#10003;</span>
                  </div>
                </div>
              </div>

              {/* Categorized Risk Factors & Mitigants Breakdown */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-blue-400" />
                    <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-200">
                      Surfaced Risk Factors & Mitigants
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
                          ? "bg-emerald-950/20 border-emerald-500/30 text-slate-200 hover:border-emerald-500/50"
                          : factor.factor_type === "ELEVATED_RISK"
                          ? "bg-red-950/20 border-red-500/30 text-slate-200 hover:border-red-500/50"
                          : "bg-slate-950 border-slate-800 text-slate-300"
                      }`}
                    >
                      <div className="mt-0.5 shrink-0">
                        {factor.factor_type === "POSITIVE_MITIGANT" ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : factor.factor_type === "ELEVATED_RISK" ? (
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                        ) : (
                          <Info className="w-4 h-4 text-slate-400" />
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

              {/* Underwriter Manual Worksheet / Review Checklist */}
              <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-amber-400" />
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
                      checked={checkedVerifications.income} 
                      onChange={(e) => setCheckedVerifications({...checkedVerifications, income: e.target.checked})}
                      className="accent-blue-500" 
                    />
                    <span className="text-slate-300">W2 / Tax Return Verified</span>
                  </label>

                  <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                    <input 
                      type="checkbox" 
                      checked={checkedVerifications.assets} 
                      onChange={(e) => setCheckedVerifications({...checkedVerifications, assets: e.target.checked})}
                      className="accent-blue-500" 
                    />
                    <span className="text-slate-300">Liquid Assets Statement</span>
                  </label>

                  <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                    <input 
                      type="checkbox" 
                      checked={checkedVerifications.credit} 
                      onChange={(e) => setCheckedVerifications({...checkedVerifications, credit: e.target.checked})}
                      className="accent-blue-500" 
                    />
                    <span className="text-slate-300">Revolving Line History</span>
                  </label>

                  <label className="flex items-center gap-2 p-2 bg-slate-950 rounded border border-slate-800 cursor-pointer hover:border-slate-700">
                    <input 
                      type="checkbox" 
                      checked={checkedVerifications.macro} 
                      onChange={(e) => setCheckedVerifications({...checkedVerifications, macro: e.target.checked})}
                      className="accent-blue-500" 
                    />
                    <span className="text-slate-300">Macro Stress Evaluated</span>
                  </label>
                </div>

                <textarea
                  value={underwriterNotes}
                  onChange={(e) => setUnderwriterNotes(e.target.value)}
                  placeholder="Record human underwriter rationale, compensating factors, or condition requirements here..."
                  className="w-full h-20 bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>

            </>
          ) : (
            <div className="h-96 flex flex-col items-center justify-center font-mono text-sm text-slate-500">
              <Activity className="animate-spin mb-2 w-6 h-6 text-blue-500" />
              Loading Credit Risk Telemetry...
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
