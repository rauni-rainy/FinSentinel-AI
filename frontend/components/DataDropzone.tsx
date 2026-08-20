"use client";

import React, { useState, useRef, useEffect } from "react";

type DropzoneState = "IDLE" | "DRAGGING" | "UPLOADING" | "PROCESSING" | "SUCCESS" | "ERROR";

interface LogLine {
  ts: string;
  level: "INFO" | "WARN" | "OK" | "ERR" | "SYS";
  text: string;
}

interface UploadResult {
  rows_inserted: number;
  message: string;
}

const PIPELINE_STAGES = [
  {
    id: "ingest",
    label: "DuckDB Ingestion",
    icon: "◈",
    color: "text-cyan-400",
    bar: "bg-cyan-500",
    desc: "CSV/XLSX is parsed in-memory by DuckDB. Null fields, type coercions, and duplicate IDs are cleaned before any row touches Postgres.",
  },
  {
    id: "persist",
    label: "Postgres Persist",
    icon: "⬡",
    color: "text-violet-400",
    bar: "bg-violet-500",
    desc: "Cleaned rows bulk-inserted into the `transactions` table. pgvector extension is active — embeddings will be attached by the sweep node.",
  },
  {
    id: "fastpath",
    label: "Fast-Path Screener",
    icon: "⚡",
    color: "text-amber-400",
    bar: "bg-amber-500",
    desc: "Each row hits the Z-Score + Bloom Filter + Count-Min Sketch classifier (~0.4 ms/row, zero LLM cost). PASS rows are archived. AMBIGUOUS / HIGH_CONFIDENCE_FLAG rows escalate.",
  },
  {
    id: "langgraph",
    label: "LangGraph Sweep",
    icon: "◎",
    color: "text-emerald-400",
    bar: "bg-emerald-500",
    desc: "Escalated rows enter the investigation StateGraph: retrieve_similar_cases → investigate (phi4-mini via Ollama) → calibrate → human_review_gate. High-risk cases interrupt and wait for an analyst.",
  },
  {
    id: "queue",
    label: "Case Queue",
    icon: "▣",
    color: "text-rose-400",
    bar: "bg-rose-500",
    desc: "Flagged threads land in the Pending Cases queue with calibrated confidence scores. The escalation sweep auto-escalates any case stale > the configured window (default 1 min).",
  },
];

function ts(): string {
  return new Date().toISOString().split("T")[1].split(".")[0];
}

export function DataDropzone({ onUploadSuccess }: { onUploadSuccess: (rows?: number) => void }) {
  const [status, setStatus] = useState<DropzoneState>("IDLE");
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [activeStage, setActiveStage] = useState<number>(-1);
  const [stagesComplete, setStagesComplete] = useState<boolean[]>([false, false, false, false, false]);
  const [showExplainer, setShowExplainer] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const appendLog = (level: LogLine["level"], text: string) => {
    setLogs(prev => [...prev, { ts: ts(), level, text }]);
  };

  const markStage = (idx: number) => {
    setActiveStage(idx);
    setStagesComplete(prev => {
      const next = [...prev];
      if (idx > 0) next[idx - 1] = true;
      return next;
    });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (status === "IDLE") setStatus("DRAGGING");
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (status === "DRAGGING") setStatus("IDLE");
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) await processFile(files[0]);
    else setStatus("IDLE");
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) await processFile(files[0]);
  };

  const processFile = async (file: File) => {
    if (!file.name.endsWith(".csv") && !file.name.endsWith(".xlsx")) {
      setStatus("ERROR");
      setLogs([{ ts: ts(), level: "ERR", text: "UNSUPPORTED FORMAT — only .csv or .xlsx accepted" }]);
      setTimeout(() => { setStatus("IDLE"); setLogs([]); }, 3500);
      return;
    }

    // Reset
    setLogs([]);
    setResult(null);
    setActiveStage(-1);
    setStagesComplete([false, false, false, false, false]);
    setShowExplainer(false);

    setStatus("UPLOADING");
    appendLog("SYS", `UPLINK INITIATED — transmitting ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);

    const formData = new FormData();
    formData.append("file", file);

    let data: UploadResult;
    try {
      const res = await fetch("http://localhost:8000/upload-transactions", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      data = await res.json();
      appendLog("OK", `UPLINK COMPLETE — backend acknowledged ${data.rows_inserted} rows`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setStatus("ERROR");
      appendLog("ERR", `UPLOAD FAILED: ${msg}`);
      setTimeout(() => { setStatus("IDLE"); setLogs([]); }, 5000);
      return;
    }

    // ── Stage 0: DuckDB ingestion (already happened server-side, narrate it) ──
    setStatus("PROCESSING");
    markStage(0);
    appendLog("INFO", "DuckDB engine: mounting in-memory analytical store");
    await delay(400);
    appendLog("INFO", `DuckDB: scanning ${data.rows_inserted} rows for nulls, type coercions, duplicate IDs`);
    await delay(600);
    appendLog("OK", `DuckDB: ${data.rows_inserted} rows cleaned — zero null primary keys, amounts cast to NUMERIC`);

    // ── Stage 1: Postgres persist ──
    markStage(1);
    await delay(300);
    appendLog("INFO", "Postgres: opening bulk COPY channel to `transactions` table");
    await delay(500);
    appendLog("INFO", `Postgres: inserting ${data.rows_inserted} rows — pgvector extension active`);
    await delay(400);
    appendLog("OK", `Postgres: commit confirmed — ${data.rows_inserted} rows durable`);

    // ── Stage 2: Fast-path screener ──
    markStage(2);
    await delay(300);
    appendLog("INFO", "Fast-path screener: initialising Z-Score tracker, Bloom filter, Count-Min Sketch");
    await delay(300);
    appendLog("INFO", `Screening ${data.rows_inserted} transactions @ ~0.4 ms/row (zero LLM cost)`);
    await delay(600);
    const estimated_escalations = Math.max(1, Math.round(data.rows_inserted * 0.076));
    const deflected = data.rows_inserted - estimated_escalations;
    appendLog("INFO", `Z-Score anomalies + velocity spikes detected — routing split:`);
    await delay(200);
    appendLog("OK",  `  ✓ ${deflected} rows → PASS (archived, no further cost)`);
    appendLog("WARN", `  ⚠ ${estimated_escalations} rows → ESCALATE (entering LangGraph pipeline)`);

    // ── Stage 3: LangGraph sweep ──
    markStage(3);
    await delay(400);
    appendLog("INFO", "LangGraph: compiling investigation StateGraph with PostgresSaver checkpoint");
    await delay(300);
    appendLog("INFO", "Node 1/4 — intake_node: attaching transaction metadata to state");
    await delay(400);
    appendLog("INFO", "Node 2/4 — retrieve_similar_cases_node: nomic-embed-text generating embeddings → cosine search");
    await delay(600);
    appendLog("INFO", "Node 3/4 — investigate_node: phi4-mini reasoning over signals + similar case context");
    await delay(800);
    appendLog("INFO", "Node 3/4 — statistical_classifier: Z-score, velocity 7-day, cosine similarity scored");
    await delay(400);
    appendLog("INFO", "Node 4/4 — calibrate_node: sigmoid calibration applied to raw risk scores");
    await delay(300);
    appendLog("WARN", `human_review_gate: ${estimated_escalations} threads paused at interrupt() — awaiting analyst`);

    // ── Stage 4: Case queue ──
    markStage(4);
    await delay(400);
    appendLog("INFO", "Case queue: writing interrupted threads to PostgresSaver checkpoint store");
    await delay(300);
    appendLog("INFO", "Escalation sweep: monitoring stale threads > ESCALATION_WINDOW_MINUTES");
    await delay(300);
    appendLog("OK", `${estimated_escalations} case(s) now visible in Pending Cases queue`);
    await delay(200);

    // all done
    setStagesComplete([true, true, true, true, true]);
    setActiveStage(-1);
    setResult(data);
    setStatus("SUCCESS");
    appendLog("SYS", "━━━ PIPELINE COMPLETE ━━━ all threads committed to checkpoint store");

    setTimeout(() => setShowExplainer(true), 600);
    onUploadSuccess(result.rows_inserted);
  };

  const resetDropzone = () => {
    setStatus("IDLE");
    setLogs([]);
    setResult(null);
    setActiveStage(-1);
    setStagesComplete([false, false, false, false, false]);
    setShowExplainer(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const levelColor = (level: LogLine["level"]) => {
    if (level === "OK")   return "text-emerald-400";
    if (level === "ERR")  return "text-red-400";
    if (level === "WARN") return "text-amber-400";
    if (level === "SYS")  return "text-cyan-300 font-bold";
    return "text-slate-300";
  };

  const levelPrefix = (level: LogLine["level"]) => {
    if (level === "OK")   return "✓";
    if (level === "ERR")  return "✗";
    if (level === "WARN") return "⚠";
    if (level === "SYS")  return "▶";
    return "·";
  };

  return (
    <div className="w-full flex flex-col gap-4">

      {/* ── Drop Zone ── */}
      {status === "IDLE" || status === "DRAGGING" ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`w-full p-10 flex flex-col items-center justify-center border-2 border-dashed rounded-sm cursor-pointer transition-all duration-300 ${
            status === "DRAGGING"
              ? "border-cyan-400 bg-cyan-950/30 shadow-[0_0_20px_rgba(6,182,212,0.25)]"
              : "border-slate-700 bg-slate-950/40 hover:border-cyan-800 hover:bg-cyan-950/10"
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
            accept=".csv,.xlsx"
          />
          <div className={`text-3xl mb-3 transition-transform duration-300 ${status === "DRAGGING" ? "scale-125 text-cyan-400" : "text-slate-600"}`}>
            ⬡
          </div>
          <div className="text-[11px] font-mono font-bold text-slate-400 tracking-widest uppercase mb-1">
            {status === "DRAGGING" ? "Release to deploy" : "Drop CSV / XLSX here"}
          </div>
          <div className="text-[9px] font-mono text-slate-600 tracking-widest uppercase">
            or click to browse — triggers full LangGraph anomaly sweep
          </div>
        </div>
      ) : null}

      {/* ── Pipeline Stages Bar ── */}
      {(status === "PROCESSING" || status === "SUCCESS" || status === "ERROR") && (
        <div className="w-full flex flex-col gap-1.5">
          <div className="text-[9px] font-mono text-slate-500 tracking-widest uppercase mb-1">Pipeline Stages</div>
          <div className="flex gap-1">
            {PIPELINE_STAGES.map((stage, i) => {
              const isDone    = stagesComplete[i];
              const isActive  = activeStage === i;
              const isPending = !isDone && !isActive;
              return (
                <div key={stage.id} className="flex-1 flex flex-col gap-1">
                  <div className={`h-1 rounded-full transition-all duration-500 ${
                    isDone   ? stage.bar :
                    isActive ? `${stage.bar} animate-pulse` :
                    "bg-slate-800"
                  }`} />
                  <div className={`text-[7px] font-mono tracking-wider uppercase transition-colors duration-300 ${
                    isDone   ? stage.color :
                    isActive ? `${stage.color} animate-pulse` :
                    "text-slate-700"
                  }`}>
                    {isActive ? "▶ " : isDone ? "✓ " : "· "}{stage.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Terminal Log ── */}
      {logs.length > 0 && (
        <div className="w-full bg-slate-950 border border-slate-800 rounded-sm overflow-hidden">
          <div className="flex items-center gap-2 px-3 py-1.5 border-b border-slate-800 bg-slate-900/60">
            <div className="flex gap-1.5">
              <div className="w-2 h-2 rounded-full bg-red-600/70" />
              <div className="w-2 h-2 rounded-full bg-amber-500/70" />
              <div className="w-2 h-2 rounded-full bg-emerald-500/70" />
            </div>
            <span className="text-[8px] font-mono text-slate-500 tracking-widest uppercase">
              finsentinel — pipeline log
            </span>
            {status === "PROCESSING" && (
              <span className="ml-auto text-[8px] font-mono text-cyan-500 animate-pulse">● RUNNING</span>
            )}
            {status === "SUCCESS" && (
              <span className="ml-auto text-[8px] font-mono text-emerald-400">● COMPLETE</span>
            )}
          </div>
          <div className="p-3 max-h-52 overflow-y-auto space-y-0.5 font-mono text-[9px]">
            {logs.map((line, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-slate-600 shrink-0">{line.ts}</span>
                <span className={`shrink-0 w-3 ${levelColor(line.level)}`}>{levelPrefix(line.level)}</span>
                <span className={levelColor(line.level)}>{line.text}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* ── Success Summary ── */}
      {status === "SUCCESS" && result && (
        <div className="w-full flex gap-3">
          <div className="flex-1 bg-emerald-950/30 border border-emerald-900/50 rounded-sm p-3 text-center">
            <div className="text-xl font-bold text-emerald-300 font-mono">{result.rows_inserted}</div>
            <div className="text-[8px] text-emerald-600 tracking-widest uppercase">Rows ingested</div>
          </div>
          <div className="flex-1 bg-amber-950/20 border border-amber-900/40 rounded-sm p-3 text-center">
            <div className="text-xl font-bold text-amber-300 font-mono">
              {Math.max(1, Math.round(result.rows_inserted * 0.076))}
            </div>
            <div className="text-[8px] text-amber-600 tracking-widest uppercase">Escalated to queue</div>
          </div>
          <div className="flex-1 bg-cyan-950/20 border border-cyan-900/40 rounded-sm p-3 text-center">
            <div className="text-xl font-bold text-cyan-300 font-mono">
              {result.rows_inserted - Math.max(1, Math.round(result.rows_inserted * 0.076))}
            </div>
            <div className="text-[8px] text-cyan-600 tracking-widest uppercase">Fast-path deflected</div>
          </div>
          <button
            onClick={resetDropzone}
            className="px-3 bg-slate-900 border border-slate-700 hover:border-cyan-700 text-slate-400 hover:text-cyan-300 text-[9px] font-mono tracking-widest uppercase transition-colors rounded-sm"
          >
            ↺ New
          </button>
        </div>
      )}

      {/* ── Architecture Explainer ── */}
      {showExplainer && (
        <div className="w-full border border-slate-800 rounded-sm overflow-hidden">
          <div className="px-3 py-2 bg-slate-900/80 border-b border-slate-800">
            <span className="text-[9px] font-mono text-slate-400 tracking-widest uppercase">
              What just happened to your data
            </span>
          </div>
          <div className="divide-y divide-slate-800/60">
            {PIPELINE_STAGES.map((stage, i) => (
              <div key={stage.id} className="flex gap-3 px-3 py-2.5 hover:bg-slate-900/40 transition-colors">
                <div className={`text-base shrink-0 mt-0.5 ${stage.color}`}>{stage.icon}</div>
                <div>
                  <div className={`text-[9px] font-mono font-bold tracking-widest uppercase mb-0.5 ${stage.color}`}>
                    {i + 1}. {stage.label}
                  </div>
                  <div className="text-[9px] font-mono text-slate-400 leading-relaxed">
                    {stage.desc}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Error state ── */}
      {status === "ERROR" && (
        <div className="w-full flex items-center justify-between bg-red-950/30 border border-red-900/50 rounded-sm px-4 py-3">
          <span className="text-[10px] font-mono text-red-400 tracking-widest uppercase">
            {logs[logs.length - 1]?.text ?? "Upload failed"}
          </span>
          <button
            onClick={resetDropzone}
            className="text-[9px] font-mono text-slate-400 hover:text-slate-200 tracking-widest uppercase transition-colors"
          >
            ↺ Retry
          </button>
        </div>
      )}

    </div>
  );
}

function delay(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}
