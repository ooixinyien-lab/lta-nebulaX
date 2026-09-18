import React from "react";
import { Play, Pause, ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { getWeekDateRange } from "../../network/mapModel";

export default function WeeklyScrubber({
  week,
  setWeek,
  horizonWeeks = 30,
  startDate = "2027-01-04",
  isPlaying,
  onTogglePlay,
  weeklySummary = [],
}) {
  const dateRangeStr = getWeekDateRange(startDate, week);

  const handlePrev = () => {
    setWeek((w) => Math.max(1, w - 1));
  };

  const handleNext = () => {
    setWeek((w) => Math.min(horizonWeeks, w + 1));
  };

  const handleSliderChange = (e) => {
    setWeek(Number(e.target.value));
  };

  // Build summary lookup map
  const summaryMap = React.useMemo(() => {
    const map = new Map();
    for (const item of weeklySummary) {
      map.set(item.week, item);
    }
    return map;
  }, [weeklySummary]);

  const currentSummary = summaryMap.get(week);
  const currentActiveCount = currentSummary ? currentSummary.activeCount : 0;

  return (
    <div className="weekly-scrubber-card sticky bottom-0 z-30 shadow-2xl bg-slate-900/95 backdrop-blur-md border-t border-slate-700/80 p-3">
      {/* Top row: Status, playback controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold uppercase tracking-wider">
            <Calendar size={14} className="text-cyan-400" />
            <span>Timeline</span>
          </div>

          <span className="text-xs bg-cyan-950/80 border border-cyan-700/70 px-2.5 py-0.5 rounded-full text-cyan-300 font-mono font-bold">
            Week {week} / {horizonWeeks}
          </span>

          <span className="text-xs text-slate-400 font-medium">
            {dateRangeStr}
          </span>

          <span className="text-[11px] text-slate-500 hidden sm:inline">
            ({currentActiveCount} active {currentActiveCount === 1 ? "activity" : "activities"})
          </span>
        </div>

        {/* Prev / Play / Next Controls */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handlePrev}
            disabled={week <= 1}
            className="scrubber-btn"
            aria-label="Previous week"
            title="Previous week (W-1)"
          >
            <ChevronLeft size={15} />
            <span className="hidden sm:inline">Prev</span>
          </button>

          <button
            type="button"
            onClick={onTogglePlay}
            className="scrubber-btn play-btn font-semibold"
            aria-label={isPlaying ? "Pause timeline playback" : "Play timeline playback"}
            title={isPlaying ? "Pause playback" : "Play timeline"}
          >
            {isPlaying ? (
              <>
                <Pause size={13} />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play size={13} fill="currentColor" />
                <span>Play</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleNext}
            disabled={week >= horizonWeeks}
            className="scrubber-btn"
            aria-label="Next week"
            title="Next week (W+1)"
          >
            <span className="hidden sm:inline">Next</span>
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      {/* 30-Week Dot Indicators & Range Track */}
      <div className="relative pt-1 pb-1">
        {/* Continuous track line */}
        <div className="absolute top-1/2 left-0 right-0 h-1 bg-slate-800 -translate-y-1/2 rounded-full pointer-events-none" />

        {/* 30 Week Interactive Dots */}
        <div className="relative flex justify-between items-center z-10">
          {Array.from({ length: horizonWeeks }, (_, idx) => {
            const w = idx + 1;
            const summary = summaryMap.get(w);
            const hasActivity = summary ? summary.hasActivity : false;
            const activeCount = summary ? summary.activeCount : 0;
            const isCurrent = w === week;

            let dotClass = "bg-slate-700 hover:bg-slate-500 border-slate-600";
            if (hasActivity) {
              dotClass = "bg-emerald-500 hover:bg-emerald-400 border-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)]";
            }
            if (isCurrent) {
              dotClass = "bg-cyan-400 border-white ring-2 ring-cyan-400 ring-offset-2 ring-offset-slate-900 scale-125 z-20";
            }

            return (
              <button
                key={w}
                type="button"
                onClick={() => setWeek(w)}
                className={`w-3 h-3 rounded-full border transition-all duration-150 flex items-center justify-center focus:outline-none ${dotClass}`}
                title={`Week ${w}: ${activeCount} active activities`}
                aria-label={`Jump to Week ${w}`}
              >
                {isCurrent && <span className="w-1 h-1 bg-slate-950 rounded-full" />}
              </button>
            );
          })}
        </div>

        {/* Hidden/accessible native range input over top for sliding & keyboard navigation */}
        <input
          type="range"
          min={1}
          max={horizonWeeks}
          value={week}
          onChange={handleSliderChange}
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-20"
          aria-label="Weekly timeline slider"
        />
      </div>

      {/* Week Labels at key intervals */}
      <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1 px-0.5 select-none">
        <span>W1</span>
        <span>W5</span>
        <span>W10</span>
        <span>W15</span>
        <span>W20</span>
        <span>W25</span>
        <span>W30</span>
      </div>
    </div>
  );
}
