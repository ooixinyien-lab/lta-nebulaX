import React from 'react';
import { HelpCircle, Sparkles } from 'lucide-react';

export default function ChatEmptyState({ context, onSelectPrompt }) {
  const { selectedActivityId, baselineRunId, selectedLocationId, selectedWeek } = context || {};

  const suggestions = [];

  if (selectedActivityId) {
    suggestions.push(`Why was ${selectedActivityId} scheduled here?`);
    if (baselineRunId) {
      suggestions.push(`Why was ${selectedActivityId} moved from baseline?`);
    }
    suggestions.push(`Are there recorded conflicts for ${selectedActivityId}?`);
  } else {
    suggestions.push("What activities are scheduled in Week 1?");
  }

  if (selectedLocationId && selectedWeek) {
    suggestions.push(`What activities use ${selectedLocationId} in week ${selectedWeek}?`);
  }

  suggestions.push("What factors are driving the scenario penalty score?");

  return (
    <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
      <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-3">
        <Sparkles size={24} />
      </div>
      <h4 className="text-sm font-bold text-slate-200 mb-1">How can I explain the schedule?</h4>
      <p className="text-xs text-slate-400 max-w-xs mb-5">
        Ask about activity placements, displacement causes, buffer conflicts, or penalty breakdowns.
      </p>

      <div className="w-full max-w-xs space-y-2 text-left">
        <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
          <HelpCircle size={12} /> Suggested Questions
        </div>
        {suggestions.map((prompt, idx) => (
          <button
            key={idx}
            onClick={() => onSelectPrompt(prompt)}
            className="w-full text-left p-2.5 rounded-lg bg-slate-900 hover:bg-slate-800/80 border border-slate-800 hover:border-cyan-500/40 text-xs text-slate-300 transition block"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
