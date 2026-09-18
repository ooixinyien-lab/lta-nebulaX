import React, { useState } from "react";
import { ArrowLeft, AlertTriangle, Info, X, Shield, GitCommit, Layers } from "lucide-react";
import ScenarioSelector from "./ScenarioSelector";

export default function NetworkToolbar({
  context,
  scenario,
  onSelectScenario,
  isMockSource = true,
}) {
  const [showInfoModal, setShowInfoModal] = useState(false);

  return (
    <>
      <header className="network-toolbar flex items-center justify-between px-6 py-2.5 bg-slate-950/90 border-b border-slate-800/80 backdrop-blur-md sticky top-0 z-40">
        <div className="network-toolbar-left flex items-center gap-3">
          <div className="brand-badge bg-gradient-to-r from-cyan-600 to-blue-600 text-white text-xs font-black px-2 py-0.5 rounded tracking-widest shadow-sm">
            NEBULA X
          </div>

          <div className="flex items-center gap-2">
            <h1 className="toolbar-title text-sm font-bold text-slate-100 tracking-tight">
              Network Possession Map
            </h1>
            <span className="text-slate-600 hidden md:inline">·</span>
            <span className="text-xs text-slate-400 font-mono hidden md:inline">
              Corridor Topology &amp; Multi-Week Protection
            </span>
          </div>

          <button
            type="button"
            onClick={() => setShowInfoModal(true)}
            className="flex items-center gap-1 text-xs bg-slate-800/80 hover:bg-slate-750 text-slate-300 hover:text-white px-2.5 py-1 rounded-lg border border-slate-700 transition"
            title="View Dual-Line Network Model Invariants & Rules"
            aria-label="View Network Model Invariants"
          >
            <Info size={13} className="text-cyan-400" />
            <span>Model Info</span>
          </button>

          {isMockSource ? (
            <div
              className="mock-badge flex items-center gap-1.5 text-[11px] bg-amber-950/60 text-amber-300 border border-amber-800/60 px-2 py-0.5 rounded-full font-medium"
              title="Schedule visualization currently uses sample_outputs because solver execution is not yet integrated."
            >
              <AlertTriangle size={12} className="text-amber-400" />
              <span>Mock Schedule Data</span>
            </div>
          ) : (
            <div
              className="solved-badge flex items-center gap-1.5 text-[11px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 px-2 py-0.5 rounded-full font-medium"
              title="Schedule visualization is reading solved outputs from the outputs/ directory."
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Solved Outputs</span>
            </div>
          )}
        </div>

        <div className="network-toolbar-right flex items-center gap-3">
          <ScenarioSelector
            scenarios={context?.scenarios || []}
            selectedScenario={scenario}
            onSelectScenario={onSelectScenario}
          />

          <a
            href="/"
            className="nav-link-btn flex items-center gap-1.5 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded-lg transition"
            title="Return to single-night planning workspace"
          >
            <ArrowLeft size={13} />
            <span className="hidden sm:inline">Planning Workspace</span>
          </a>
        </div>
      </header>

      {/* Topology & Model Info Modal */}
      {showInfoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Layers size={18} className="text-cyan-400" />
                <h3 className="text-base font-bold text-slate-100">
                  Dual-Line Network Model &amp; Protection Rules
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowInfoModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
                aria-label="Close dialog"
              >
                <X size={16} />
              </button>
            </div>

            <div className="text-xs text-slate-300 space-y-3 font-sans leading-relaxed max-h-[70vh] overflow-y-auto pr-1">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5">
                <div className="font-bold text-cyan-300 flex items-center gap-1.5">
                  <GitCommit size={14} /> 2k+1 Graph Invariant
                </div>
                <p className="text-slate-400">
                  Each line with k stations has k-1 bidirectional sectors connecting them sequentially.
                  Composite station keys (e.g. <code>ALP:H01</code>, <code>BET:H01</code>) distinguish platforms
                  at the shared interchange zone.
                </p>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5">
                <div className="font-bold text-amber-300 flex items-center gap-1.5">
                  <Shield size={14} /> Safety Protection Buffers
                </div>
                <ul className="list-disc pl-4 space-y-1 text-slate-400">
                  <li>
                    <strong className="text-rose-300">Live Work:</strong> 2 buffer sectors on each side + opposite-bound mirrored closure + cross-line interchange tunnel/platform protection.
                  </li>
                  <li>
                    <strong className="text-slate-300">Non-live (Consist):</strong> 1 buffer sector on each side; no opposite-bound mirroring.
                  </li>
                  <li>
                    <strong className="text-slate-300">Non-live (Others):</strong> 0 buffer sectors.
                  </li>
                </ul>
              </div>

              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-1.5">
                <div className="font-bold text-emerald-300 flex items-center gap-1.5">
                  <Layers size={14} /> Co-Sharing Rules
                </div>
                <p className="text-slate-400">
                  Within any location-week possession group:
                  <br />• Exactly 1 PM alone; OR
                  <br />• Exactly 1 PC with at most 3 C (max 4 activities total); OR
                  <br />• At most 4 C activities.
                  <br />Two PCs can never share a possession group.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setShowInfoModal(false)}
                className="bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs px-4 py-2 rounded-lg transition"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
