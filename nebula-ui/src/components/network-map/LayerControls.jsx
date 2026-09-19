import React from "react";
import { Layers } from "lucide-react";

export default function LayerControls({ layers, onToggleLayer }) {
  const layerDefs = [
    {
      key: "core",
      label: "Core Work",
      symbol: (
        <span className="w-3 h-1.5 bg-cyan-400 rounded-xs inline-block shadow-sm" />
      ),
    },
    {
      key: "buffers",
      label: "Safety Buffers",
      symbol: (
        <span className="w-3 h-1.5 border-b-2 border-dashed border-amber-400 inline-block" />
      ),
    },
    {
      key: "mirrored",
      label: "Opposite Mirrored",
      symbol: (
        <span className="w-3 h-2 bg-orange-500/30 border border-orange-500 inline-block rounded-xs" />
      ),
    },
    {
      key: "crossLine",
      label: "Cross-Line",
      symbol: (
        <span className="w-3 h-1.5 bg-purple-400 rounded-xs inline-block shadow-sm" />
      ),
    },
    {
      key: "capacity",
      label: "Capacity Alerts",
      symbol: (
        <span className="w-2.5 h-2.5 rounded-full border border-rose-500 bg-rose-500/40 inline-flex items-center justify-center text-[8px] font-bold text-rose-200">
          !
        </span>
      ),
    },
    {
      key: "maintenance",
      label: "Maintenance Work",
      symbol: <span className="w-3 h-2 bg-amber-400/80 border border-amber-200 inline-block rounded-xs" />,
    },
  ];

  return (
    <div className="relative flex items-center gap-2 flex-nowrap">
      <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold uppercase tracking-wider pr-1">
        <Layers size={13} className="text-slate-400" />
        <span>Layers:</span>
      </div>

      <div className="flex items-center gap-2 flex-wrap flex-1 min-w-0">
        {layerDefs.map((def) => {
          const isActive = layers[def.key];
          return (
            <label
              key={def.key}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium cursor-pointer transition border select-none ${
                isActive
                  ? "bg-slate-800 border-slate-600 text-slate-100 shadow-sm"
                  : "bg-slate-950/60 border-slate-800/80 text-slate-500 opacity-60 hover:opacity-90"
              }`}
              title={`Toggle ${def.label} overlay`}
            >
              <input
                type="checkbox"
                checked={isActive}
                onChange={() => onToggleLayer(def.key)}
                className="w-3.5 h-3.5 rounded bg-slate-900 border-slate-600 text-cyan-500 focus:ring-0 cursor-pointer accent-cyan-400"
                aria-label={def.label}
              />
              {def.symbol}
              <span>{def.label}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
