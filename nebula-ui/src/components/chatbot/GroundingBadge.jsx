import React from 'react';
import { Sparkles, ShieldCheck, Database } from 'lucide-react';

export default function GroundingBadge({ responseMode, isMock = false }) {
  if (isMock) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-950/80 text-amber-300 border border-amber-800/60">
        <Database size={11} /> Mock Source
      </span>
    );
  }

  if (responseMode === 'gemini') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
        <Sparkles size={11} /> Gemini Grounded
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-purple-950/80 text-purple-300 border border-purple-800/60">
      <ShieldCheck size={11} /> Verified Schedule Facts
    </span>
  );
}
