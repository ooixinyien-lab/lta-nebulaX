import React, { useState, useMemo } from "react";
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
import JobEditorModal from "../jobs/JobEditorModal";

export default function NetworkMap() {
  const { context, activities, loading: topoLoading, error: topoError } = useNetworkTopology();

  const [scenario, setScenario] = useState("A");
  const [week, setWeek] = useState(1);
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [layers, setLayers] = useState(DEFAULT_LAYERS);
  const [isJobModalOpen, setIsJobModalOpen] = useState(false);
  const [modalInitialData, setModalInitialData] = useState(null);
  const [mapPickField, setMapPickField] = useState(null);
  const [insertedJobs, setInsertedJobs] = useState([]);

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

  const { occupancy, loading: occLoading } = useNetworkOccupancy(
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

  const existingJobs = useMemo(() => {
    const list = (activities || []).map((a) => ({
      id: a.activityId,
      title: `${a.contractNumber || ''} ${a.activityId}`,
      lineCode: a.lineCode || 'NSL',
      completionDate: a.plannedCompletionDate || a.completionDate || '2027-05-30',
      natureOfWorks: a.natureOfWorks || 'MEDIUM',
    }));
    return [...list, ...insertedJobs];
  }, [activities, insertedJobs]);

  const handleSelectOnMap = (field) => {
    setMapPickField(field);
    setIsJobModalOpen(false);
  };

  const handleEntitySelect = (entity) => {
    if (mapPickField && entity?.id) {
      const stationCode = entity.id.split(':').pop();
      setModalInitialData((prev) => ({
        ...prev,
        [mapPickField]: stationCode,
      }));
      setMapPickField(null);
      setIsJobModalOpen(true);
      return;
    }
    setSelectedEntity(entity);
  };

  const handleJobSubmit = async (jobData) => {
    // Add newly inserted job to state
    setInsertedJobs((prev) => [
      ...prev,
      {
        id: jobData.id,
        title: `${jobData.contract_number || 'ADHOC'} ${jobData.id}`,
        lineCode: jobData.line_code,
        completionDate: jobData.planned_completion_date,
        natureOfWorks: jobData.nature_of_works,
      },
    ]);
  };

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
        onNewJob={() => {
          setModalInitialData(null);
          setIsJobModalOpen(true);
        }}
      />

      {/* Map Picking Banner */}
      {mapPickField && (
        <div className="bg-cyan-950 border-y border-cyan-500/50 px-6 py-2.5 flex items-center justify-between text-xs z-30">
          <div className="flex items-center gap-2 text-cyan-300 font-mono">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
            <span>
              <strong>Pick on Map Active:</strong> Click any station on the diagram to set as{' '}
              <strong className="text-white uppercase underline">
                {mapPickField === 'start_location_id' ? 'Start Location' : 'End Location'}
              </strong>.
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              setMapPickField(null);
              setIsJobModalOpen(true);
            }}
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-600 text-xs font-bold transition"
          >
            Cancel Pick &amp; Return to Form
          </button>
        </div>
      )}

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
              onSelectEntity={handleEntitySelect}
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

      {/* 4. CONSTRAINT-AWARE JOB EDITOR MODAL */}
      <JobEditorModal
        isOpen={isJobModalOpen}
        onClose={() => setIsJobModalOpen(false)}
        onSubmit={handleJobSubmit}
        initialData={modalInitialData}
        existingJobs={existingJobs}
        topologyData={context}
        onSelectOnMap={handleSelectOnMap}
      />
    </div>
  );
}

