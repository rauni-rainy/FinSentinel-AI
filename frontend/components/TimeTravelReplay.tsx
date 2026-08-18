"use client";

import { useEffect, useState } from "react";
import { GitBranch, Clock, ArrowRight } from "lucide-react";
import { ForkModal } from "./ForkModal";

interface TimeTravelReplayProps {
  caseId: string;
  onForked: (newThreadId: string) => void;
}

export function TimeTravelReplay({ caseId, onForked }: TimeTravelReplayProps) {
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [forkModalOpen, setForkModalOpen] = useState(false);
  const [selectedCheckpoint, setSelectedCheckpoint] = useState<any>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`http://localhost:8000/cases/${caseId}/history`)
      .then(res => res.json())
      .then(data => {
        // LangGraph history is usually returned in reverse chronological order, let's reverse it to chronological if so
        const sorted = [...data].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
        setHistory(sorted);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [caseId]);

  const handleOpenFork = (h: any) => {
    setSelectedCheckpoint(h);
    setForkModalOpen(true);
  };

  if (loading) {
    return <div className="text-slate-500 font-mono text-sm p-4 animate-pulse">Loading execution history...</div>;
  }

  if (history.length === 0) {
    return <div className="text-slate-500 font-mono text-sm p-4">No history found for this thread.</div>;
  }

  return (
    <div className="flex flex-col h-full bg-slate-900 border-l border-slate-800 overflow-y-auto">
      <div className="p-4 border-b border-slate-800 bg-slate-950 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-brand-blue" />
          <h3 className="text-sm font-bold tracking-widest text-slate-300 uppercase">Time-Travel Replay</h3>
        </div>
      </div>

      <div className="p-6 relative">
        {/* Vertical line connecting nodes */}
        <div className="absolute top-6 bottom-6 left-10 w-0.5 bg-slate-800"></div>

        <div className="flex flex-col gap-8 relative z-10">
          {history.map((h, i) => (
            <div key={h.checkpoint_id} className="flex gap-6 group">
              {/* Dot */}
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-950 border-2 border-brand-blue flex items-center justify-center text-xs font-bold text-brand-blue font-mono shadow-[0_0_10px_rgba(30,136,229,0.3)]">
                {i + 1}
              </div>

              {/* Content */}
              <div className="flex-1 bg-slate-800/40 border border-slate-700/50 rounded-lg p-4 transition-colors hover:bg-slate-800/80 hover:border-slate-600">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="font-mono text-xs text-slate-500 mb-1">
                      {new Date(h.created_at).toLocaleTimeString()}
                    </div>
                    <h4 className="font-mono text-sm font-bold text-brand-blue">
                      {h.source === 'loop' ? h.step : h.source || 'input'}
                    </h4>
                  </div>
                  <button
                    onClick={() => handleOpenFork(h)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-brand-blue text-slate-300 hover:text-white rounded text-xs font-mono font-bold transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <GitBranch className="w-3 h-3" />
                    Fork Here
                  </button>
                </div>

                {/* State preview snippet */}
                <div className="bg-slate-950 border border-slate-800 rounded p-3 overflow-hidden relative">
                  <pre className="text-[10px] text-slate-400 font-mono max-h-24 overflow-hidden">
                    {JSON.stringify(h.values, null, 2)}
                  </pre>
                  <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-slate-950 to-transparent"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedCheckpoint && (
        <ForkModal
          isOpen={forkModalOpen}
          onClose={() => setForkModalOpen(false)}
          checkpointId={selectedCheckpoint.checkpoint_id}
          threadId={caseId}
          initialState={selectedCheckpoint.values}
          onForked={(newId) => {
            setForkModalOpen(false);
            onForked(newId);
          }}
        />
      )}
    </div>
  );
}
