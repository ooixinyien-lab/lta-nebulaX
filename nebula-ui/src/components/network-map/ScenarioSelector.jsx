import React from "react";

export default function ScenarioSelector({ scenarios = [], selectedScenario, onSelectScenario }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-400 font-semibold uppercase tracking-wider text-[11px]">Scenario:</span>
      <div className="inline-flex rounded-lg bg-slate-800 p-0.5 border border-slate-700">
        {(scenarios.length > 0 ? scenarios : [
          { scenario: "A", available: true, source: "mock" },
          { scenario: "B", available: false },
          { scenario: "C", available: false },
        ]).map((sc) => {
          const isSelected = selectedScenario === sc.scenario;
          const isAvailable = sc.available;

          return (
            <button
              key={sc.scenario}
              onClick={() => isAvailable && onSelectScenario(sc.scenario)}
              disabled={!isAvailable}
              aria-label={isAvailable ? `Select Scenario ${sc.scenario}` : `Scenario ${sc.scenario}: No mock output`}
              title={isAvailable ? `Select Scenario ${sc.scenario}` : `Scenario ${sc.scenario}: No mock output`}
              className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${
                isSelected
                  ? "bg-cyan-500 text-slate-950 shadow-sm"
                  : isAvailable
                  ? "text-slate-300 hover:text-white hover:bg-slate-700/60"
                  : "text-slate-600 cursor-not-allowed opacity-50"
              }`}
            >
              Scenario {sc.scenario}
              {!isAvailable && <span className="ml-1 text-[9px] font-normal text-slate-500">(No mock)</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
