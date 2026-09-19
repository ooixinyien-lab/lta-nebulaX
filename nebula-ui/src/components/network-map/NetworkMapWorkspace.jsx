import React, { useState } from "react";
import { useNetworkTopology } from "../../hooks/useNetworkTopology";
import { useNetworkOccupancy } from "../../hooks/useNetworkOccupancy";
import { useWeeklyPlayback } from "../../hooks/useWeeklyPlayback";
import { DEFAULT_LAYERS } from "../../network/mapConstants";
import { useScheduleChat } from "../../chat/ScheduleChatContext";

import NetworkToolbar from "./NetworkToolbar";
import WeekStatusBar from "./WeekStatusBar";
import NetworkSvgCanvas from "./NetworkSvgCanvas";
import WeeklyScrubber from "./WeeklyScrubber";
import ActivityFilter from "./ActivityFilter";
import LayerControls from "./LayerControls";
import NetworkInspector from "./NetworkInspector";
import MapTooltip from "./MapTooltip";

export default function NetworkMapWorkspace({
  scenario: controlledScenario,
  onSelectScenario: controlledOnSelectScenario,
  week: controlledWeek,
  onWeekChange: controlledOnWeekChange,
  selectedActivityId: controlledActivityId,
  onSelectActivity: controlledOnSelectActivity,
  selectedEntity: controlledEntity,
  onSelectEntity: controlledOnSelectEntity,
  embedded = false,
  identity = null,
  weeklySummary: controlledWeeklySummary = null,
  onExport,
}) {
  const { context, activities, loading: topoLoading, error: topoError } = useNetworkTopology(identity);

  // Controlled or uncontrolled scenario
  const [internalScenario, setInternalScenario] = useState("A");
  const scenario = controlledScenario !== undefined ? controlledScenario : internalScenario;
  const setScenario = (sc) => {
    if (controlledOnSelectScenario) controlledOnSelectScenario(sc);
    else setInternalScenario(sc);
  };

  // Controlled or uncontrolled week
  const [internalWeek, setInternalWeek] = useState(1);
  const week = controlledWeek !== undefined ? controlledWeek : internalWeek;
  const setWeek = (wOrUpdater) => {
    const nextW = typeof wOrUpdater === "function" ? wOrUpdater(week) : wOrUpdater;
    if (controlledOnWeekChange) controlledOnWeekChange(nextW);
    else setInternalWeek(nextW);
  };

  // Controlled or uncontrolled activity
  const [internalActivityId, setInternalActivityId] = useState(null);
  const selectedActivityId = controlledActivityId !== undefined ? controlledActivityId : internalActivityId;
  const setSelectedActivityId = (actId) => {
    if (controlledOnSelectActivity) controlledOnSelectActivity(actId);
    else setInternalActivityId(actId);
  };

  // Controlled or uncontrolled entity
  const [internalEntity, setInternalEntity] = useState(null);
  const selectedEntity = controlledEntity !== undefined ? controlledEntity : internalEntity;
  const setSelectedEntity = (entity) => {
    if (controlledOnSelectEntity) controlledOnSelectEntity(entity);
    else setInternalEntity(entity);
  };

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

  const { occupancy, loading: occLoading, error: occError, retry: retryOccupancy } = useNetworkOccupancy(
    scenario,
    week,
    selectedActivityId,
    identity
  );

  const { isPlaying, toggle: togglePlay } = useWeeklyPlayback(
    week,
    setWeek,
    horizonWeeks
  );

  const { setScheduleChatContext } = useScheduleChat();

  const toggleLayer = (layerKey) => {
    setLayers((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  const handleSelectActivity = (actId) => {
    setSelectedActivityId(actId);
    setScheduleChatContext({ selectedActivityId: actId || null });
    if (actId) {
      setSelectedEntity({ type: "activity", id: actId });
    } else if (selectedEntity?.type === "activity") {
      setSelectedEntity(null);
    }
  };

  const handleCloseInspector = () => {
    setSelectedEntity(null);
    setScheduleChatContext({ selectedActivityId: null, selectedLocationId: null });
  };

  const handleSelectEntity = (entity) => {
    if (
      entity &&
      selectedEntity &&
      selectedEntity.type === entity.type &&
      selectedEntity.id === entity.id
    ) {
      setSelectedEntity(null);
      setScheduleChatContext({ selectedLocationId: null });
    } else {
      setSelectedEntity(entity);
      if (entity?.type === "station" || entity?.type === "sector") {
        setScheduleChatContext({ selectedLocationId: entity.id });
      }
    }
  };

  const handleJumpToWeek = (targetWeek) => {
    if (targetWeek >= 1 && targetWeek <= horizonWeeks) {
      setWeek(targetWeek);
    }
  };

  if (topoLoading) {
    return (
      <div className="network-map-container flex items-center justify-center min-h-[500px] bg-slate-950 text-cyan-400 font-mono">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-bold tracking-wider">Loading network topology...</p>
        </div>
      </div>
    );
  }

  if (topoError) {
    return (
      <div className="network-map-container flex items-center justify-center min-h-[500px] bg-slate-950 text-rose-400 p-8">
        <div className="bg-rose-950/40 border border-rose-800 p-6 rounded-xl max-w-lg text-center space-y-3">
          <h2 className="text-lg font-bold">Failed to load network topology</h2>
          <p className="text-xs text-rose-300 font-mono">{topoError}</p>
          <a
            href="/"
            className="inline-block bg-slate-800 text-slate-200 px-4 py-2 rounded-lg text-xs font-bold hover:bg-slate-700"
          >
            Return to Planning Workspace
          </a>
        </div>
      </div>
    );
  }

  const isInspectorOpen = Boolean(selectedEntity);

  return (
    <div className={`network-map-container ${embedded ? "network-map-embedded" : ""}`}>
      {/* 1. TOP HEADER TOOLBAR (If not embedded) */}
      {!embedded && (
        <NetworkToolbar
          context={context}
          scenario={scenario}
          onSelectScenario={(sc) => {
            setScenario(sc);
            setSelectedEntity(null);
          }}
          isMockSource={context?.scheduleSource === "sample_outputs"}
        />
      )}

      {/* 2. WORKSPACE SPLIT (CANVAS + SLIDE-OUT INSPECTOR) */}
      <div className="network-main relative flex flex-1 overflow-hidden">
        <section className={`network-canvas-panel flex-1 flex flex-col min-w-0 p-4 overflow-y-auto transition-all duration-200 ${isInspectorOpen ? "lg:mr-[380px]" : ""}`}>
          {/* Status summary banner */}
          <WeekStatusBar
            week={week}
            startDate={startDate}
            occupancy={occupancy}
            occLoading={occLoading}
            occError={occError}
            onRetry={retryOccupancy}
          />
          {/* Top filter and overlay toggles */}
          <div className="filter-layer-bar mb-3 max-w-[1060px] w-full mx-auto relative z-30">
            <ActivityFilter
              activities={activities}
              selectedActivityId={selectedActivityId}
              onSelectActivity={handleSelectActivity}
              activeActivitiesInWeek={occupancy?.activeActivities || []}
              currentWeek={week}
              onJumpToWeek={handleJumpToWeek}
            />

            <LayerControls layers={layers} onToggleLayer={toggleLayer} />
          </div>

          {/* SVG Canvas Box */}
          <div className="svg-wrapper relative">
            {occLoading && (
              <div className="absolute top-3 right-3 bg-slate-950/85 border border-cyan-500/40 text-cyan-400 text-[10px] px-2.5 py-1 rounded-full font-mono flex items-center gap-1.5 z-20 shadow-md">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span>Syncing week {week}...</span>
              </div>
            )}

            <NetworkSvgCanvas
              layers={layers}
              occupancy={occupancy}
              activities={activities}
              selectedActivityId={selectedActivityId}
              selectedEntity={selectedEntity}
              onSelectEntity={handleSelectEntity}
              tooltip={tooltip}
              setTooltip={setTooltip}
              currentWeek={week}
            />

            <MapTooltip tooltip={tooltip} />
          </div>

          {/* Sticky Bottom Timeline Scrubber */}
          <div className="network-controls-panel max-w-[1060px] w-full mx-auto mt-4">
            <WeeklyScrubber
              week={week}
              setWeek={setWeek}
              horizonWeeks={horizonWeeks}
              startDate={startDate}
              isPlaying={isPlaying}
              onTogglePlay={togglePlay}
              weeklySummary={controlledWeeklySummary || context?.weeklySummary || []}
            />
          </div>
        </section>

        {/* 3. SLIDE-OUT DRAWER INSPECTOR */}
        {isInspectorOpen && (
          <>
            {/* Backdrop on tablet/mobile (<1024px) */}
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-xs z-30 lg:hidden"
              onClick={handleCloseInspector}
              aria-hidden="true"
            />

            <div className="network-inspector-drawer fixed lg:absolute top-0 right-0 bottom-0 w-full sm:w-[400px] lg:w-[380px] z-40 bg-slate-950/95 lg:bg-slate-950 border-l border-slate-800 shadow-2xl overflow-y-auto transition-transform duration-200">
              <NetworkInspector
                selectedEntity={selectedEntity}
                occupancy={occupancy}
                activities={activities}
                currentWeek={week}
                onSelectActivity={handleSelectActivity}
                onClose={handleCloseInspector}
                onJumpToWeek={handleJumpToWeek}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
