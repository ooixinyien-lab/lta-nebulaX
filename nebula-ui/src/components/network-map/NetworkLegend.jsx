import React from "react";

export default function NetworkLegend() {
  return (
    <div className="flex items-center gap-4 text-xs font-mono text-slate-300 flex-wrap bg-slate-950/60 border border-slate-800/80 px-3 py-2 rounded-lg">
      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-sans">Legend:</span>

      <span className="flex items-center gap-1.5">
        <span className="w-3 h-0.5 bg-cyan-400 inline-block shadow-sm"></span>
        <span>Core Work</span>
      </span>

      <span className="flex items-center gap-1.5">
        <span className="w-3 h-0.5 border-b-2 border-dashed border-amber-400 inline-block"></span>
        <span>Safety Buffer</span>
      </span>

      <span className="flex items-center gap-1.5">
        <span className="w-3 h-2 bg-orange-500/40 border border-orange-500 inline-block"></span>
        <span>Mirrored (Live)</span>
      </span>

      <span className="flex items-center gap-1.5">
        <span className="w-3 h-0.5 bg-purple-500 inline-block"></span>
        <span>Cross-Line (H01/H02)</span>
      </span>

      <span className="flex items-center gap-1.5">
        <span className="w-2.5 h-2.5 rounded-full border border-rose-500 bg-rose-500/30 inline-block"></span>
        <span>Capacity Exceeded</span>
      </span>
    </div>
  );
}
