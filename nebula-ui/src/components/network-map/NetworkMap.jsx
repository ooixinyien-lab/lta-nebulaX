import React, { useState } from "react";
import { useNetworkTopology } from "../../hooks/useNetworkTopology";
import { useNetworkOccupancy } from "../../hooks/useNetworkOccupancy";
import { useWeeklyPlayback } from "../../hooks/useWeeklyPlayback";
import { DEFAULT_LAYERS } from "../../network/mapConstants";

import NetworkToolbar from "./NetworkToolbar";
import NetworkSvgCanvas from "./NetworkSvgCanvas";
import WeeklyScrubber from "./WeeklyScrubber";
import ActivityFilter from "./ActivityFilter";
import LayerControls from "./LayerControls";
import NetworkLegend from "./NetworkLegend";
import NetworkInspector from "./NetworkInspector";
import MapTooltip from "./MapTooltip";

export default function NetworkMap() {
  const { context, activities, loading: topoLoading, error: topoError } = useNetworkTopology();

  const [scenario, setScenario] = useState("A");
  const [week, setWeek] = useState(1);
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [tooltip, setTooltip] = useState({
    visible: false,
    x: 0,
    y: 0,
    title: "",
    subtitle: "",
    extra: "",
  });

  const horizonWeeks = context?.horizon?.weeks || 30;
  const startDate = context?.horizon?.startDate || "2027-01-04";

  const { occupancy, loading: occLoading, error: occError } = useNetworkOccupancy(
    scenario,
    week,
    selectedActivityId
  );

  const { isPlaying, toggle: togglePlay } = useWeeklyPlayback(week, setWeek, horizonWeeks);

  const toggleLayer = (layerKey) => {
    setLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  const handleSelectActivity = (actId) => {
    setSelectedActivityId(actId);
    if (actId) {
      setSelectedEntity({ type: "activity", id: actId });
    } else if (selectedEntity?.type === "activity") {
      setSelectedEntity(null);
    }
  };

  if (topoLoading) {
    return (
      <div className="network-map-container flex items-center justify-center min-h-screen bg-slate-950 text-cyan-400 font-mono">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-bold tracking-wider">Loading network topology...</p>
        </div>
      </div>
    );
  }

  if (topoError) {
    return (
      <div className="network-map-container flex items-center justify-center min-h-screen bg-slate-950 text-rose-400 p-8">
        <div className="bg-rose-950/40 border border-rose-800 p-6 rounded-xl max-w-lg text-center space-y-3">
          <h2 className="text-lg font-bold">Failed to load network topology</h2>
          <p className="text-xs text-rose-300 font-mono">{topoError}</p>
          <a href="/" className="inline-block bg-slate-800 text-slate-200 px-4 py-2 rounded-lg text-xs font-bold hover:bg-slate-700">
            Return to Planning Workspace
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="network-map-container">
      {/* 1. TOP HEADER TOOLBAR */}
      <NetworkToolbar
        context={context}
        scenario={scenario}
        onSelectScenario={(sc) => {
          setScenario(sc);
          setSelectedEntity(null);
        }}
        isMockSource={context?.scheduleSource === "sample_outputs"}
      />

      {/* 2. WORKSPACE SPLIT (CANVAS + INSPECTOR) */}
      <div className="network-main">
        <section className="network-canvas-panel">
          {/* Top filter and overlay toggles */}
          <div className="filter-layer-bar mb-3 max-w-[1060px] w-full mx-auto">
            <ActivityFilter
              activities={activities}
              selectedActivityId={selectedActivityId}
              onSelectActivity={handleSelectActivity}
              activeActivitiesInWeek={occupancy?.activeActivities || []}
              currentWeek={week}
            />

            <LayerControls layers={layers} onToggleLayer={toggleLayer} />
          </div>

          {/* SVG Canvas Box */}
          <div className="svg-wrapper">
            {occError && (
              <div
                role="status"
                className="absolute top-3 left-3 right-3 bg-rose-950/90 border border-rose-800 text-rose-200 text-xs px-3 py-2 rounded-lg font-mono z-20"
              >
                Occupancy update failed: {occError}
              </div>
            )}
            {occLoading && (
              <div className="absolute top-3 right-3 bg-slate-950/80 border border-cyan-500/40 text-cyan-400 text-[10px] px-2.5 py-1 rounded-full font-mono flex items-center gap-1.5 z-20">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span>Updating week {week}...</span>
              </div>
            )}

            <NetworkSvgCanvas
              layers={layers}
              occupancy={occupancy}
              activities={activities}
              selectedActivityId={selectedActivityId}
              selectedEntity={selectedEntity}
              onSelectEntity={setSelectedEntity}
              tooltip={tooltip}
              setTooltip={setTooltip}
            />

            <MapTooltip tooltip={tooltip} />
          </div>

          {/* Bottom Controls (Legend + Timeline Scrubber) */}
          <div className="network-controls-panel">
            <NetworkLegend />

            <WeeklyScrubber
              week={week}
              setWeek={setWeek}
              horizonWeeks={horizonWeeks}
              startDate={startDate}
              isPlaying={isPlaying}
              onTogglePlay={togglePlay}
            />
          </div>
        </section>

        {/* 3. SIDEBAR INSPECTOR */}
        <NetworkInspector
          selectedEntity={selectedEntity}
          occupancy={occupancy}
          activities={activities}
          currentWeek={week}
          onSelectActivity={handleSelectActivity}
        />
      </div>
    </div>
  );
}
