import React from 'react';
import { Calendar, Map, Upload, Plus, Sparkles, Check } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'network_map', label: 'Interactive Network Map', icon: Map },
  { id: 'matrix', label: 'Schedule Matrix & Drag Dispatch', icon: Calendar },
  { id: 'upload', label: 'Data Ingestion', icon: Upload },
  { id: 'calendar_preview', label: 'Actual Night Preview', icon: Calendar },
];

export default function AppHeader({ activeTab, onNavigate, mode, scenario, onModeChange, onScenarioChange, onAddJob, onSolve, onAccept, solving, hasCandidate }) {
  return (
    <header className="app-header bg-slate-950/90 border-b border-slate-800/80 px-4 py-2 flex flex-wrap items-center justify-between gap-3 text-xs">
      <nav className="flex min-w-0 items-center gap-4 overflow-x-auto" aria-label="Primary navigation">
        {NAV_ITEMS.map(({ id, label, icon: Icon }, index) => (
          <React.Fragment key={id}>
            {index > 0 && <span className="shrink-0 text-slate-600" aria-hidden="true">|</span>}
            <button
              type="button"
              onClick={() => onNavigate(id)}
              aria-current={activeTab === id ? 'page' : undefined}
              className={`flex shrink-0 items-center gap-1.5 transition ${
                activeTab === id
                  ? 'font-bold text-cyan-400'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon size={13} />
              {label}
            </button>
          </React.Fragment>
        ))}
      </nav>
      <div className="flex flex-wrap items-center gap-2" aria-label="Planning controls">
        <div className="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5" role="group" aria-label="Planning mode">
          {[['requirements', 'PS1 Requirements'], ['operations', 'Operations Mode']].map(([value, label]) => (
            <button key={value} type="button" onClick={() => onModeChange(value)}
              aria-pressed={mode === value}
              className={`rounded-md px-3 py-1.5 font-bold ${mode === value ? 'bg-cyan-500 text-slate-950' : 'text-slate-400 hover:text-white'}`}>
              {label}
            </button>
          ))}
        </div>
        <div className="flex rounded-lg border border-slate-700 bg-slate-900 p-0.5" role="group" aria-label="Scenario policy">
          {['A', 'B', 'C'].map((value) => (
            <button key={value} type="button" onClick={() => onScenarioChange(value)} aria-pressed={scenario === value}
              className={`rounded px-2.5 py-1.5 font-bold ${scenario === value ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>
              {value}
            </button>
          ))}
        </div>
        {mode === 'operations' && <button type="button" onClick={onAddJob} className="flex items-center gap-1 rounded-lg border border-slate-700 px-3 py-1.5 text-slate-200 hover:bg-slate-800"><Plus size={13}/> Add Job Request</button>}
        <button type="button" onClick={onSolve} disabled={solving} className="flex items-center gap-1 rounded-lg bg-cyan-500 px-3 py-1.5 font-bold text-slate-950 disabled:opacity-50"><Sparkles size={13}/>{solving ? 'Solving…' : mode === 'operations' ? 'Auto Solve' : 'Solve'}</button>
        {mode === 'operations' && hasCandidate && <button type="button" onClick={onAccept} className="flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-1.5 font-bold text-slate-950"><Check size={13}/> Accept Schedule</button>}
      </div>
    </header>
  );
}
