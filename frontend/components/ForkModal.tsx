"use client";

import { useState } from "react";
import { X, GitBranch, Play } from "lucide-react";

interface ForkModalProps {
  isOpen: boolean;
  onClose: () => void;
  checkpointId: string;
  threadId: string;
  initialState: any;
  onForked: (newThreadId: string) => void;
}

export function ForkModal({ isOpen, onClose, checkpointId, threadId, initialState, onForked }: ForkModalProps) {
  const [jsonText, setJsonText] = useState(JSON.stringify(initialState, null, 2));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFork = async () => {
    try {
      setError(null);
      const parsedState = JSON.parse(jsonText);
      setLoading(true);

      const res = await fetch(`http://localhost:8000/cases/${threadId}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          checkpoint_id: checkpointId,
          overrides: parsedState
        })
      });

      if (!res.ok) {
        throw new Error(`Server error: ${await res.text()}`);
      }

      const data = await res.json();
      onForked(data.new_thread_id);
    } catch (err: any) {
      setError(err.message || "Invalid JSON or network error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-3xl flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-slate-800 bg-slate-800/50">
          <div className="flex items-center gap-2 text-brand-blue">
            <GitBranch className="w-5 h-5" />
            <h3 className="font-mono font-bold text-slate-200">Fork Execution State</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col gap-4">
          <p className="text-sm text-slate-400 font-mono">
            Edit the state dictionary below. When you click Fork, a completely new thread will be created starting from this node using your edited state.
          </p>

          <div className="relative">
            <textarea
              className="w-full h-96 bg-slate-950 border border-slate-800 text-slate-300 font-mono text-sm p-4 rounded focus:outline-none focus:border-brand-blue/50 focus:ring-1 focus:ring-brand-blue/50 transition-all resize-none"
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              spellCheck={false}
            />
            {error && (
              <div className="absolute bottom-4 left-4 right-4 bg-red-900/80 text-red-200 text-xs font-mono p-2 rounded border border-red-800">
                Error: {error}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 font-mono text-sm text-slate-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleFork}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 font-mono text-sm font-bold bg-brand-blue hover:bg-blue-600 text-white rounded transition-colors disabled:opacity-50"
          >
            {loading ? "Forking..." : (
              <>
                <Play className="w-4 h-4" />
                Launch Fork
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
