import React from "react";
import { AlertCircle, ShieldAlert, CheckCircle2, XCircle, Info } from "lucide-react";
import { resolveLocationDetails } from "../../network/mapModel";

export default function NetworkInspector({
  selectedEntity,
  occupancy,
  activities = [],
  currentWeek,
  onSelectActivity,
}) {
  if (!selectedEntity) {
    return (
      <aside className="network-inspector-panel">
        <div className="inspector-card text-center py-10">
          <Info size={32} className="mx-auto text-slate-500 mb-2" />
          <h3 className="text-sm font-bold text-slate-300">Network Inspector</h3>
          <p className="text-xs text-slate-400 mt-1">
            Click any station, platform, or EB/WB sector to inspect capacity, co-sharing, and active protections.
          </p>
        </div>
      </aside>
    );
  }

  const { type, id } = selectedEntity;
  const locationOcc = occupancy?.locationOccupancy?.[id];
  const activeExplanations = (occupancy?.protection?.explanations || []).filter(
    (exp) => exp.locationId === id
  );

  // If entity is an activity
  if (type === "activity") {
    const act = activities.find((a) => a.activityId === id);
    if (!act) return null;
    const isScheduledThisWeek = (occupancy?.activeActivities || []).includes(id);

    return (
      <aside className="network-inspector-panel">
        <div className="inspector-card">
          <div className="inspector-head">
            <div>
              <span className="text-[10px] font-mono text-slate-400">Activity Inspection</span>
              <h3 className="text-base font-bold text-cyan-400">{act.activityId}</h3>
            </div>
            <span
              className={`inspector-badge ${
                act.natureOfActivity === "Live" ? "badge-alp" : "badge-bet"
              }`}
            >
              {act.natureOfActivity}
            </span>
          </div>

          <div className="text-xs space-y-1.5 font-mono text-slate-300">
            <div>Contract: <strong className="text-slate-100">{act.contractNumber}</strong></div>
            <div>Type: <span className="text-slate-200">{act.activityType}</span></div>
            <div>Priority: <span className="text-amber-400">Activity P{act.activityPriority} / Contract P{act.contractPriority}</span></div>
            <div>Planned Start: <span className="text-slate-300">{act.plannedStartDate}</span></div>
            <div>Required Accesses: <span className="text-slate-300">{act.totalAccesses}</span></div>
          </div>

          <div
            className={`p-2.5 rounded-lg border text-xs ${
              isScheduledThisWeek
                ? "bg-emerald-950/40 border-emerald-700/80 text-emerald-300"
                : "bg-slate-900 border-slate-700 text-slate-400"
            }`}
          >
            {isScheduledThisWeek ? (
              <div className="flex items-center gap-1.5 font-semibold">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span>Scheduled &amp; active in Week {currentWeek}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 font-medium">
                <Info size={14} className="text-slate-400" />
                <span>Not scheduled during Week {currentWeek}</span>
              </div>
            )}
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">Footprint Profile</h4>
            <div className="text-[11px] space-y-1 text-slate-300 font-mono bg-slate-950 p-2.5 rounded-lg border border-slate-800">
              <div>Core Locations: <strong className="text-cyan-400">{act.coreLocations.length}</strong></div>
              <div>Buffer Locations: <strong className="text-amber-400">{act.bufferLocations.length}</strong></div>
              <div>Mirrored Locations: <strong className="text-orange-400">{act.mirroredLocations.length}</strong></div>
              <div>Cross-Line Locations: <strong className="text-purple-400">{act.crossLineLocations.length}</strong></div>
            </div>
          </div>
        </div>
      </aside>
    );
  }

  // Station or Sector location inspection
  const meta = resolveLocationDetails(id);
  const supply = locationOcc?.supplyCapacity ?? 2;
  const peakOccupied = locationOcc?.peakOccupiedGroupCount ?? 0;
  const isOverCapacity = locationOcc?.capacityExceeded ?? (peakOccupied > supply);

  return (
    <aside className="network-inspector-panel">
      <div className="inspector-card">
        <div className="inspector-head">
          <div>
            <span className="text-[10px] font-mono text-slate-400">{meta.type.toUpperCase()}</span>
            <h3 className="text-sm font-bold text-slate-100">{meta.label}</h3>
          </div>
          <span
            className={`inspector-badge ${
              meta.lineCode === "ALP" ? "badge-alp" : "badge-bet"
            }`}
          >
            {meta.lineCode} • {meta.bound}
          </span>
        </div>

        {/* Capacity Section */}
        <div>
          <h4 className="text-xs font-bold uppercase text-slate-400 mb-1.5">Capacity Utilization (Week {currentWeek})</h4>
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
