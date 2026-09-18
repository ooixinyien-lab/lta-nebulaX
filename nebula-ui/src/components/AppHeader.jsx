import React from 'react';
import { Calendar, Map, Upload } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'network_map', label: 'Interactive Network Map', icon: Map },
  { id: 'matrix', label: 'Schedule Matrix & Drag Dispatch', icon: Calendar },
  { id: 'upload', label: 'Data Ingestion', icon: Upload },
  { id: 'calendar_preview', label: 'Actual Night Preview', icon: Calendar },
];

export default function AppHeader({ activeTab, onNavigate }) {
  return (
    <header className="app-header bg-slate-950/80 border-b border-slate-800/80 px-6 py-1.5 flex items-center justify-between text-xs">
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
    </header>
  );
}
