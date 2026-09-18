import React, { useState, useMemo } from "react";
import { Filter, X, ArrowRight, Check } from "lucide-react";
import { findNextScheduledWeek } from "../../network/mapModel";

export default function ActivityFilter({
  activities = [],
  selectedActivityId,
  onSelectActivity,
  activeActivitiesInWeek = [],
  currentWeek = 1,
  onJumpToWeek,
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [activeOnly, setActiveOnly] = useState(false);

  const selectedActivity = useMemo(
    () => activities.find((a) => a.activityId === selectedActivityId),
    [activities, selectedActivityId]
  );

  const isSelectedActiveThisWeek = useMemo(() => {
    if (!selectedActivityId) return false;
    return activeActivitiesInWeek.includes(selectedActivityId);
  }, [selectedActivityId, activeActivitiesInWeek]);

  const nextScheduledWeek = useMemo(() => {
    if (!selectedActivity || isSelectedActiveThisWeek) return null;
    return findNextScheduledWeek(selectedActivity.scheduledWeeks || [], currentWeek);
  }, [selectedActivity, isSelectedActiveThisWeek, currentWeek]);

  // Group and filter activities
  const { activeList, otherList } = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();

    const matches = (a) => {
      if (!term) return true;
      return (
        a.activityId?.toLowerCase().includes(term) ||
        a.contractNumber?.toLowerCase().includes(term) ||
        a.natureOfActivity?.toLowerCase().includes(term) ||
        a.activityType?.toLowerCase().includes(term) ||
        a.lineCode?.toLowerCase().includes(term) ||
        a.bound?.toLowerCase().includes(term)
      );
    };

    const active = [];
    const other = [];

    for (const a of activities) {
      if (!matches(a)) continue;
      const isActive = activeActivitiesInWeek.includes(a.activityId);
      if (isActive) {
        active.push(a);
      } else if (!activeOnly) {
        other.push(a);
      }
    }

    return { activeList: active, otherList: other };
  }, [activities, activeActivitiesInWeek, searchTerm, activeOnly]);

  const totalFiltered = activeList.length + otherList.length;

  return (
    <div className="relative flex items-center gap-2">
      <div className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold uppercase tracking-wider">
        <Filter size={13} className="text-cyan-400" />
        <span>Activity:</span>
      </div>

      <div className="relative">
        {selectedActivity ? (
          <div className="flex items-center gap-2 bg-slate-800 border border-cyan-500/50 rounded-lg px-2.5 py-1 text-xs shadow-sm">
            <span className="font-bold text-cyan-300">{selectedActivity.activityId}</span>
            <span className="text-slate-400 text-[11px] font-mono">({selectedActivity.contractNumber})</span>
            
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                selectedActivity.natureOfActivity === "Live"
                  ? "bg-rose-950 text-rose-300 border border-rose-800"
                  : "bg-slate-900 text-slate-400 border border-slate-700"
              }`}
            >
              {selectedActivity.natureOfActivity}
            </span>

            {/* Active / Inactive badge */}
            <span
              className={`text-[10px] px-2 py-0.5 rounded font-semibold ${
                isSelectedActiveThisWeek
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                  : "bg-amber-950/80 text-amber-300 border border-amber-800"
              }`}
            >
              {isSelectedActiveThisWeek ? `Active W${currentWeek}` : `Inactive W${currentWeek}`}
            </span>

            {/* Jump to Next Week Button if inactive */}
            {!isSelectedActiveThisWeek && nextScheduledWeek != null && onJumpToWeek && (
              <button
                type="button"
                onClick={() => onJumpToWeek(nextScheduledWeek)}
                className="flex items-center gap-1 text-[10px] font-bold bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-700 px-2 py-0.5 rounded transition"
                title={`Jump to Week ${nextScheduledWeek} where ${selectedActivity.activityId} is next scheduled`}
              >
                <span>Jump to W{nextScheduledWeek}</span>
                <ArrowRight size={11} />
              </button>
            )}

            <button
              type="button"
              onClick={() => onSelectActivity(null)}
              className="text-slate-400 hover:text-white ml-1 p-0.5 rounded hover:bg-slate-700 transition"
              aria-label="Clear activity focus"
              title="Clear activity focus"
            >
              <X size={13} />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsOpen(!isOpen)}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-750 text-slate-200 px-3 py-1 rounded-lg text-xs border border-slate-700 hover:border-slate-600 transition"
              aria-expanded={isOpen}
            >
              <span>Focus Activity...</span>
              <span className="text-[11px] text-cyan-400 bg-slate-900 px-1.5 py-0.2 rounded font-mono">
                {activeActivitiesInWeek.length} active
              </span>
            </button>

            {/* Quick Active Only Toggle Pill */}
            <button
              type="button"
              onClick={() => {
                setActiveOnly((prev) => !prev);
                setIsOpen(true);
              }}
              className={`flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg border transition ${
                activeOnly
                  ? "bg-emerald-950 text-emerald-300 border-emerald-600 font-semibold"
                  : "bg-slate-800/60 text-slate-400 border-slate-700 hover:text-slate-200"
              }`}
              title="Show only activities active in the current week"
            >
              {activeOnly && <Check size={11} className="text-emerald-400" />}
              <span>Active Only</span>
            </button>
          </div>
        )}

        {isOpen && !selectedActivity && (
          <div className="absolute top-full mt-1.5 left-0 z-[100] w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2.5 flex flex-col gap-2 max-h-96">
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search ID, contract, nature, type..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 placeholder:text-slate-500"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-slate-200 p-1"
                aria-label="Close activity search"
              >
                <X size={14} />
              </button>
            </div>

            <div className="flex items-center justify-between px-1 text-[10px] text-slate-400 font-medium">
              <span>{totalFiltered} activities found</span>
              <button
                type="button"
                onClick={() => setActiveOnly((v) => !v)}
                className={`hover:underline ${activeOnly ? "text-emerald-400 font-bold" : "text-slate-400"}`}
              >
                {activeOnly ? "Showing Active Only" : "Filter: Active Only"}
              </button>
            </div>

            <div className="overflow-y-auto flex-1 flex flex-col gap-1 pr-1 divide-y divide-slate-800/60">
              {/* Group 1: Active this week */}
              {activeList.length > 0 && (
                <div className="pb-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 px-1.5 py-1 flex items-center justify-between">
                    <span>Active This Week ({activeList.length})</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  </div>
                  {activeList.map((act) => (
                    <button
                      key={act.activityId}
                      type="button"
                      onClick={() => {
                        onSelectActivity(act.activityId);
                        setIsOpen(false);
                        setSearchTerm("");
                      }}
                      className="w-full flex items-center justify-between p-1.5 rounded-lg hover:bg-slate-800/80 text-left text-xs transition group"
                    >
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-cyan-300 group-hover:text-cyan-200">
                            {act.activityId}
                          </span>
                          <span className="text-slate-400 text-[11px] font-mono">
                            ({act.contractNumber})
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {act.lineCode} · {act.bound} · {act.natureOfActivity} ({act.activityType})
                        </div>
                      </div>
                      <span className="text-[9px] bg-emerald-950 text-emerald-300 border border-emerald-700 px-1.5 py-0.5 rounded font-mono font-semibold">
                        Active W{currentWeek}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {/* Group 2: Other scheduled activities */}
              {!activeOnly && otherList.length > 0 && (
                <div className="pt-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-1.5 py-1">
                    Other Activities ({otherList.length})
                  </div>
                  {otherList.map((act) => {
                    const nextWk = findNextScheduledWeek(act.scheduledWeeks || [], currentWeek);
                    return (
                      <button
                        key={act.activityId}
                        type="button"
                        onClick={() => {
                          onSelectActivity(act.activityId);
                          setIsOpen(false);
                          setSearchTerm("");
                        }}
                        className="w-full flex items-center justify-between p-1.5 rounded-lg hover:bg-slate-800/80 text-left text-xs transition group opacity-85 hover:opacity-100"
                      >
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-slate-300 group-hover:text-white">
                              {act.activityId}
                            </span>
                            <span className="text-slate-500 text-[11px] font-mono">
                              ({act.contractNumber})
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {act.lineCode} · {act.bound} · {act.natureOfActivity} ({act.activityType})
                          </div>
                        </div>
                        {nextWk != null && (
                          <span className="text-[9px] bg-slate-950 text-slate-400 border border-slate-800 px-1.5 py-0.5 rounded font-mono">
                            Next: W{nextWk}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {activeList.length === 0 && otherList.length === 0 && (
                <div className="p-4 text-center text-xs text-slate-500">
                  No matching activities found.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
