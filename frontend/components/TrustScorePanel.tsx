"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

type TrustMetric = {
  timestamp: string;
  precision: number;
  recall: number;
  false_positive_rate: number;
};

export function TrustScorePanel() {
  const [data, setData] = useState<TrustMetric[]>([]);

  useEffect(() => {
    // We would ideally fetch a timeseries array. The backend `/metrics/trust` currently returns only the latest.
    // For this milestone demo, let's fetch it, but we can also mock historical points to show the Recharts trend.
    fetch("http://localhost:8000/metrics/trust")
      .then((res) => res.json())
      .then((metrics) => {
        if (!Array.isArray(metrics) || metrics.length === 0) return;
        
        const formatted = metrics.map((m: any) => ({
          timestamp: new Date(m.timestamp).toISOString().split("T")[0],
          precision: m.precision,
          recall: m.recall,
          false_positive_rate: m.false_positive_rate
        }));
        
        setData(formatted);
      })
      .catch((err) => console.error(err));
  }, []);

  if (data.length === 0) {
    return <div className="h-full flex items-center justify-center text-slate-500 font-mono text-sm">Loading telemetry...</div>;
  }

  return (
    <div className="h-full w-full bg-slate-950 p-4 flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase">Model Trust Telemetry</h2>
        <div className="flex gap-4 text-xs font-mono">
          <span className="text-brand-blue flex items-center gap-1"><div className="w-2 h-2 bg-brand-blue rounded-full"></div>Precision</span>
          <span className="text-emerald-500 flex items-center gap-1"><div className="w-2 h-2 bg-emerald-500 rounded-full"></div>Recall</span>
          <span className="text-brand-red flex items-center gap-1"><div className="w-2 h-2 bg-brand-red rounded-full"></div>FPR</span>
        </div>
      </div>
      <div className="flex-1 w-full min-h-[150px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis 
              dataKey="timestamp" 
              stroke="#475569" 
              fontSize={10} 
              tickMargin={10} 
              axisLine={false} 
              tickLine={false} 
              tickFormatter={(val) => {
                const parts = val.split("-");
                return parts.length === 3 ? `${parts[1]}-${parts[2]}` : val;
              }}
            />
            <YAxis stroke="#475569" fontSize={10} tickFormatter={(val) => `${(val * 100).toFixed(0)}%`} axisLine={false} tickLine={false} />
            <Tooltip 
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b", fontSize: "12px", fontFamily: "monospace" }}
              itemStyle={{ color: "#f8fafc" }}
              formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, ""]}
            />
            <Line type="monotone" dataKey="precision" stroke="#003366" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            <Line type="monotone" dataKey="recall" stroke="#10b981" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
            <Line type="monotone" dataKey="false_positive_rate" stroke="#B22222" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
