import React from "react";
import { Layers } from "lucide-react";

export default function LayerControls({ layers, onToggleLayer }) {
  const layerDefs = [
    { key: "core", label: "Core Work", color: "#06b6d4" },
    { key: "buffers", label: "Buffers", color: "#f59e0b" },
    { key: "mirrored", label: "Opposite Mirrored", color: "#f97316" },
    { key: "crossLine", label: "Cross-Line Protection", color: "#a855f7" },
    { key: "capacity", label: "Capacity Alerts", color: "#ef4444" },
  ];

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-1.5 text-xs text-slate-400 font-semibold uppercase tracking-wider">
        <Layers size={13} />
        <span>Overlays:</span>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        {layerDefs.map((def) => (
          <label key={def.key} className="layer-toggle-label">
            <input
              type="checkbox"
              checked={layers[def.key]}
              onChange={() => onToggleLayer(def.key)}
            />
            <span
              className="w-2.5 h-2.5 rounded-full inline-block"
              style={{ backgroundColor: def.color }}
            />
            <span className="text-xs text-slate-300 font-medium">{def.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
