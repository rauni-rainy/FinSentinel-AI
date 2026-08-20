"use client";

import React, { useState } from "react";
import Link from "next/link";
import { DataDropzone } from "../../components/DataDropzone";

export default function DataOpsPage() {
  const [ingestCount, setIngestCount] = useState(0);
  const [totalRows, setTotalRows]     = useState(0);

  const handleUploadSuccess = (rows?: number) => {
    setIngestCount(prev => prev + 1);
    if (rows) setTotalRows(prev => prev + rows);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col items-center relative overflow-x-hidden font-mono">

      {/* Background Grid */}
      <div
        className="absolute inset-0 z-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(6,182,212,1) 1px, transparent 1px), linear-gradient(90deg, rgba(6,182,212,1) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Top bar */}
      <div className="w-full flex items-center justify-between px-6 py-5 z-20">
        <Link
          href="/"
          className="flex items-center gap-2 text-[10px] text-cyan-500 hover:text-cyan-300 tracking-[0.2em] uppercase font-bold transition-colors group"
        >
          <span className="group-hover:-translate-x-1 transition-transform">{"<<"}</span>
          RETURN TO COCKPIT
        </Link>

        <div className="text-right text-[9px] tracking-widest text-slate-500 uppercase leading-relaxed">
          <div>SYS.OP // <span className="text-emerald-500">ONLINE</span></div>
          <div>DUCKDB CLUSTER // <span className="text-cyan-500">MOUNTED (IN-MEMORY)</span></div>
          <div>VECTOR POOL // <span className="text-amber-500">IDLE</span></div>
          <div className="mt-1 flex justify-end gap-1 opacity-60">
            {[...Array(6)].map((_, i) => (
              <div key={i} className={`w-1.5 h-1.5 ${i % 2 === 0 ? "bg-cyan-500 animate-pulse" : "bg-slate-700"}`} />
            ))}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="z-10 w-full max-w-3xl flex flex-col items-center gap-6 px-6 pb-16">

        {/* Header */}
        <div className="flex flex-col items-center text-center">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 bg-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.5)] flex items-center justify-center">
              <div className="w-3 h-3 bg-slate-950" />
            </div>
            <h1 className="text-5xl font-black tracking-tighter text-slate-100">
              DATA<span className="text-emerald-500">OPS</span>
            </h1>
          </div>
          <p className="text-[11px] text-emerald-100/70 tracking-[0.3em] uppercase font-bold border-b border-emerald-900/50 pb-2">
            In-Memory Ledger Ingestion &amp; Adversarial Sweep
          </p>
        </div>

        {/* Stats row */}
        <div className="w-full flex gap-6">
          <div className="flex-1 bg-slate-900/50 border border-slate-800 p-3 rounded-sm text-center">
            <div className="text-xs text-slate-500 tracking-widest uppercase mb-1">Ingestion Runs</div>
            <div className="text-2xl font-bold text-slate-200">{ingestCount}</div>
          </div>
          <div className="flex-1 bg-slate-900/50 border border-slate-800 p-3 rounded-sm text-center">
            <div className="text-xs text-slate-500 tracking-widest uppercase mb-1">Ingestion Engine</div>
            <div className="text-2xl font-bold text-cyan-400">DUCKDB</div>
          </div>
          <div className="flex-1 bg-slate-900/50 border border-slate-800 p-3 rounded-sm text-center">
            <div className="text-xs text-slate-500 tracking-widest uppercase mb-1">Sweep Agent</div>
            <div className="text-2xl font-bold text-emerald-400">ONLINE</div>
          </div>
          <div className="flex-1 bg-slate-900/50 border border-slate-800 p-3 rounded-sm text-center">
            <div className="text-xs text-slate-500 tracking-widest uppercase mb-1">LLM Reasoner</div>
            <div className="text-2xl font-bold text-violet-400">PHI4-MINI</div>
          </div>
        </div>

        {/* Dropzone card */}
        <div className="w-full bg-slate-900/50 border border-slate-800 p-6 rounded-sm shadow-2xl backdrop-blur-sm relative">
          {/* Corner accents */}
          <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-cyan-500/50" />
          <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-cyan-500/50" />
          <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-cyan-500/50" />
          <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-cyan-500/50" />

          <DataDropzone onUploadSuccess={handleUploadSuccess} />
        </div>

      </div>

      {/* Bottom disclaimer */}
      <div className="absolute bottom-5 w-full text-center text-[8px] text-slate-700 tracking-[0.2em] uppercase px-12">
        WARNING: All uploaded transactions are immediately passed through the LangGraph investigation pipeline.
        High-risk threads interrupt for human review.
      </div>
    </div>
  );
}
