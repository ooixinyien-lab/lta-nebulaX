import React from 'react';
import { Layers, Activity, Calendar, GitCompare } from 'lucide-react';

export default function ChatContextBar({ context }) {
  const { runId, baselineRunId, scenario, selectedActivityId, selectedLocationId, selectedWeek } = context || {};
  const isMock = Boolean(runId && (runId.startsWith('mock') || runId === 'sample_run' || runId === 'sample-run'));
  const isDatabase = Boolean(runId && !isMock);

  return (
    <div className="bg-slate-950/90 border-b border-slate-800/80 px-4 py-2 flex flex-wrap items-center gap-2 text-[11px] font-mono text-slate-300">
      <div className="flex items-center gap-1 text-cyan-400">
        <Layers size={13} />
        <span>Scenario {scenario || 'A'}</span>
      </div>

      <span className="text-slate-600">|</span>

      <div className="flex items-center gap-1 text-slate-300">
        <span className="text-slate-500">Run:</span>
        {isMock ? (
          <span className="text-amber-400 font-semibold">Sample schedule data (Mock)</span>
        ) : isDatabase ? (
          <span className="text-emerald-400 font-semibold" title={runId}>
            {runId.length > 20 ? `${runId.slice(0, 16)}...` : runId} (Database)
          </span>
        ) : (
          <span className="text-slate-400 font-semibold">Active instance (Database)</span>
        )}
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

      {selectedLocationId && (
        <>
          <span className="text-slate-600">|</span>
          <div className="flex items-center gap-1 text-cyan-300 font-bold">
            <span>Loc: {selectedLocationId}</span>
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
