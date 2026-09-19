import React from 'react';
import { Bot, X, RotateCcw } from 'lucide-react';
import GroundingBadge from './GroundingBadge';

export default function ChatHeader({ onClose, onClear, isMock = false }) {
  return (
    <div className="bg-slate-950 px-4 py-3 border-b border-slate-800 flex items-center justify-between select-none">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
          <Bot size={18} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-100 tracking-wide">Schedule Explainer</h3>
            <GroundingBadge isMock={isMock} />
          </div>
          <p className="text-[11px] text-slate-400">Grounded decision support &amp; displacement analysis</p>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={onClear}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition"
          title="Clear Conversation"
          aria-label="Clear Conversation"
        >
          <RotateCcw size={15} />
        </button>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition"
          title="Close Explainer (Esc)"
          aria-label="Close Explainer"
        >
          <X size={17} />
        </button>
      </div>
    </div>
  );
}
