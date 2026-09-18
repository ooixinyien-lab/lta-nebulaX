import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';

export default function EvidenceList({ citations = [] }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const getBadgeStyle = (classification, entityType) => {
    if (entityType === 'conflict') return 'bg-rose-950 text-rose-300 border-rose-800';
    if (entityType === 'counterfactual') return 'bg-purple-950 text-purple-300 border-purple-800';
    if (classification === 'stored_fact') return 'bg-blue-950 text-blue-300 border-blue-800';
    return 'bg-cyan-950 text-cyan-300 border-cyan-800';
  };

  const getLabel = (classification, entityType) => {
    if (entityType === 'conflict') return 'Conflict';
    if (entityType === 'counterfactual') return 'Alternative';
    if (classification === 'stored_fact') return 'Stored';
    return 'Solver';
  };

  return (
    <div className="mt-2.5 pt-2 border-t border-slate-800/80 text-xs">
      <button
        onClick={() => setIsExpanded((prev) => !prev)}
        className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition font-medium text-[11px] cursor-pointer"
        aria-expanded={isExpanded}
      >
        {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <FileText size={12} className="text-cyan-400" />
        <span>Evidence &amp; Grounding ({citations.length})</span>
      </button>

      {isExpanded && (
        <div className="mt-2 space-y-1.5 pl-3 border-l-2 border-slate-800">
          {citations.map((item, idx) => (
            <div key={item.evidence_id || idx} className="bg-slate-900/90 rounded p-2 border border-slate-800 text-[11px]">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${getBadgeStyle(
                    item.classification,
                    item.entity_type
                  )}`}
                >
                  {getLabel(item.classification, item.entity_type)}
                </span>
                <span className="font-mono text-cyan-300 font-bold">{item.entity_id}</span>
                {item.run_id && (
                  <span className="text-slate-500 text-[10px] ml-auto font-mono">[{item.run_id}]</span>
                )}
              </div>
              <p className="text-slate-300 leading-snug">{item.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
