import React from 'react';
import { Layers, Activity, Calendar, GitCompare } from 'lucide-react';

export default function ChatContextBar({ context }) {
  const { runId, baselineRunId, scenario, selectedActivityId, selectedWeek } = context || {};
  const isMock = !runId || runId.startsWith('mock') || runId === 'sample_run' || runId === 'sample-run';

  return (
    <div className="bg-slate-950/90 border-b border-slate-800/80 px-4 py-2 flex flex-wrap items-center gap-2 text-[11px] font-mono text-slate-300">
      <div className="flex items-center gap-1 text-cyan-400">
        <Layers size={13} />
        <span>Scenario {scenario || 'A'}</span>
      </div>

      <span className="text-slate-600">|</span>

      <div className="flex items-center gap-1 text-slate-300">
        <span className="text-slate-500">Run:</span>
        <span className={isMock ? 'text-amber-400 font-semibold' : 'text-slate-200'}>
          {isMock ? 'Sample schedule data (Mock)' : runId}
        </span>
      </div>

      {selectedActivityId && (
        <>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-emerald-400 font-bold">
            <Activity size={12} />
            <span>Activity {selectedActivityId}</span>
          </div>
        </>
      )}

      {selectedWeek && (
        <>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-purple-400">
            <Calendar size={12} />
            <span>Week {selectedWeek}</span>
          </div>
        </>
      )}

      {baselineRunId && (
        <>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-amber-300">
            <GitCompare size={12} />
            <span className="text-slate-500">vs:</span>
            <span>{baselineRunId}</span>
          </div>
        </>
      )}
    </div>
  );
}
