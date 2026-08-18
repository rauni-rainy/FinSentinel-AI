"use client";

import { useEffect, useRef } from "react";
import { AlertTriangle, TrendingUp, ShieldAlert } from "lucide-react";

export type PendingCase = {
  thread_id: string;
  account: string;
  amount: number;
  calibrated_confidence: number;
  risk_score: number;
  summary: string;
  recommended_action: string;
  escalated_at?: string;
};

interface CaseQueueProps {
  cases: PendingCase[];
  activeCaseId: string | null;
  onSelectCase: (id: string) => void;
}

export function CaseQueue({ cases, activeCaseId, onSelectCase }: CaseQueueProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to active case
  useEffect(() => {
    if (activeCaseId && listRef.current) {
      const activeEl = listRef.current.querySelector(`[data-id="${activeCaseId}"]`);
      if (activeEl) {
        activeEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [activeCaseId]);

  return (
    <div className="flex flex-col h-full bg-slate-900 border-r border-slate-800" ref={listRef}>
      <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-950">
        <h2 className="text-sm font-bold tracking-widest text-slate-400 uppercase">Triage Queue</h2>
        <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-300 font-mono">{cases.length} pending</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {cases.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-sm">No cases in queue.</div>
        ) : (
          cases.map((c) => {
            const isActive = c.thread_id === activeCaseId;
            const isHighRisk = c.calibrated_confidence > 0.7;

            return (
              <button
                key={c.thread_id}
                data-id={c.thread_id}
                onClick={() => onSelectCase(c.thread_id)}
                className={`w-full text-left p-4 border-b border-slate-800/50 transition-colors focus:outline-none ${
                  isActive ? "bg-slate-800 border-l-4 border-l-brand-blue" : "hover:bg-slate-800/50 border-l-4 border-l-transparent"
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    {isHighRisk ? <ShieldAlert className="w-4 h-4 text-brand-red" /> : <AlertTriangle className="w-4 h-4 text-amber-500" />}
                    <span className="font-mono text-sm font-semibold text-slate-200">
                      {c.account.slice(0, 8)}...
                    </span>
                  </div>
                  <span className="font-mono text-sm font-bold text-slate-300">
                    ${c.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs text-slate-400 font-mono mt-2">
                  <span>Conf: {(c.calibrated_confidence * 100).toFixed(1)}%</span>
                  {c.escalated_at && (
                    <span className="bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded text-[10px] font-bold animate-pulse">
                      ESCALATED
                    </span>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
