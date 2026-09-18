import React from "react";
import {
  AlertCircle,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Info,
  X,
  ArrowRight,
  ChevronRight,
} from "lucide-react";
import { resolveLocationDetails, findNextScheduledWeek } from "../../network/mapModel";

export default function NetworkInspector({
  selectedEntity,
  occupancy,
  activities = [],
  currentWeek = 1,
  onSelectActivity,
  onClose,
  onJumpToWeek,
}) {
  if (!selectedEntity) {
    return null;
  }

  const { type, id } = selectedEntity;
  const activeExplanations = (occupancy?.protection?.explanations || []).filter(
    (exp) => exp.locationId === id || (type === "station" && exp.locationId.includes(id))
  );

  // 1. ACTIVITY INSPECTION
  if (type === "activity") {
    const act = activities.find((a) => a.activityId === id);
    if (!act) return null;
    const isScheduledThisWeek = (occupancy?.activeActivities || []).includes(id);
    const nextWeek = findNextScheduledWeek(act.scheduledWeeks, currentWeek);

    return (
      <aside className="network-inspector-panel">
        <div className="inspector-card">
          <div className="inspector-head">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Activity Inspection
              </span>
              <h3 className="text-base font-bold text-cyan-400">{act.activityId}</h3>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`inspector-badge ${
                  act.natureOfActivity === "Live" ? "badge-alp" : "badge-bet"
                }`}
              >
                {act.natureOfActivity}
              </span>
              {onClose && (
                <button
                  onClick={onClose}
                  className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
                  title="Close Inspector"
                  aria-label="Close Inspector"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          <div className="text-xs space-y-1.5 font-mono text-slate-300">
            <div>Contract: <strong className="text-slate-100">{act.contractNumber}</strong></div>
            <div>Type: <span className="text-slate-200">{act.activityType}</span></div>
            <div>Priority: <span className="text-amber-400">Activity P{act.activityPriority} / Contract P{act.contractPriority}</span></div>
            <div>Planned Start: <span className="text-slate-300">{act.plannedStartDate}</span></div>
            <div>Total Accesses: <span className="text-slate-300">{act.totalAccesses}</span></div>
          </div>

          {/* Schedule Status Banner (Item 2) */}
          <div
            className={`p-3 rounded-lg border text-xs ${
              isScheduledThisWeek
                ? "bg-emerald-950/40 border-emerald-700/80 text-emerald-300"
                : "bg-slate-900 border-amber-800/60 text-slate-300"
            }`}
          >
            {isScheduledThisWeek ? (
              <div className="flex items-center gap-1.5 font-semibold text-emerald-300">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span>Scheduled &amp; Active in Week {currentWeek}</span>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 font-medium text-amber-300">
                  <Info size={14} className="text-amber-400 shrink-0" />
                  <span>Not scheduled in Week {currentWeek}</span>
                </div>
                {nextWeek && onJumpToWeek && (
                  <button
                    onClick={() => onJumpToWeek(nextWeek)}
                    className="flex items-center gap-1.5 text-xs bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 px-2.5 py-1 rounded border border-amber-500/40 transition font-mono w-full justify-center font-bold"
                  >
                    <span>Jump to Scheduled Week (Week {nextWeek})</span>
                    <ArrowRight size={13} />
                  </button>
                )}
              </div>
            )}
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">Footprint Profile</h4>
            <div className="text-[11px] space-y-1 text-slate-300 font-mono bg-slate-950 p-2.5 rounded-lg border border-slate-800">
              <div>Core Locations: <strong className="text-cyan-400">{act.coreLocations?.length || 0}</strong></div>
              <div>Buffer Locations: <strong className="text-amber-400">{act.bufferLocations?.length || 0}</strong></div>
              <div>Mirrored Locations: <strong className="text-orange-400">{act.mirroredLocations?.length || 0}</strong></div>
              <div>Cross-Line Locations: <strong className="text-purple-400">{act.crossLineLocations?.length || 0}</strong></div>
            </div>
          </div>
        </div>
      </aside>
    );
  }

  // 2. STATION INSPECTION (Item 1: Decomposed EB & WB Platform capacities)
  const meta = resolveLocationDetails(id);
  const isDirectPlatform = id.startsWith("PLAT:");

  if (meta.type === "station" && !isDirectPlatform) {
    const lineCode = meta.lineCode || "ALP";
    const stnId = meta.stationId;
    const ebPlatId = `PLAT:${lineCode}:${stnId}:EB`;
    const wbPlatId = `PLAT:${lineCode}:${stnId}:WB`;
    const ebOcc = occupancy?.locationOccupancy?.[ebPlatId];
    const wbOcc = occupancy?.locationOccupancy?.[wbPlatId];

    const ebSupply = ebOcc?.supplyCapacity ?? 2;
    const ebPeak = ebOcc?.peakOccupiedGroupCount ?? 0;
    const ebOver = ebOcc?.capacityExceeded ?? (ebPeak > ebSupply);

    const wbSupply = wbOcc?.supplyCapacity ?? 2;
    const wbPeak = wbOcc?.peakOccupiedGroupCount ?? 0;
    const wbOver = wbOcc?.capacityExceeded ?? (wbPeak > wbSupply);

    const allStationActivities = [
      ...new Set([
        ...(ebOcc?.activeActivities || []),
        ...(wbOcc?.activeActivities || []),
      ]),
    ];

    const stationProtections = (occupancy?.protection?.explanations || []).filter(
      (exp) => exp.locationId === ebPlatId || exp.locationId === wbPlatId
    );

    return (
      <aside className="network-inspector-panel">
        <div className="inspector-card">
          <div className="inspector-head">
            <div>
              <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                Station Inspection
              </span>
              <h3 className="text-base font-bold text-slate-100">
                Station {stnId} · Line {lineCode === "ALP" ? "Alpha" : "Beta"}
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`inspector-badge ${
                  lineCode === "ALP" ? "badge-alp" : "badge-bet"
                }`}
              >
                {lineCode} {meta.isInterchange ? "• Interchange" : ""}
              </span>
              {onClose && (
                <button
                  onClick={onClose}
                  className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
                  title="Close Inspector"
                  aria-label="Close Inspector"
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          {/* EB Platform Card */}
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-sky-400">EB Platform</span>
              <span className="text-[11px] font-mono text-slate-400">
                PLAT:{lineCode}:{stnId}:EB
              </span>
            </div>
            <div className={`capacity-meter ${ebOver ? "alert" : ""}`}>
              <span>Possession Groups:</span>
              <span className="font-bold text-sm">[{ebPeak} / {ebSupply}]</span>
            </div>
            {ebOver && (
              <div className="text-[11px] text-rose-400 font-bold flex items-center gap-1 bg-rose-950/40 p-1.5 rounded border border-rose-800">
                <AlertCircle size={13} />
                <span>EB Platform Capacity Exceeded!</span>
              </div>
            )}
            {ebOcc?.coShareGroups && ebOcc.coShareGroups.length > 0 ? (
              <div className="text-xs text-slate-300 font-mono">
                {ebOcc.coShareGroups.map((grp, idx) => (
                  <div key={idx} className="flex items-center justify-between text-[11px] pt-1">
                    <span className="text-slate-400">Group {grp.group}:</span>
                    <span className={grp.isCompliant ? "text-emerald-400" : "text-rose-400"}>
                      {grp.isCompliant ? "Legal Mix" : "Illegal Mix"} ({grp.activities.length} acts)
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] text-slate-500 italic">No EB bookings this week.</div>
            )}
          </div>

          {/* WB Platform Card */}
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-bold text-xs text-sky-400">WB Platform</span>
              <span className="text-[11px] font-mono text-slate-400">
                PLAT:{lineCode}:{stnId}:WB
              </span>
            </div>
            <div className={`capacity-meter ${wbOver ? "alert" : ""}`}>
              <span>Possession Groups:</span>
              <span className="font-bold text-sm">[{wbPeak} / {wbSupply}]</span>
            </div>
            {wbOver && (
              <div className="text-[11px] text-rose-400 font-bold flex items-center gap-1 bg-rose-950/40 p-1.5 rounded border border-rose-800">
                <AlertCircle size={13} />
                <span>WB Platform Capacity Exceeded!</span>
              </div>
            )}
            {wbOcc?.coShareGroups && wbOcc.coShareGroups.length > 0 ? (
              <div className="text-xs text-slate-300 font-mono">
                {wbOcc.coShareGroups.map((grp, idx) => (
                  <div key={idx} className="flex items-center justify-between text-[11px] pt-1">
                    <span className="text-slate-400">Group {grp.group}:</span>
                    <span className={grp.isCompliant ? "text-emerald-400" : "text-rose-400"}>
                      {grp.isCompliant ? "Legal Mix" : "Illegal Mix"} ({grp.activities.length} acts)
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] text-slate-500 italic">No WB bookings this week.</div>
            )}
          </div>

          {/* Active activities at Station */}
          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">
              Active Activities ({allStationActivities.length})
            </h4>
            {allStationActivities.length > 0 ? (
              <div className="flex items-center gap-1.5 flex-wrap">
                {allStationActivities.map((aid) => (
                  <button
                    key={aid}
                    onClick={() => onSelectActivity(aid)}
                    className="bg-slate-800 hover:bg-slate-700 text-cyan-300 px-2 py-1 rounded text-xs font-mono font-bold transition flex items-center gap-1 border border-slate-700"
                  >
                    <span>{aid}</span>
                    <ChevronRight size={12} className="text-slate-500" />
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic bg-slate-950/40 p-2 rounded border border-slate-800">
                No active possession activities at this station in Week {currentWeek}.
              </p>
            )}
          </div>

          {/* Protection Affecting Station */}
          {stationProtections.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase text-purple-400 mb-1.5 flex items-center gap-1.5">
                <ShieldAlert size={14} />
                <span>Protections Affecting Station ({stationProtections.length})</span>
              </h4>
              <div className="space-y-1.5">
                {stationProtections.map((exp, idx) => (
                  <div key={idx} className="protection-alert-box text-xs">
                    <div className="font-bold capitalize">{exp.type} Protection</div>
                    <div className="text-[11px] text-purple-200 mt-0.5">{exp.reason}</div>
                    <button
                      onClick={() => onSelectActivity(exp.activityId)}
                      className="text-[10px] text-cyan-400 hover:underline mt-1 inline-block"
                    >
                      View Triggering Activity {exp.activityId}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>
    );
  }

  // 3. SECTOR OR DIRECT PLATFORM INSPECTION (Item 12)
  const locationOcc = occupancy?.locationOccupancy?.[id];
  const supply = locationOcc?.supplyCapacity ?? 2;
  const peakOccupied = locationOcc?.peakOccupiedGroupCount ?? 0;
  const isOverCapacity = locationOcc?.capacityExceeded ?? (peakOccupied > supply);

  return (
    <aside className="network-inspector-panel">
      <div className="inspector-card">
        <div className="inspector-head">
          <div>
            <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              {meta.type.toUpperCase()}
            </span>
            <h3 className="text-sm font-bold text-slate-100">{meta.label}</h3>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`inspector-badge ${
                meta.lineCode === "ALP" ? "badge-alp" : "badge-bet"
              }`}
            >
              {meta.lineCode} • {meta.bound}
            </span>
            {onClose && (
              <button
                onClick={onClose}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
                title="Close Inspector"
                aria-label="Close Inspector"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Operational Status Badge */}
        <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs">
          <span className="text-slate-400 font-medium">Operational Status:</span>
          {isOverCapacity ? (
            <span className="text-rose-400 font-bold flex items-center gap-1">
              <AlertCircle size={14} /> Capacity Exceeded
            </span>
          ) : peakOccupied > 0 ? (
            <span className="text-cyan-400 font-bold flex items-center gap-1">
              <CheckCircle2 size={14} /> Active Occupancy
            </span>
          ) : (
            <span className="text-emerald-400 font-bold flex items-center gap-1">
              <CheckCircle2 size={14} /> Clear (No Bookings)
            </span>
          )}
        </div>

        {/* Capacity Section */}
        <div>
          <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">
            Capacity Utilization (Week {currentWeek})
          </h4>
          <div className={`capacity-meter ${isOverCapacity ? "alert" : ""}`}>
            <span>Possession Groups:</span>
            <span className="font-bold text-sm">
              [{peakOccupied} / {supply}]
            </span>
          </div>

          {isOverCapacity && (
            <div className="flex items-center gap-1.5 text-rose-400 text-xs font-semibold mt-1.5 bg-rose-950/40 p-2 rounded border border-rose-800">
              <AlertCircle size={14} />
              <span>Capacity Exceeded: Peak {peakOccupied} groups exceeds supply {supply}!</span>
            </div>
          )}
        </div>

        {/* Active Co-share Groups */}
        <div>
          <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">
            Co-Share Groups ({locationOcc?.coShareGroups?.length || 0})
          </h4>

          {locationOcc && locationOcc.coShareGroups?.length > 0 ? (
            <div className="space-y-2">
              {locationOcc.coShareGroups.map((grp, idx) => (
                <div
                  key={idx}
                  className="bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs font-mono space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-cyan-400 font-bold">Group: {grp.group}</span>
                    {grp.isCompliant ? (
                      <span className="text-emerald-400 flex items-center gap-1 text-[10px] font-bold">
                        <CheckCircle2 size={12} /> Legal Mix
                      </span>
                    ) : (
                      <span className="text-rose-400 flex items-center gap-1 text-[10px] font-bold">
                        <XCircle size={12} /> Illegal Mix
                      </span>
                    )}
                  </div>
                  <div className="text-slate-400 text-[11px]">
                    Mix: {grp.pmCount} PM, {grp.pcCount} PC, {grp.cCount} C (Total {grp.activities.length})
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap pt-1">
                    {grp.activities.map((aid) => (
                      <button
                        key={aid}
                        onClick={() => onSelectActivity(aid)}
                        className="bg-slate-800 hover:bg-slate-700 text-cyan-300 px-1.5 py-0.5 rounded text-[10px] transition"
                      >
                        {aid}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic bg-slate-950/50 p-2 rounded border border-slate-800">
              No active possession bookings at this location in Week {currentWeek}.
            </p>
          )}
        </div>

        {/* Protection Explanations */}
        {activeExplanations.length > 0 && (
          <div>
            <h4 className="text-xs font-bold uppercase text-purple-400 mb-1.5 flex items-center gap-1.5">
              <ShieldAlert size={14} />
              <span>Active Protection Overlays</span>
            </h4>
            <div className="space-y-1.5">
              {activeExplanations.map((exp, idx) => (
                <div key={idx} className="protection-alert-box">
                  <div className="font-bold capitalize">{exp.type} Protection</div>
                  <div className="text-[11px] text-purple-200 mt-0.5">{exp.reason}</div>
                  <button
                    onClick={() => onSelectActivity(exp.activityId)}
                    className="text-[10px] text-cyan-400 hover:underline mt-1 inline-block"
                  >
                    View Triggering Activity {exp.activityId}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
