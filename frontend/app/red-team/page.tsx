"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { ShieldAlert, RefreshCw, ChevronLeft } from "lucide-react";

export default function RedTeamPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchResults = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/reports/redteam_latest");
      const result = await res.json();
      if (result.status === "success") {
        setData(result.data);
      } else {
        setData(null);
      }
    } catch (err) {
      console.error(err);
      setData(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchResults();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-300 flex items-center justify-center font-mono">
        Loading Red-Team Simulation Results...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-300 flex flex-col items-center justify-center p-8 font-mono">
        <ShieldAlert className="w-16 h-16 text-slate-600 mb-6" />
        <h1 className="text-2xl font-bold text-slate-100 mb-2">Simulation Not Yet Run</h1>
        <p className="text-slate-500 max-w-md text-center mb-8">
          The Adversarial Red-Team Simulator hasn't generated any artifacts yet. Run the Python script or `make redteam` to execute the benchmark against the LLM, then refresh this page.
        </p>
        <button 
          onClick={fetchResults}
          className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded transition-colors flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" /> Check for Artifact
        </button>
      </div>
    );
  }

  // Format data for Recharts
  const structData = data.scenarios[0].variants.map((v: any) => ({
    name: v.variant_id,
    label: v.name,
    "Detection Confidence (%)": (v.calibrated_confidence * 100).toFixed(1),
    "Risk Score (%)": (v.risk_score * 100).toFixed(1),
    reasoning: v.llm_reasoning
  }));

  const synData = data.scenarios[1].variants.map((v: any) => ({
    name: v.variant_id,
    label: v.name,
    "Detection Confidence (%)": (v.calibrated_confidence * 100).toFixed(1),
    "Risk Score (%)": (v.risk_score * 100).toFixed(1),
    reasoning: v.llm_reasoning
  }));

  return (
    <div className="h-screen bg-slate-950 text-slate-300 font-mono p-8 overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-8 pb-20">
        
        {/* Header */}
        <header className="border-b border-slate-800 pb-6">
          <div className="flex justify-between items-end">
            <div>
              <a href="/" className="inline-flex items-center gap-2 text-brand-blue hover:text-sky-300 mb-4 text-sm transition-colors">
                <ChevronLeft className="w-4 h-4" /> Back to Triage Queue
              </a>
              <h1 className="text-3xl font-bold text-slate-100 tracking-tight flex items-center gap-3">
                <ShieldAlert className="text-brand-red w-8 h-8" /> Adversarial Evaluation Report
              </h1>
              <p className="text-slate-500 mt-2 max-w-2xl text-sm leading-relaxed">
                Measuring detection confidence decay as synthetic adversaries progressively structure transactions and blur identity graphs to evade the `{data.metadata.model}` LLM node.
              </p>
            </div>
            <div className="text-right text-xs text-slate-500 bg-slate-900 p-4 rounded border border-slate-800">
              <p>Model: <span className="text-slate-300 font-bold">{data.metadata.model}</span></p>
              <p>Vector: <span className="text-slate-300">{data.metadata.embeddings}</span></p>
              <p>Run Time: {new Date(data.metadata.timestamp).toLocaleString()}</p>
            </div>
          </div>
        </header>

        {/* Structuring Scenario */}
        <section className="bg-slate-900/50 border border-slate-800 rounded p-6">
          <h2 className="text-xl font-bold text-slate-100 mb-2">Scenario A: Structuring / Smurfing</h2>
          <p className="text-slate-400 text-sm mb-8">{data.scenarios[0].description}</p>
          
          <div className="h-[300px] mb-8">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={structData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} />
                <YAxis stroke="#64748b" domain={[0, 100]} tick={{ fill: '#64748b' }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', color: '#f1f5f9' }}
                  itemStyle={{ color: '#f8fafc' }}
                />
                <Legend />
                <Line type="monotone" dataKey="Detection Confidence (%)" stroke="#ef4444" strokeWidth={3} dot={{ r: 6, fill: '#ef4444' }} activeDot={{ r: 8 }} />
                <Line type="monotone" dataKey="Risk Score (%)" stroke="#3b82f6" strokeDasharray="5 5" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-800/50 border-b border-slate-700">
                  <th className="p-3 font-bold text-slate-300">Variant</th>
                  <th className="p-3 font-bold text-slate-300">Conf.</th>
                  <th className="p-3 font-bold text-slate-300 w-1/2">LLM Reasoning Trace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {structData.map((d: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-800/30">
                    <td className="p-3 text-slate-400 whitespace-nowrap">{d.label}</td>
                    <td className="p-3 font-bold text-slate-200">{d["Detection Confidence (%)"]}%</td>
                    <td className="p-3 text-slate-500 text-xs">
                      <div className="space-y-1">
                        <p><span className="text-slate-400">Signal:</span> {d.reasoning.signal_magnitude}</p>
                        <p><span className="text-slate-400">Context:</span> {d.reasoning.similar_cases_context}</p>
                        <p><span className="text-brand-blue">Typology:</span> {d.reasoning.typology_match}</p>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Synthetic ID Scenario */}
        <section className="bg-slate-900/50 border border-slate-800 rounded p-6">
          <h2 className="text-xl font-bold text-slate-100 mb-2">Scenario B: Synthetic Identity Blending</h2>
          <p className="text-slate-400 text-sm mb-8">{data.scenarios[1].description}</p>
          
          <div className="h-[300px] mb-8">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={synData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="label" stroke="#64748b" tick={{ fill: '#64748b', fontSize: 12 }} />
                <YAxis stroke="#64748b" domain={[0, 100]} tick={{ fill: '#64748b' }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#020617', borderColor: '#1e293b', color: '#f1f5f9' }}
                />
                <Legend />
                <Line type="monotone" dataKey="Detection Confidence (%)" stroke="#f59e0b" strokeWidth={3} dot={{ r: 6, fill: '#f59e0b' }} activeDot={{ r: 8 }} />
                <Line type="monotone" dataKey="Risk Score (%)" stroke="#3b82f6" strokeDasharray="5 5" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-800/50 border-b border-slate-700">
                  <th className="p-3 font-bold text-slate-300">Variant</th>
                  <th className="p-3 font-bold text-slate-300">Conf.</th>
                  <th className="p-3 font-bold text-slate-300 w-1/2">LLM Reasoning Trace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {synData.map((d: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-800/30">
                    <td className="p-3 text-slate-400 whitespace-nowrap">{d.label}</td>
                    <td className="p-3 font-bold text-slate-200">{d["Detection Confidence (%)"]}%</td>
                    <td className="p-3 text-slate-500 text-xs">
                      <div className="space-y-1">
                        <p><span className="text-slate-400">Signal:</span> {d.reasoning.signal_magnitude}</p>
                        <p><span className="text-slate-400">Context:</span> {d.reasoning.similar_cases_context}</p>
                        <p><span className="text-amber-500">Typology:</span> {d.reasoning.typology_match}</p>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </div>
  );
}
