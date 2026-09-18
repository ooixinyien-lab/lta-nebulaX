import React, { useMemo } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw, Activity, MapPin } from "lucide-react";
import { getWeekDateRange } from "../../network/mapModel";

export default function WeekStatusBar({
  week = 1,
  startDate = "2027-01-04",
  occupancy,
  occLoading = false,
  occError = null,
  onRetry,
}) {
  const dateRangeStr = getWeekDateRange(startDate, week);

  const activeCount = occupancy?.activeActivities?.length || 0;
  const locationKeys = occupancy?.locationOccupancy ? Object.keys(occupancy.locationOccupancy) : [];
  const occupiedCount = locationKeys.length;

  const alertCount = useMemo(() => {
    if (!occupancy?.locationOccupancy) return 0;
    let count = 0;
    for (const loc of Object.values(occupancy.locationOccupancy)) {
      if ((loc.peakOccupiedGroupCount || 0) > (loc.supplyCapacity || 0)) {
        count++;
      }
    }
    return count;
  }, [occupancy]);

  const isAvailable = occupancy?.available !== false;

  // 1. Error state banner
  if (occError) {
    return (
      <div className="w-full max-w-[1060px] mx-auto mb-2.5 px-4 py-2 bg-rose-950/70 border border-rose-800 rounded-xl flex items-center justify-between text-xs text-rose-200">
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-rose-400 shrink-0" />
          <span>Failed to load occupancy data for Week {week}: {occError}</span>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-1 bg-rose-900/80 hover:bg-rose-800 text-white font-bold px-2.5 py-1 rounded-lg transition"
          >
            <RefreshCw size={12} />
            <span>Retry</span>
          </button>
        )}
      </div>
    );
  }

  // 2. Unavailable scenario output banner
  if (!isAvailable) {
    return (
      <div className="w-full max-w-[1060px] mx-auto mb-2.5 px-4 py-2 bg-amber-950/60 border border-amber-800/80 rounded-xl flex items-center justify-between text-xs text-amber-200">
        <div className="flex items-center gap-2">
          <AlertTriangle size={14} className="text-amber-400 shrink-0" />
          <span>
            {occupancy?.reason || `No schedule output available for this scenario. Showing corridor topology only.`}
          </span>
        </div>
        <span className="text-[11px] font-mono text-amber-300">Topology Only</span>
      </div>
    );
  }

  // 3. Normal weekly operational status
  return (
    <div className="w-full max-w-[1060px] mx-auto mb-2.5 px-4 py-1.5 bg-slate-900/90 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-2 text-xs font-mono shadow-sm">
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="font-bold text-cyan-300 font-sans text-[13px]">
          Week {week}
        </span>
        <span className="text-slate-600">·</span>
        <span className="text-slate-400">{dateRangeStr}</span>
        <span className="text-slate-600">·</span>

        {activeCount > 0 ? (
          <>
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <Activity size={12} />
              <span>{activeCount} {activeCount === 1 ? "activity" : "activities"} active</span>
            </span>
            <span className="text-slate-600">·</span>
            <span className="flex items-center gap-1 text-slate-300">
              <MapPin size={12} className="text-cyan-400" />
              <span>{occupiedCount} locations occupied</span>
            </span>
          </>
        ) : (
          <span className="text-slate-400 italic">No scheduled possessions</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        {alertCount > 0 ? (
          <span className="flex items-center gap-1 text-rose-400 font-bold bg-rose-950/60 border border-rose-800/80 px-2 py-0.5 rounded-full text-[11px]">
            <AlertTriangle size={12} />
            <span>{alertCount} capacity {alertCount === 1 ? "alert" : "alerts"}</span>
          </span>
        ) : activeCount > 0 ? (
          <span className="flex items-center gap-1 text-slate-400 text-[11px]">
            <CheckCircle2 size={12} className="text-emerald-400" />
            <span>Normal operations</span>
          </span>
        ) : null}

        {occLoading && (
          <span className="text-[10px] text-cyan-400 animate-pulse font-sans">
            Syncing...
          </span>
        )}
      </div>
    </div>
  );
}
