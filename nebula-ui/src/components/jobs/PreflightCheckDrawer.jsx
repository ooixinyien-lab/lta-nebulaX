import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Sparkles,
  Shield,
  Layers,
  Clock,
  ExternalLink,
} from 'lucide-react';

export default function PreflightCheckDrawer({
  result,
  isLoading = false,
  isOpen = true,
  onToggle = () => {},
  onRecheck = () => {},
}) {
  if (!result && !isLoading) {
    return null;
  }

  const status = result?.status || 'UNKNOWN';
  const isPassed = status === 'PASSED';
  const isWarning = status === 'WARNING';
  const isHardConflict = status === 'HARD CONFLICT';

  // Visual theming based on feasibility status
  const theme = isHardConflict
    ? {
        border: 'border-rose-700/80',
        bg: 'bg-rose-950/40',
        badge: 'bg-rose-500/20 text-rose-300 border-rose-600',
        icon: <XCircle className="text-rose-400" size={18} />,
        statusLabel: 'HARD CONFLICT DETECTED',
      }
    : isWarning
    ? {
        border: 'border-amber-700/80',
        bg: 'bg-amber-950/30',
        badge: 'bg-amber-500/20 text-amber-300 border-amber-600',
        icon: <AlertTriangle className="text-amber-400" size={18} />,
        statusLabel: 'FEASIBLE WITH WARNINGS',
      }
    : {
        border: 'border-emerald-700/80',
        bg: 'bg-emerald-950/30',
        badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-600',
        icon: <CheckCircle2 className="text-emerald-400" size={18} />,
        statusLabel: 'SCHEDULE INSERTION FEASIBLE',
      };

  return (
    <div
      className={`border rounded-xl transition-all duration-200 overflow-hidden shadow-lg ${theme.border} ${theme.bg}`}
    >
      {/* HEADER BANNER */}
      <div className="px-4 py-3 flex items-center justify-between gap-3 bg-slate-950/70 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          {isLoading ? (
            <RefreshCw className="animate-spin text-cyan-400" size={18} />
          ) : (
            theme.icon
          )}
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-black tracking-wider text-slate-100">
                PREFLIGHT ENGINE CHECK
              </span>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${theme.badge}`}
              >
                {isLoading ? 'ANALYZING CONSTRAINTS...' : theme.statusLabel}
              </span>
            </div>
            {result?.timestamp && (
              <span className="text-[10px] text-slate-400 flex items-center gap-1">
                <Clock size={10} /> Last checked: {result.timestamp}
              </span>
            )}
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRecheck}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-cyan-400 border border-slate-700 text-xs flex items-center gap-1 transition"
            title="Re-run Preflight Check"
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
            <span className="hidden sm:inline text-[11px]">Re-test</span>
          </button>

          <button
            type="button"
            onClick={onToggle}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 transition"
            title={isOpen ? 'Collapse panel' : 'Expand panel'}
          >
            {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* DRAWER BODY (COLLAPSIBLE) */}
      {isOpen && (
        <div className="p-4 space-y-4 text-xs font-sans">
          {/* 1. METRICS ROW */}
          {result?.metrics && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="bg-slate-950/80 border border-slate-800 p-2.5 rounded-lg text-center">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                  Disruption Score
                </div>
                <div className="text-sm font-bold font-mono text-cyan-400 mt-0.5">
                  {result.metrics.disruptionScore} pts
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 p-2.5 rounded-lg text-center">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                  Displaced Visits
                </div>
                <div
                  className={`text-sm font-bold font-mono mt-0.5 ${
                    result.metrics.displacedVisits > 0 ? 'text-amber-400' : 'text-emerald-400'
                  }`}
                >
                  {result.metrics.displacedVisits} visits
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 p-2.5 rounded-lg text-center">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                  Safety Halo
                </div>
                <div className="text-sm font-bold font-mono text-purple-400 mt-0.5">
                  +{result.metrics.bufferHaloSectors} Sectors
                </div>
              </div>

              <div className="bg-slate-950/80 border border-slate-800 p-2.5 rounded-lg text-center">
                <div className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                  Peak Utilization
                </div>
                <div className="text-sm font-bold font-mono text-slate-200 mt-0.5">
                  {result.metrics.capacityPeakRatio}
                </div>
              </div>
            </div>
          )}

          {/* 2. RULE BREAKDOWN CHECKLIST */}
          <div className="space-y-2">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Constraint &amp; Safety Rule Verification
            </span>

            <div className="space-y-1.5">
              {(result?.ruleBreakdown || []).map((ruleItem, idx) => {
                const isItemPass = ruleItem.severity === 'success';
                const isItemWarn = ruleItem.severity === 'warning';
                const isItemFail = ruleItem.severity === 'error';

                return (
                  <div
                    key={idx}
                    className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs transition ${
                      isItemFail
                        ? 'bg-rose-950/40 border-rose-800/80 text-rose-200'
                        : isItemWarn
                        ? 'bg-amber-950/40 border-amber-800/80 text-amber-200'
                        : 'bg-slate-950/60 border-slate-800 text-slate-300'
                    }`}
                  >
                    <div className="shrink-0 mt-0.5">
                      {isItemFail ? (
                        <XCircle size={14} className="text-rose-400" />
                      ) : isItemWarn ? (
                        <AlertTriangle size={14} className="text-amber-400" />
                      ) : (
                        <CheckCircle2 size={14} className="text-emerald-400" />
                      )}
                    </div>

                    <div className="flex-1 space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-100">{ruleItem.rule}</span>
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.2 rounded uppercase ${
                            isItemFail
                              ? 'text-rose-400 font-bold'
                              : isItemWarn
                              ? 'text-amber-400 font-bold'
                              : 'text-emerald-400'
                          }`}
                        >
                          {ruleItem.severity}
                        </span>
                      </div>
                      <p className="text-[11px] leading-relaxed text-slate-300">
                        {ruleItem.detail}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. HARD CONFLICT BLOCKER ALERT */}
          {isHardConflict && (
            <div className="bg-rose-950/60 border border-rose-700/80 rounded-lg p-3 text-rose-200 space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-rose-300 text-xs">
                <XCircle size={14} /> Blocker Notice
              </div>
              <p className="text-[11px] text-rose-200 leading-normal">
                {result.hardConflictReason ||
                  'One or more hard constraints are violated. The solver cannot insert this possession job until the conflicting dependency or date window is adjusted.'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
