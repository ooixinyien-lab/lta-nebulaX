import React, { useState, useMemo } from "react";
import { Filter, X } from "lucide-react";


export default function ActivityFilter({
  activities = [],
  selectedActivityId,
  onSelectActivity,
  activeActivitiesInWeek = [],
  currentWeek,
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const selectedActivity = useMemo(
    () => activities.find((a) => a.activityId === selectedActivityId),
    [activities, selectedActivityId]
  );

  const filteredActivities = useMemo(() => {
    if (!searchTerm.trim()) return activities;
    const term = searchTerm.toLowerCase();
    return activities.filter(
      (a) =>
        a.activityId.toLowerCase().includes(term) ||
        a.contractNumber.toLowerCase().includes(term) ||
        a.natureOfActivity.toLowerCase().includes(term) ||
        a.activityType.toLowerCase().includes(term)
    );
  }, [activities, searchTerm]);

  const isSelectedActiveThisWeek = useMemo(() => {
    if (!selectedActivityId) return false;
    return activeActivitiesInWeek.includes(selectedActivityId);
  }, [selectedActivityId, activeActivitiesInWeek]);

  return (
    <div className="relative flex items-center gap-2">
      <div className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold uppercase tracking-wider">
        <Filter size={13} className="text-cyan-400" />
        <span>Activity Focus:</span>
      </div>

      <div className="relative">
        {selectedActivity ? (
          <div className="flex items-center gap-2 bg-slate-800 border border-cyan-500/50 rounded-lg px-2.5 py-1 text-xs">
            <span className="font-bold text-cyan-400">{selectedActivity.activityId}</span>
            <span className="text-slate-400 text-[11px] font-mono">({selectedActivity.contractNumber})</span>
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded font-bold uppercase ${
                selectedActivity.natureOfActivity === "Live"
                  ? "bg-rose-950 text-rose-300 border border-rose-800"
                  : "bg-slate-900 text-slate-400 border border-slate-700"
              }`}
            >
              {selectedActivity.natureOfActivity}
            </span>

            {/* Active / Inactive badge */}
            <span
              className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${
                isSelectedActiveThisWeek
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  : "bg-amber-950 text-amber-300 border border-amber-800"
              }`}
              title={
                isSelectedActiveThisWeek
                  ? `Active in Week ${currentWeek}`
                  : `Not scheduled during Week ${currentWeek}`
              }
            >
              {isSelectedActiveThisWeek ? `Active W${currentWeek}` : `Inactive W${currentWeek}`}
            </span>

            <button
              onClick={() => onSelectActivity(null)}
              className="text-slate-400 hover:text-white ml-1 p-0.5"
              aria-label="Clear activity focus"
              title="Clear focus"
            >
              <X size={13} />
            </button>
          </div>
        ) : (
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1 rounded-lg text-xs border border-slate-700 transition"
          >
            <span>All Activities ({activities.length})</span>
          </button>
        )}

        {isOpen && !selectedActivity && (
          <div className="absolute top-full mt-1 left-0 z-50 w-72 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 flex flex-col gap-2 max-h-80">
            <input
              type="text"
              placeholder="Search by ID, contract, nature..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              autoFocus
            />

            <div className="overflow-y-auto flex-1 flex flex-col gap-1 pr-1">
              {filteredActivities.map((act) => {
                const isActive = activeActivitiesInWeek.includes(act.activityId);
                return (
                  <button
                    key={act.activityId}
                    onClick={() => {
                      onSelectActivity(act.activityId);
                      setIsOpen(false);
                      setSearchTerm("");
                    }}
                    className="flex items-center justify-between p-1.5 rounded-lg hover:bg-slate-800 text-left text-xs transition"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-cyan-400">{act.activityId}</span>
                        <span className="text-slate-400 text-[11px]">({act.contractNumber})</span>
                      </div>
                      <div className="text-[10px] text-slate-500 truncate">
                        {act.natureOfActivity} • {act.activityType}
                      </div>
                    </div>
                    {isActive && (
                      <span className="text-[9px] bg-emerald-950 text-emerald-400 border border-emerald-800 px-1 py-0.5 rounded font-mono">
                        Active W{currentWeek}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
