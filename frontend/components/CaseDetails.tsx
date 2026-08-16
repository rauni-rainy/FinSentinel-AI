"use client";

import { useEffect, useState, useCallback } from "react";
import { ReactFlow, Background, Controls, Node, Edge, MarkerType } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ShieldCheck, ShieldAlert, AlertOctagon, Activity } from "lucide-react";

interface CaseDetailsProps {
  caseId: string;
  onProcessed: () => void;
}

export function CaseDetails({ caseId, onProcessed }: CaseDetailsProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`http://localhost:8000/cases/${caseId}`)
      .then((res) => res.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [caseId]);

  const handleDecision = useCallback(
    async (decision: string) => {
      if (processing) return;
      setProcessing(true);
      try {
        await fetch(`http://localhost:8000/cases/${caseId}/resume`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision }),
        });
        onProcessed();
      } catch (err) {
        console.error("Failed to resume thread:", err);
      } finally {
        setProcessing(false);
      }
    },
    [caseId, processing, onProcessed]
  );

  // Global Keyboard Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const key = e.key.toUpperCase();
      if (key === "A") handleDecision("APPROVE");
      if (key === "R") handleDecision("DENY");
      if (key === "E") handleDecision("ESCALATE");
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleDecision]);

  if (loading || !data) {
    return (
      <div className="h-full w-full flex items-center justify-center text-slate-500 font-mono">
        <Activity className="animate-spin mr-2" /> Loading case ledger...
      </div>
    );
  }

  // Format React Flow nodes for dark mode
  const nodes: Node[] = (data.network?.nodes || []).map((n: any) => ({
    ...n,
    style: {
      background: n.data.isRoot ? "#003366" : n.data.isFraud ? "#450a0a" : "#1e293b",
      color: "#f8fafc",
      border: `1px solid ${n.data.isFraud ? "#ef4444" : "#475569"}`,
      borderRadius: "4px",
      padding: "10px",
      fontFamily: "monospace",
      fontSize: "12px",
      width: 180,
    },
  }));

  const edges: Edge[] = (data.network?.edges || []).map((e: any) => ({
    ...e,
    style: { stroke: "#475569", strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#475569" },
  }));

  return (
    <div className="flex flex-col h-full bg-slate-950 relative">
      {/* Header */}
      <div className="p-6 border-b border-slate-800 bg-slate-900/50 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold font-mono tracking-tight text-slate-100">
              Txn: {data.transaction?.transaction_id?.slice(0, 8)}
            </h1>
            <span className="px-2 py-1 bg-slate-800 text-slate-300 text-xs font-mono rounded">
              {data.transaction?.merchant_category?.toUpperCase()}
            </span>
          </div>
          <p className="text-slate-400 font-mono text-sm">Account: {data.transaction?.account_id}</p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-slate-100 font-mono">
            ${(data.transaction?.amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-slate-400 text-sm font-mono mt-1">
            Risk: {(data.risk_score * 100).toFixed(0)} | Conf: {(data.calibrated_confidence * 100).toFixed(1)}% | <span className="text-slate-300">AI suggests: </span><span className={`font-bold ${data.recommended_action === 'APPROVE' ? 'text-emerald-400' : data.recommended_action === 'DENY' ? 'text-rose-500' : 'text-amber-400'}`}>{data.recommended_action}</span>
          </div>
        </div>
      </div>

      {/* Main Content Split */}
      <div className="flex-1 flex overflow-hidden">
        {/* Timeline Evidence */}
        <div className="w-1/3 border-r border-slate-800 p-6 overflow-y-auto bg-slate-950">
          <h2 className="text-xs font-bold tracking-widest text-slate-500 uppercase mb-6">Execution Trace</h2>
          
          <div className="relative pl-4 border-l-2 border-slate-800 space-y-8">
            <div className="relative">
              <div className="absolute w-3 h-3 bg-brand-blue rounded-full -left-[23px] top-1"></div>
              <p className="text-xs text-slate-500 font-mono mb-1">FAST SCREEN</p>
              <p className="text-sm text-slate-300">Transaction isolated from ledger stream.</p>
            </div>
            <div className="relative">
              <div className="absolute w-3 h-3 bg-brand-blue rounded-full -left-[23px] top-1"></div>
              <p className="text-xs text-slate-500 font-mono mb-1">SIMILAR CASES</p>
              <p className="text-sm text-slate-300">Found {data.network?.nodes?.filter((n: any) => n.id.startsWith("case_")).length || 0} historical links via pgvector.</p>
            </div>
            <div className="relative">
              <div className="absolute w-3 h-3 bg-brand-blue rounded-full -left-[23px] top-1"></div>
              <p className="text-xs text-slate-500 font-mono mb-1">LLM REASONING</p>
              <div className="bg-slate-900 border border-slate-800 rounded p-4 mt-2">
                {typeof data.summary === 'object' && data.summary !== null ? (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-start gap-2">
                      <span className="text-brand-blue/80 w-1/4 text-xs font-mono font-bold uppercase tracking-widest mt-0.5">Signal</span>
                      <span className="text-slate-300 w-3/4 text-sm">{data.summary.signal_magnitude}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-brand-blue/80 w-1/4 text-xs font-mono font-bold uppercase tracking-widest mt-0.5">Context</span>
                      <span className="text-slate-300 w-3/4 text-sm">{data.summary.similar_cases_context}</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-brand-blue/80 w-1/4 text-xs font-mono font-bold uppercase tracking-widest mt-0.5">Typology</span>
                      <span className="text-slate-300 w-3/4 text-sm">{data.summary.typology_match}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-300 leading-relaxed">{String(data.summary)}</p>
                )}
              </div>
            </div>
            <div className="relative">
              <div className="absolute w-3 h-3 bg-amber-500 rounded-full -left-[23px] top-1 animate-pulse"></div>
              <p className="text-xs text-amber-500 font-mono mb-1">INTERRUPT</p>
              <p className="text-sm text-slate-300">Paused execution for human authorization.</p>
            </div>
            </div>
          </div>

        {/* Network Graph */}
        <div className="w-2/3 relative bg-slate-950">
          <ReactFlow
            nodes={nodes.map(n => ({
              ...n,
              style: n.data.fullText ? { ...n.style, width: 220, padding: 10 } : n.style,
              data: {
                ...n.data,
                label: n.data.fullText ? (
                  <div title={n.data.fullText} className="cursor-help whitespace-pre-wrap break-words w-full text-xs leading-snug text-center">
                    {n.data.label}
                  </div>
                ) : n.data.label
              }
            }))}
            edges={edges}
            fitView 
            proOptions={{ hideAttribution: true }}
            colorMode="dark"
          >
            <Background color="#1e293b" gap={16} size={1} />
            <Controls className="!bg-slate-900 !border-slate-800 !fill-slate-400" />
          </ReactFlow>
          <div className="absolute top-4 left-4 text-xs font-mono text-slate-500 tracking-widest uppercase">
            Entity Resolution Network
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between">
        <div className="text-xs text-slate-500 font-mono flex items-center gap-4">
          <span><kbd className="bg-slate-800 px-2 py-1 rounded text-slate-300 border border-slate-700">A</kbd> Approve</span>
          <span><kbd className="bg-slate-800 px-2 py-1 rounded text-slate-300 border border-slate-700">R</kbd> Reject</span>
          <span><kbd className="bg-slate-800 px-2 py-1 rounded text-slate-300 border border-slate-700">E</kbd> Escalate</span>
        </div>
        
        <div className="flex gap-3">
          <button onClick={() => handleDecision("APPROVE")} disabled={processing} className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-bold font-mono rounded flex items-center gap-2 transition-colors border border-slate-700">
            <ShieldCheck className="w-4 h-4 text-emerald-500" /> [A] APPROVE
          </button>
          <button onClick={() => handleDecision("DENY")} disabled={processing} className="px-6 py-2 bg-brand-red/20 hover:bg-brand-red/30 text-brand-red text-sm font-bold font-mono rounded flex items-center gap-2 transition-colors border border-brand-red/50">
            <ShieldAlert className="w-4 h-4" /> [R] REJECT
          </button>
          <button onClick={() => handleDecision("ESCALATE")} disabled={processing} className="px-6 py-2 bg-amber-500/20 hover:bg-amber-500/30 text-amber-500 text-sm font-bold font-mono rounded flex items-center gap-2 transition-colors border border-amber-500/50">
            <AlertOctagon className="w-4 h-4" /> [E] ESCALATE
          </button>
        </div>
      </div>

      {processing && (
        <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="text-brand-blue font-mono text-lg flex items-center gap-3">
            <Activity className="animate-spin" /> EXECUTING COMMAND(RESUME)...
          </div>
        </div>
      )}
    </div>
  );
}
