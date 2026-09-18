import React from "react";
import { ArrowLeft, AlertTriangle } from "lucide-react";

import ScenarioSelector from "./ScenarioSelector";

export default function NetworkToolbar({
  context,
  scenario,
  onSelectScenario,
  isMockSource = true,
}) {
  return (
    <header className="network-toolbar">
      <div className="network-toolbar-left">
        <div className="brand-badge">NEBULA X</div>
        <div>
          <h1 className="toolbar-title">Dual-Line Network Possession Map</h1>
          <p className="toolbar-subtitle">Corridor Topology, Spatial Allocations &amp; Multi-Week Protection</p>
        </div>

        {isMockSource && (
          <div
            className="mock-badge"
            title="Schedule visualization currently uses sample_outputs because solver execution is not yet integrated."
          >
            <AlertTriangle size={12} className="text-amber-400" />
            <span>Mock Schedule Data</span>
          </div>
        )}
      </div>

      <div className="network-toolbar-right">
        <ScenarioSelector
          scenarios={context?.scenarios || []}
          selectedScenario={scenario}
          onSelectScenario={onSelectScenario}
        />

        <a
          href="/"
          className="nav-link-btn"
          title="Return to existing single-night planning workspace"
        >
          <ArrowLeft size={14} />
          <span>Planning Workspace</span>
        </a>
      </div>
    </header>
  );
}
