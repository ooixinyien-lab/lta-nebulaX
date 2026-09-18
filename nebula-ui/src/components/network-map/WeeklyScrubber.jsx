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

  return (
    <div className="weekly-scrubber-card">
      <div className="scrubber-header">
        <div className="flex items-center gap-3">
          <Calendar size={16} className="text-cyan-400" />
          <span className="scrubber-title">Weekly Timeline Scrubber</span>
          <span className="text-xs bg-slate-900 border border-slate-700 px-2 py-0.5 rounded text-cyan-300 font-mono font-bold">
            Week {week} / {horizonWeeks}
          </span>
        </div>

        <div className="scrubber-dates">{dateRangeStr}</div>
      </div>

      <div className="scrubber-controls">
        <button
          onClick={handlePrev}
          disabled={week <= 1}
          className="scrubber-btn"
          aria-label="Previous week"
          title="Previous week (W-1)"
        >
          <ChevronLeft size={16} />
          <span>Prev</span>
        </button>

        <button
          onClick={onTogglePlay}
          className="scrubber-btn play-btn"
          aria-label={isPlaying ? "Pause timeline playback" : "Play timeline playback"}
          title={isPlaying ? "Pause playback" : "Auto-advance weeks (800ms/week)"}
        >
          {isPlaying ? (
            <>
              <Pause size={14} />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play size={14} fill="currentColor" />
              <span>Play</span>
            </>
          )}
        </button>

        <button
          onClick={handleNext}
          disabled={week >= horizonWeeks}
          className="scrubber-btn"
          aria-label="Next week"
          title="Next week (W+1)"
        >
          <span>Next</span>
          <ChevronRight size={16} />
        </button>

        <input
          type="range"
          min={1}
          max={horizonWeeks}
          value={week}
          onChange={handleSliderChange}
          className="scrubber-slider"
          aria-label="Weekly timeline slider"
        />
      </div>
    </div>
  );
}
