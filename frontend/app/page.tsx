"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { CaseQueue, PendingCase } from "../components/CaseQueue";
import { CaseDetails } from "../components/CaseDetails";
import { TrustScorePanel } from "../components/TrustScorePanel";
import { Activity, LayoutDashboard, ShieldAlert, Download, CreditCard, Crosshair } from "lucide-react";

export default function Home() {
  const [cases, setCases] = useState<PendingCase[]>([]);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchCases = () => {
    fetch("http://localhost:8000/cases/pending")
      .then((res) => res.json())
      .then((data) => {
        setCases(data);
        if (data.length > 0 && (!activeCaseId || !data.find((c: any) => c.thread_id === activeCaseId))) {
          setActiveCaseId(data[0].thread_id);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch pending cases", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchCases();
    
    const ws = new WebSocket("ws://localhost:8000/ws/notifications");
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "new_interrupt" || data.event === "escalation") {
          fetchCases();
        }
      } catch (e) {
        console.error("WS parse error", e);
      }
    };
    return () => {
      ws.close();
    };
  }, []);

  const handleCaseProcessed = () => {
    // Refresh the queue after a decision is made
    fetchCases();
  };

  const downloadReport = () => {
    window.location.href = "http://localhost:8000/reports/executive_summary?session_id=all";
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-50">
      {/* Sidebar: Queue & Telemetry */}
      <div className="w-[400px] flex flex-col border-r border-slate-800 shrink-0">
        <div className="p-4 border-b border-slate-800 bg-slate-900 flex justify-between items-center gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand-blue rounded">
              <LayoutDashboard className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-widest uppercase">FinSentinel AI</h1>
              <p className="text-xs text-slate-400 font-mono">Investigator Cockpit</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Link
              href="/credit-triage"
              className="p-2 bg-slate-800 hover:bg-blue-600/30 text-blue-400 hover:text-blue-200 border border-blue-500/20 rounded transition-colors"
              title="Credit Risk Triage"
            >
              <CreditCard className="w-4 h-4" />
            </Link>
            <Link
              href="/red-team"
              className="p-2 bg-slate-800 hover:bg-red-600/30 text-red-400 hover:text-red-200 border border-red-500/20 rounded transition-colors"
              title="Red-Team Benchmark"
            >
              <Crosshair className="w-4 h-4" />
            </Link>
            <button 
              onClick={downloadReport}
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
              title="Download Executive Report (ZIP)"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
        </div>
        
        <div className="flex-1 overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center font-mono text-sm text-slate-500">
              <Activity className="animate-spin mr-2" /> Syncing Checkpoints...
            </div>
          ) : (
            <CaseQueue cases={cases} activeCaseId={activeCaseId} onSelectCase={setActiveCaseId} />
          )}
        </div>
        
        <div className="h-[250px] border-t border-slate-800 bg-slate-900 shrink-0">
          <TrustScorePanel />
        </div>
      </div>

      {/* Main Content: Case Details */}
      <div className="flex-1 flex flex-col min-w-0 bg-slate-950">
        {activeCaseId ? (
          <CaseDetails caseId={activeCaseId} onProcessed={handleCaseProcessed} />
        ) : (
          <div className="flex-1 flex items-center justify-center flex-col text-slate-500">
            <ShieldAlert className="w-16 h-16 mb-4 opacity-20" />
            <p className="font-mono text-lg">No Active Investigation</p>
            <p className="text-sm mt-2">Select a case from the triage queue.</p>
          </div>
        )}
      </div>
    </div>
  );
}
