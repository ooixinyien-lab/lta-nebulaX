import React from "react";

export default function MapTooltip({ tooltip }) {
  if (!tooltip || !tooltip.visible) return null;

  return (
    <div
      className="map-tooltip"
      style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
    >
      <div className="font-bold text-xs text-cyan-300">{tooltip.title}</div>
      {tooltip.subtitle && (
        <div className="text-[11px] text-slate-300">{tooltip.subtitle}</div>
      )}
      {tooltip.extra && (
        <div className="text-[10px] text-slate-400 mt-1 font-mono border-t border-slate-700/60 pt-1">
          {tooltip.extra}
        </div>
      )}
    </div>
  );
}
