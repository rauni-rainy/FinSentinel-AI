"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { CaseQueue, PendingCase } from "../components/CaseQueue";
import { CaseDetails } from "../components/CaseDetails";
import { TrustScorePanel } from "../components/TrustScorePanel";


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
        <div className="p-3 border-b border-slate-800 bg-slate-900 flex flex-col gap-3">
          {/* Logo Area */}
          <div className="flex flex-col w-full mb-0">
            <div className="flex items-start justify-between w-full">
              <div className="flex flex-col w-full">
                {/* Top Row: Mark & Telemetry (Fills top right) */}
                <div className="flex items-start justify-between w-full mb-1">
                  {/* Abstract Geometric Mark */}
                  <div className="flex items-center gap-1">
                    <div className="w-5 h-5 bg-cyan-500 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.4)]">
                      <div className="w-2 h-2 bg-slate-950"></div>
                    </div>
                    <div className="h-5 w-1 bg-cyan-700"></div>
                    <div className="h-5 w-[2px] bg-cyan-900"></div>
                  </div>
                  
                  {/* Top-Right Telemetry Data Array */}
                  <div className="flex items-start gap-2 pt-0.5 text-[8px] font-mono text-slate-500 text-right uppercase">
                    <div className="flex flex-col gap-[1px] items-end leading-none">
                      <span className="text-cyan-500 font-bold">SESSION // <span className="text-slate-300 font-normal">ACTV-092</span></span>
                      <span className="text-amber-500 font-bold">UPLINK // <span className="text-slate-300 font-normal">SECURE</span></span>
                      <span className="text-emerald-500 font-bold">CORE // <span className="text-slate-300 font-normal">STABLE</span></span>
                    </div>
                    <div className="grid grid-cols-3 gap-[2px] opacity-80 pt-0.5">
                      {[...Array(9)].map((_, i) => (
                        <div key={i} className={`w-1 h-1 ${i % 3 === 0 ? 'bg-cyan-500 animate-pulse' : (i % 5 === 0 ? 'bg-amber-400' : 'bg-slate-700')}`}></div>
                      ))}
                    </div>
                  </div>
                </div>
                
                {/* Typography */}
                <div className="flex items-end gap-3 w-full">
                  <h1 className="font-mono font-black text-4xl tracking-tight uppercase text-slate-100 leading-none">
                    FIN<span className="text-cyan-500 drop-shadow-[0_0_8px_rgba(6,182,212,0.6)]">SENTINEL</span>
                  </h1>
                </div>
                
                {/* Subtitle Row (Brought up tighter to logo) */}
                <div className="flex items-center gap-3 mt-1.5 w-full">
                  <span className="font-mono text-[10px] text-cyan-100 font-bold tracking-[0.2em] uppercase whitespace-nowrap">
                    Institutional Ledger Surveillance
                  </span>
                  <div className="flex-1 h-[1px] bg-slate-800"></div>
                  <div className="flex items-center gap-1.5 text-[9px] font-mono font-bold tracking-widest uppercase text-slate-400 border border-slate-700 bg-slate-950 px-2 py-0.5">
                    <span className="text-emerald-500 animate-pulse text-[10px] leading-none">●</span> SYS.OP
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Action Links */}
          <div className="flex items-center gap-2 w-full">
            <Link
              href="/credit-triage"
              className="flex-1 text-center px-2 py-2 font-mono text-[9px] font-bold bg-slate-950 hover:bg-cyan-950/50 text-cyan-400 hover:text-cyan-300 border border-cyan-900/50 rounded transition-all uppercase tracking-widest shadow-inner relative overflow-hidden group"
              title="Credit Risk Triage"
            >
              <div className="absolute inset-0 bg-cyan-500/10 translate-y-full group-hover:translate-y-0 transition-transform"></div>
              <span className="relative z-10">[ CREDIT ]</span>
            </Link>
            <Link
              href="/red-team"
              className="flex-1 text-center px-2 py-2 font-mono text-[9px] font-bold bg-slate-950 hover:bg-red-950/50 text-red-400 hover:text-red-300 border border-red-900/50 rounded transition-all uppercase tracking-widest shadow-inner relative overflow-hidden group"
              title="Red-Team Benchmark"
            >
              <div className="absolute inset-0 bg-red-500/10 translate-y-full group-hover:translate-y-0 transition-transform"></div>
              <span className="relative z-10">[ RED TEAM ]</span>
            </Link>
            <button 
              onClick={downloadReport}
              className="flex-1 text-center px-2 py-2 font-mono text-[9px] font-bold bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-700 rounded transition-all uppercase tracking-widest shadow-inner relative overflow-hidden group"
              title="Download Executive Report (ZIP)"
            >
              <div className="absolute inset-0 bg-slate-600/30 translate-y-full group-hover:translate-y-0 transition-transform"></div>
              <span className="relative z-10">[ EXPORT ]</span>
            </button>
          </div>
          
          {/* Dedicated Data Ops Command Center Link */}
          <div className="mt-3 w-full">
            <Link
              href="/data-ops"
              className="flex items-center justify-center w-full px-4 py-3 font-mono text-[10px] font-black bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-400 hover:text-emerald-300 border border-emerald-500/50 rounded transition-all uppercase tracking-[0.2em] shadow-[0_0_15px_rgba(16,185,129,0.15)] hover:shadow-[0_0_25px_rgba(16,185,129,0.3)] relative overflow-hidden group"
              title="Enter Data Ops Command Center"
            >
              <div className="absolute inset-0 bg-emerald-500/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300"></div>
              <span className="relative z-10 flex items-center gap-2">
                <span className="w-2 h-2 bg-emerald-500 animate-pulse rounded-full"></span>
                [ ENTER DATA OPS DROPZONE ]
              </span>
            </Link>
          </div>
        </div>
        
        <div className="flex-1 overflow-hidden">
          {loading ? (
            <div className="h-full flex items-center justify-center font-mono text-sm text-slate-500 uppercase tracking-widest">
              [ Syncing Checkpoints... ]
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
            <div className="font-sans font-black text-6xl opacity-10 mb-4 tracking-tighter">IDLE</div>
            <p className="font-mono text-lg tracking-widest uppercase">No Active Investigation</p>
            <p className="text-sm mt-2 font-mono text-slate-600">AWAITING SELECTION FROM TRIAGE QUEUE</p>
          </div>
        )}
      </div>
    </div>
  );
}
