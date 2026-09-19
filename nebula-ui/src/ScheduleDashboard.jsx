import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { 
  Calendar, Zap, Layers, Filter,
  ChevronLeft, ChevronRight, X, AlertTriangle, RefreshCw,
  Sparkles, RotateCcw, AlertOctagon, CheckCircle, Move, Check
} from 'lucide-react';
import { evaluateScheduleConflicts, computeValidDropTargets } from './services/conflictChecker';

// Access Type Semantic Styling
const ACCESS_TYPE_STYLES = {
  PC: {
    bg: 'bg-purple-950/80 hover:bg-purple-900',
    border: 'border-purple-600/80',
    text: 'text-purple-200',
    badge: 'bg-purple-900/90 text-purple-300 border-purple-500/50',
    label: 'Possession with Consist'
  },
  C: {
    bg: 'bg-emerald-950/80 hover:bg-emerald-900',
    border: 'border-emerald-600/80',
    text: 'text-emerald-200',
    badge: 'bg-emerald-900/90 text-emerald-300 border-emerald-500/50',
    label: 'Consist Tenant'
  },
  PM: {
    bg: 'bg-blue-950/80 hover:bg-blue-900',
    border: 'border-blue-600/80',
    text: 'text-blue-200',
    badge: 'bg-blue-900/90 text-blue-300 border-blue-500/50',
    label: 'Plant Solo'
  }
  ,MAINT: {
    bg: 'bg-amber-950/80 hover:bg-amber-900', border: 'border-amber-500/80', text: 'text-amber-200',
    badge: 'bg-amber-900/90 text-amber-200 border-amber-500/50', label: 'Maintenance Work'
  }
};

const NIGHTS_OF_WEEK = [
  { id: 1, label: 'Monday', isEclo: false },
  { id: 2, label: 'Tuesday', isEclo: false },
  { id: 3, label: 'Wednesday', isEclo: false },
  { id: 4, label: 'Thursday', isEclo: false },
  { id: 5, label: 'Friday', isEclo: false },
  { id: 6, label: 'Saturday', isEclo: false },
  { id: 7, label: 'Sunday', isEclo: false },
];

function getActDay(a) {
  if (a == null) return 1;
  if (a.day_of_week != null) return Number(a.day_of_week);
  if (a.service_date) {
    const [y, m, d] = String(a.service_date).split('-').map(Number);
    const day = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
    return day === 0 ? 7 : day;
  }
  return a.access_night || 1;
}

export default function ScheduleDashboard({
  displayData = {},
  mode,
  scenario: initialScenario = 'A',
  onScenarioChange = () => {},
  authoritativeConflicts = [],
  highlightedJobId = null,
  week: controlledWeek,
  onWeekChange,
  onExport,
}) {
  const [currentScenario, setCurrentScenario] = useState(initialScenario);

  useEffect(() => {
    setCurrentScenario(initialScenario);
  }, [initialScenario]);
  // Navigation & Filter State
  const [internalWeek, setInternalWeek] = useState(1);
  const activeWeek = controlledWeek ?? internalWeek;
  const setActiveWeek = (value) => {
    const next = typeof value === 'function' ? value(activeWeek) : value;
    if (onWeekChange) onWeekChange(next);
    else setInternalWeek(next);
  };
  const [lineFilter, setLineFilter] = useState('ALL');
  const [boundFilter, setBoundFilter] = useState('BOTH');
  const [showBuffers, setShowBuffers] = useState(true);
  const [showRoutineMaintenance, setShowRoutineMaintenance] = useState(true);
  const [selectedActivity, setSelectedActivity] = useState(null);

  // Full Schedule State & Solver Baseline
  const [scheduleData, setScheduleData] = useState(null);
  const [solverBaseline, setSolverBaseline] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRescheduling, setIsRescheduling] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  // Manual Drag-and-Drop & Drop-Target Highlighting State
  const [draggingJob, setDraggingJob] = useState(null);
  const [dragOverCell, setDragOverCell] = useState(null);
  const [manualMoveHistory, setManualMoveHistory] = useState([]);
  const isPs1Schedule = (mode || (scheduleData?.identity || displayData?.identity)?.mode) === 'requirements';
  const visibleNights = isPs1Schedule
    ? NIGHTS_OF_WEEK.slice(0, 3).map((night) => ({ ...night, label: `Access night ${night.id}` }))
    : NIGHTS_OF_WEEK;

  // Toast Notification Helper
  const showToast = useCallback((msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4500);
  }, []);

  // The parent planning context owns the exact schedule identity and projection.
  useEffect(() => {
    setScheduleData(displayData?.identity ? displayData : null);
    setSolverBaseline(displayData?.identity ? JSON.parse(JSON.stringify(displayData)) : null);
    setIsLoading(false);
  }, [displayData]);

  // Fallback / Normalized Data Elements
  const activities = scheduleData?.activities || displayData.activities || displayData.sample_activities || [];
  const contracts = scheduleData?.contracts || displayData.contracts || displayData.sample_projects || [];
  const locationsList = scheduleData?.locations || [];
  const sectorsList = scheduleData?.sectors || displayData.sample_sectors || [];
  const accesses = scheduleData?.accesses || [];
  const occupancies = scheduleData?.occupancies || [];

  // Activities & Contracts fast lookups
  const activityMap = useMemo(() => {
    return new Map(activities.map(a => [a.activity_id, a]));
  }, [activities]);

  const contractMap = useMemo(() => {
    return new Map(contracts.map(c => [c.contract_number, c]));
  }, [contracts]);
  useEffect(() => {
    if (!highlightedJobId) return;
    const highlighted = activities.find((activity) => activity.activity_id === highlightedJobId);
    if (highlighted) setSelectedActivity(highlighted);
  }, [highlightedJobId, activities]);

  // 2. Real-Time AGENTS.md Conflict Evaluation
  const preliminaryConflictReport = useMemo(() => {
    return evaluateScheduleConflicts({
      accesses,
      occupancies,
      activities,
      contracts,
      locations: locationsList,
      scenario: currentScenario,
      activeWeek,
      isPs1Schedule,
    });
  }, [accesses, occupancies, activities, contracts, locationsList, currentScenario, activeWeek, isPs1Schedule]);
  const conflictReport = useMemo(() => {
    if (!authoritativeConflicts.length) return preliminaryConflictReport;
    const activityConflicts = new Map();
    authoritativeConflicts.forEach((finding) => {
      const id = finding.job_id || finding.activity_id;
      if (!id) return;
      const rows = activityConflicts.get(id) || [];
      rows.push({ rule: finding.rule, message: finding.detail });
      activityConflicts.set(id, rows);
    });
    return { hasConflicts: true, totalConflicts: authoritativeConflicts.length, activityConflicts };
  }, [authoritativeConflicts, preliminaryConflictReport]);

  // 3. Compute Valid Drop Targets when dragging a job
  const validDropTargets = useMemo(() => {
    if (!draggingJob) return {};
    return computeValidDropTargets({
      draggingJob,
      activeWeek,
      accesses,
      occupancies,
      activities,
      contracts,
      locations: filteredLocationsMemo(locationsList, sectorsList, activities, lineFilter, boundFilter),
      scenario: currentScenario,
      isPs1Schedule,
    });
  }, [draggingJob, activeWeek, accesses, occupancies, activities, contracts, locationsList, sectorsList, currentScenario, lineFilter, boundFilter, isPs1Schedule]);

  // Helper for filtered locations
  function filteredLocationsMemo(locs, secs, acts, lineF, boundF) {
    const locationSet = new Set();
    locs.forEach(l => locationSet.add(l.location_id));
    acts.forEach(a => {
      if (a.start_location_id) locationSet.add(a.start_location_id);
      if (a.start_location) locationSet.add(a.start_location);
    });
    secs.forEach(s => {
      if (s.sector_id) locationSet.add(s.sector_id);
    });

    return Array.from(locationSet).map((locId) => {
      const parts = String(locId).split(':');
      return {
        sector_id: locId,
        location_id: locId,
        line_code: parts[1] || 'BET',
        is_station: locId.startsWith('PLAT'),
        is_interchange: locId.includes('H01') || locId.includes('H02') || locId.includes('S15'),
        bound: locId.endsWith('EB') ? 'EB' : locId.endsWith('WB') ? 'WB' : 'BOTH',
      };
    }).filter((loc) => {
      if (lineF !== 'ALL' && loc.line_code !== lineF) return false;
      if (boundF !== 'BOTH' && loc.bound !== 'BOTH' && loc.bound !== boundF) return false;
      return true;
    });
  }

  // 4. Matrix Processing: Filtered Locations, Week Activities, and KPIs
  const { filteredLocations, weekActivities, weekKpis, groupedContracts } = useMemo(() => {
    const locs = filteredLocationsMemo(locationsList, sectorsList, activities, lineFilter, boundFilter);

    // Merge accesses and occupancies for the active planning week
    let currentWeekActs = [];
    if (accesses.length > 0) {
      const weekAccesses = accesses.filter(a => a.week === activeWeek);
      currentWeekActs = weekAccesses.map(acc => {
        const actDetails = activityMap.get(acc.activity_id) || {};
        const cDetails = contractMap.get(actDetails.contract_number) || {};
        const occ = occupancies.find(o => o.activity_id === acc.activity_id && o.week === activeWeek);
        return {
          ...actDetails,
          ...acc,
          start_location: occ?.location_id || actDetails.start_location_id || actDetails.start_location || 'SEC:BET:S01_S02',
          co_share_group: occ?.co_share_group || 'SOLO',
          access_type: actDetails.access_type || cDetails.access_type || 'PC',
        };
      });
    } else {
      currentWeekActs = activities.filter(a => (a.planned_start_week || 1) === activeWeek);
    }

    const maintenanceActs = showRoutineMaintenance ? (scheduleData?.maintenance || [])
      .filter((visit) => visit.week === activeWeek)
      .flatMap((visit) => (visit.location_ids || [visit.sector_id]).map((location) => ({
        activity_id: visit.visit_id,
        contract_number: 'MAINTENANCE',
        start_location: location,
        access_night: 1,
        day_of_week: getActDay(visit),
        service_date: visit.service_date,
        access_type: 'MAINT',
        isMaintenance: true,
        maintenance_visit: visit,
        eclo: 0,
      }))) : [];
    currentWeekActs = [...currentWeekActs, ...maintenanceActs];
    const activeLocationIds = new Set(currentWeekActs.map((act) => act.start_location));

    // Compute KPIs
    const ecloCount = currentWeekActs.filter(a => a.eclo === 1).length;
    const totalSlots = currentWeekActs.length;

    // Group contracts for the Weekly Activities section.
    const contractsGrouping = {};
    currentWeekActs.forEach((act) => {
      const cNum = act.contract_number || 'C001';
      if (!contractsGrouping[cNum]) contractsGrouping[cNum] = [];
      contractsGrouping[cNum].push(act);
    });

    return {
      filteredLocations: locs.filter((loc) => activeLocationIds.has(loc.sector_id)),
      weekActivities: currentWeekActs,
      weekKpis: { totalSlots, ecloCount },
      groupedContracts: contractsGrouping,
    };
  }, [locationsList, sectorsList, activities, accesses, occupancies, scheduleData, activeWeek, lineFilter, boundFilter, activityMap, contractMap, showRoutineMaintenance]);

  // 5. Drag & Move Handlers
  const handleDragStart = (e, act) => {
    e.dataTransfer.setData('text/plain', act.activity_id);
    e.dataTransfer.effectAllowed = 'move';
    setDraggingJob(act);
  };

  const handleDragEnd = () => {
    setDraggingJob(null);
    setDragOverCell(null);
  };

  const handleDragOver = (e, locId, nightId) => {
    e.preventDefault();
    const cellKey = `${locId}_N${nightId}`;
    const targetStatus = validDropTargets[cellKey];
    if (targetStatus && !targetStatus.canDrop) {
      e.dataTransfer.dropEffect = 'none';
    } else {
      e.dataTransfer.dropEffect = 'move';
    }
    setDragOverCell(cellKey);
  };

  const handleDrop = (targetLocationId, targetNightId) => {
    if (!draggingJob) return;
    const cellKey = `${targetLocationId}_N${targetNightId}`;
    const targetStatus = validDropTargets[cellKey];

    if (targetStatus && !targetStatus.canDrop) {
      showToast(`Cannot drop job here: ${targetStatus.reason || 'Violates AGENTS.md constraint'}`);
      setDraggingJob(null);
      setDragOverCell(null);
      return;
    }

    // Record history snapshot for Undo
    setManualMoveHistory(prev => [
      ...prev,
      {
        accesses: JSON.parse(JSON.stringify(accesses)),
        occupancies: JSON.parse(JSON.stringify(occupancies)),
        jobId: draggingJob.activity_id,
        fromNight: isPs1Schedule ? draggingJob.access_night : getActDay(draggingJob),
        toNight: targetNightId,
      }
    ]);

    // Update accesses state: update access_night or day_of_week / service_date
    const updatedAccesses = accesses.map(acc => {
      if (acc.activity_id === draggingJob.activity_id && acc.week === activeWeek) {
        if (isPs1Schedule) {
          return { ...acc, access_night: targetNightId };
        }
        const horizonStart = displayData?.horizon_start || scheduleData?.horizon_start;
        let newDateStr = acc.service_date;
        if (horizonStart) {
          const [y, m, d] = String(horizonStart).split('-').map(Number);
          const dt = new Date(Date.UTC(y, m - 1, d));
          dt.setUTCDate(dt.getUTCDate() + (activeWeek - 1) * 7 + (targetNightId - 1));
          newDateStr = dt.toISOString().split('T')[0];
        }
        return {
          ...acc,
          day_of_week: targetNightId,
          service_date: newDateStr,
        };
      }
      return acc;
    });

    // Update occupancies state: update location_id
    const updatedOccupancies = occupancies.map(occ => {
      if (occ.activity_id === draggingJob.activity_id && occ.week === activeWeek) {
        return { ...occ, location_id: targetLocationId };
      }
      return occ;
    });

    setScheduleData(prev => ({
      ...prev,
      accesses: updatedAccesses,
      occupancies: updatedOccupancies,
    }));

    const nightName = isPs1Schedule
      ? `Access night ${targetNightId}`
      : (NIGHTS_OF_WEEK[targetNightId - 1]?.label || `Night N${targetNightId}`);
    showToast(`✓ Moved ${draggingJob.activity_id} to ${nightName} at ${targetLocationId}`);
    setDraggingJob(null);
    setDragOverCell(null);
  };

  // Restore the immutable projection currently selected by the planning context.
  const handleReschedule = async () => {
    setIsRescheduling(true);
    if (solverBaseline) setScheduleData(JSON.parse(JSON.stringify(solverBaseline)));
    setManualMoveHistory([]);
    showToast(`Restored active ${displayData.identity?.mode || ''} schedule identity`);
    setIsRescheduling(false);
  };

  // Undo manual move
  const handleUndoMove = () => {
    if (manualMoveHistory.length === 0) return;
    const lastMove = manualMoveHistory[manualMoveHistory.length - 1];
    setScheduleData(prev => ({
      ...prev,
      accesses: lastMove.accesses,
      occupancies: lastMove.occupancies,
    }));
    setManualMoveHistory(prev => prev.slice(0, -1));
    showToast(`Undid move for ${lastMove.jobId} (reverted to Night N${lastMove.fromNight})`);
  };

  return (
    <div className="min-h-full bg-slate-950 text-slate-100 flex flex-col font-sans select-none">
      {/* ========================================================================= */}
      {/* 2. FILTER & KPI STRIP */}
      {/* ========================================================================= */}
      <div className="border-b border-slate-800 bg-slate-900/60 px-6 py-2 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1 rounded-lg border border-slate-800">
            <Filter size={13} className="text-cyan-400" />
            <span className="text-slate-400">Line:</span>
            <select
              value={lineFilter}
              onChange={(e) => setLineFilter(e.target.value)}
              className="bg-transparent text-slate-200 font-bold focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Lines</option>
              <option value="ALP">ALP Line</option>
              <option value="BET">BET Line</option>
            </select>
          </div>

          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1 rounded-lg border border-slate-800">
            <span className="text-slate-400">Bound:</span>
            <select
              value={boundFilter}
              onChange={(e) => setBoundFilter(e.target.value)}
              className="bg-transparent text-slate-200 font-bold focus:outline-none cursor-pointer"
            >
              <option value="BOTH">Both Bounds (EB + WB)</option>
              <option value="EB">Eastbound (EB)</option>
              <option value="WB">Westbound (WB)</option>
            </select>
          </div>

          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-amber-300">
            <input
              type="checkbox"
              checked={showBuffers}
              onChange={(e) => setShowBuffers(e.target.checked)}
              className="accent-amber-500 rounded cursor-pointer"
            />
            Show Safety Buffers
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-amber-300">
            <input type="checkbox" checked={showRoutineMaintenance} onChange={(e) => setShowRoutineMaintenance(e.target.checked)} className="accent-amber-500 rounded cursor-pointer" />
            Show Routine Maintenance
          </label>
        </div>

        {/* Capacity KPIs */}
        <div className="flex items-center gap-6">
          <div className="bg-slate-950 px-3 py-1 rounded-lg border border-slate-800 flex items-center gap-3">
            <div>
              <span className="text-slate-500 text-[9px] block">WEEK {activeWeek} POSSESSIONS</span>
              <span className="text-cyan-400 font-bold">{weekKpis.totalSlots} night-slots</span>
            </div>
            <div className="border-l border-slate-800 pl-3">
              <span className="text-slate-500 text-[9px] block">ECLO ACCELERATED</span>
              <span className="text-amber-400 font-bold flex items-center gap-1">
                <Zap size={11} fill="currentColor" /> {weekKpis.ecloCount} (⚡ 1.5x)
              </span>
            </div>
          </div>
          {onExport && <button type="button" onClick={onExport} className="rounded-lg border border-cyan-700 bg-cyan-950/60 px-3 py-1 text-[11px] font-bold text-cyan-200 hover:bg-cyan-900">Export CSV</button>}
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 4. MAIN CONTENT AREA */}
      {/* ========================================================================= */}
      <main className="flex-1 overflow-hidden relative flex">
        
        {/* SCHEDULE MATRIX VIEW */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64 text-cyan-400 font-mono space-y-3">
              <RefreshCw size={24} className="animate-spin" />
              <p className="text-sm font-bold">Loading full PS1 schedule...</p>
            </div>
          ) : (
            <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[1100px]">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-900/90 font-mono text-xs">
                      <th className="p-3 sticky left-0 bg-slate-900 border-r border-slate-800 w-64 z-20 font-bold text-slate-300 uppercase tracking-wider">
                        Track Location / Sector ID
                      </th>

                      {/* Calendar Nights Columns (3 Access Nights or 7 Weekdays) */}
                      {visibleNights.map((night) => (
                        <th
                          key={night.id}
                          className={`p-2.5 text-center border-r border-slate-800/80 min-w-[130px] ${
                            night.isEclo ? 'bg-amber-950/20 text-amber-300' : 'text-slate-300'
                          }`}
                        >
                          <div className="font-bold flex items-center justify-center gap-1">
                            {isPs1Schedule ? night.label : `${night.label} (N${night.id})`}
                            {night.isEclo && <Zap size={12} className="text-amber-400 fill-amber-400" />}
                          </div>
                          <div className="text-[10px] text-slate-500 font-normal">
                            {isPs1Schedule ? 'Contract/type weekly index — not a weekday' : 'Operational service day'}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-800/60 text-xs font-mono">
                    {filteredLocations.map((loc) => (
                      <tr key={loc.sector_id} className="hover:bg-slate-900/30 transition">
                        
                        {/* Sticky Sector ID Column */}
                        <td className="p-3 sticky left-0 bg-slate-950 border-r border-slate-800 font-bold text-slate-200 z-10 flex items-center justify-between gap-2">
                          <span className="truncate">{loc.sector_id}</span>
                          <div className="flex items-center gap-1 text-[9px]">
                            {loc.is_station && (
                              <span className="px-1.5 py-0.5 rounded bg-cyan-950 border border-cyan-700 text-cyan-300 font-bold">
                                STN
                              </span>
                            )}
                            {loc.is_interchange && (
                              <span className="px-1.5 py-0.5 rounded bg-rose-950 border border-rose-700 text-rose-300 font-bold">
                                INT
                              </span>
                            )}
                          </div>
                        </td>

                        {/* 7 Night Cells */}
                        {visibleNights.map((night) => {
                          const cellKey = `${loc.sector_id}_N${night.id}`;
                          const dropInfo = validDropTargets[cellKey];
                          const isDraggingActive = draggingJob !== null;
                          const canDropHere = isDraggingActive && dropInfo?.canDrop;
                          const cannotDropHere = isDraggingActive && !dropInfo?.canDrop;
                          const isDragOver = dragOverCell === cellKey;

                          const matchingActs = weekActivities.filter((a) => {
                            if (a.start_location !== loc.sector_id) return false;
                            if (isPs1Schedule) {
                              return a.access_night === night.id;
                            }
                            return getActDay(a) === night.id;
                          });

                          // Group by co_share_group from SCHEDULE_OCCUPANCY.csv
                          const coShareGroups = {};
                          matchingActs.forEach((act) => {
                            const grp = act.co_share_group || 'SOLO';
                            if (!coShareGroups[grp]) coShareGroups[grp] = [];
                            coShareGroups[grp].push(act);
                          });

                          return (
                            <td
                              key={night.id}
                              onDragOver={(e) => handleDragOver(e, loc.sector_id, night.id)}
                              onDrop={() => handleDrop(loc.sector_id, night.id)}
                              className={`p-1.5 border-r border-slate-800/50 align-top relative transition-all duration-150 min-h-[70px] ${
                                night.isEclo ? 'bg-amber-950/10' : ''
                              } ${
                                canDropHere
                                  ? isDragOver
                                    ? 'bg-emerald-900/60 border-2 border-emerald-400 ring-2 ring-emerald-400/60 shadow-xl'
                                    : 'bg-emerald-950/40 border-2 border-dashed border-emerald-500/80'
                                  : ''
                              } ${
                                cannotDropHere
                                  ? 'opacity-20 filter grayscale bg-slate-950/90 pointer-events-none'
                                  : ''
                              }`}
                            >
                              {/* Valid Drop Target Highlight Banner */}
                              {canDropHere && (
                                <div className="text-[10px] font-bold text-emerald-300 bg-emerald-950/90 border border-emerald-500/60 rounded px-1.5 py-0.5 mb-1 flex items-center justify-center gap-1 shadow">
                                  <Check size={11} /> Drop to Schedule
                                </div>
                              )}

                              {Object.entries(coShareGroups).map(([groupTag, acts], grpIdx) => (
                                <div
                                  key={grpIdx}
                                  className={`rounded-lg p-1 space-y-1 shadow-lg border my-0.5 ${
                                    groupTag !== 'SOLO'
                                      ? 'bg-slate-900/90 border-cyan-700/80'
                                      : 'bg-transparent border-transparent'
                                  }`}
                                >
                                  {groupTag !== 'SOLO' && (
                                    <div className="text-[9px] font-bold text-cyan-400 px-1 border-b border-slate-800 pb-0.5 flex justify-between">
                                      <span>GROUP #{groupTag}</span>
                                      <span>1 SLOT</span>
                                    </div>
                                  )}

                                  {acts.map((act) => {
                                    const accessType = act.access_type || 'PC';
                                    const style = ACCESS_TYPE_STYLES[accessType] || ACCESS_TYPE_STYLES.PC;
                                    const isSelected = selectedActivity?.activity_id === act.activity_id;
                                    const isBeingDragged = draggingJob?.activity_id === act.activity_id;

                                    // Check if this activity has an active conflict
                                    const actIssues = conflictReport.activityConflicts?.get(act.activity_id) || [];
                                    const hasConflict = actIssues.length > 0;

                                    return (
                                      <div
                                        key={act.activity_id}
                                        draggable={!act.isMaintenance}
                                        onDragStart={(e) => !act.isMaintenance && handleDragStart(e, act)}
                                        onDragEnd={handleDragEnd}
                                        onClick={() => setSelectedActivity(act)}
                                        className={`w-full text-left p-1.5 rounded-md border transition-all cursor-grab active:cursor-grabbing transform hover:scale-[1.02] ${
                                          isBeingDragged ? 'opacity-30 scale-95 border-dashed border-cyan-400' : ''
                                        } ${
                                          hasConflict
                                            ? 'bg-rose-950/95 border-rose-500 text-rose-100 ring-2 ring-rose-500 shadow-xl shadow-rose-900/60 animate-pulse'
                                            : `${style.bg} ${style.border} ${style.text}`
                                        } ${
                                          isSelected ? 'ring-2 ring-cyan-400 shadow-xl' : ''
                                        }`}
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="font-extrabold text-xs flex items-center gap-1">
                                            {hasConflict && <AlertTriangle size={12} className="text-rose-400 shrink-0" />}
                                            {act.activity_id}
                                          </span>
                                          <span className="text-[9px] text-slate-400 font-mono">
                                            Seq #{act.access_seq || 1}
                                          </span>
                                        </div>

                                        <div className="text-[10px] text-slate-300 opacity-90 truncate mt-0.5">
                                          {act.isMaintenance ? `Maintenance · ${act.maintenance_visit?.service_date || 'scheduled'}` : `Contract: ${act.contract_number || 'C001'} (${accessType})`}
                                        </div>

                                        {/* CLASH BADGE: Rendered in RED when conflict detected */}
                                        {hasConflict && (
                                          <div className="mt-1 bg-rose-900/90 border border-rose-400 text-rose-100 font-bold text-[9px] rounded px-1.5 py-0.5 space-y-0.5 shadow">
                                            <div className="flex items-center gap-1 text-rose-200">
                                              <AlertOctagon size={10} />
                                              <span>{actIssues[0].rule.toUpperCase()} CLASH</span>
                                            </div>
                                            <div className="text-[8px] text-rose-300 leading-tight">
                                              {actIssues[0].message}
                                            </div>
                                          </div>
                                        )}

                                        {act.eclo === 1 && !hasConflict && (
                                          <div className="mt-1 flex items-center gap-1 text-[9px] font-bold text-amber-300 bg-amber-950/80 border border-amber-600/60 rounded px-1 py-0.2">
                                            <Zap size={9} fill="currentColor" /> ECLO (1.5x Yield)
                                          </div>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              ))}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <section className="bg-slate-950 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4 font-mono">
            <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">Weekly Activities</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(groupedContracts).length === 0 ? <p className="text-xs text-slate-500">No activities scheduled for this week.</p> : Object.entries(groupedContracts).map(([contractNum, acts]) => {
                const uniqueActs = Array.from(new Map(acts.map((act) => [act.activity_id, act])).values());
                return (
                <div key={contractNum} className="rounded-xl border border-slate-800 bg-slate-900 p-3 text-xs">
                  <div className="flex items-center justify-between"><strong className="text-slate-100">{contractNum}</strong><span className="text-cyan-300">{uniqueActs.length} activities</span></div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {uniqueActs.map((act) => (
                      <span key={act.activity_id} className="rounded bg-slate-950 px-2 py-1 text-slate-300">
                        {act.activity_id} · {isPs1Schedule ? `N${act.access_night || '-'}` : (['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][(getActDay(act) || 1) - 1] || `N${act.access_night || '-'}`)}
                      </span>
                    ))}
                  </div>
                </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* POSSESSION INSPECTOR DRAWER */}
        {selectedActivity && (
          <div className="w-96 bg-slate-950 border-l border-slate-800 p-6 shadow-2xl overflow-y-auto z-30 flex flex-col justify-between font-mono">
            <div className="space-y-6">
              
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-cyan-400">{selectedActivity.activity_id}</h3>
                  <span className="text-xs text-slate-400">Possession &amp; Conflict Inspector</span>
                </div>
                <button
                  onClick={() => setSelectedActivity(null)}
                  className="text-slate-400 hover:text-white p-1 rounded-md"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Active Conflicts in Drawer */}
              {conflictReport.activityConflicts?.has(selectedActivity.activity_id) && (
                <div className="bg-rose-950/80 border border-rose-600 rounded-xl p-4 space-y-2 text-xs">
                  <div className="text-rose-300 font-bold flex items-center gap-2">
                    <AlertTriangle size={14} className="text-rose-400" />
                    <span>Active Constraint Violations:</span>
                  </div>
                  {conflictReport.activityConflicts.get(selectedActivity.activity_id).map((iss, idx) => (
                    <div key={idx} className="bg-rose-900/60 p-2 rounded text-rose-200 text-[11px]">
                      <span className="font-bold text-rose-100 block">{iss.rule.toUpperCase()}:</span>
                      {iss.message}
                    </div>
                  ))}
                </div>
              )}

              {/* Data Card */}
              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 space-y-2">
                <div className="text-slate-500 text-[10px]">CONTRACT NUMBER</div>
                <div className="text-sm font-bold text-slate-200">{selectedActivity.contract_number || 'C001'}</div>

                <div className="border-t border-slate-800 pt-2 text-slate-500 text-[10px]">LOCATION ID</div>
                <div className="text-xs font-bold text-cyan-300">{selectedActivity.start_location}</div>
              </div>

              <div className="bg-slate-900 p-4 rounded-xl border border-slate-800 space-y-3 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Access Sequence:</span>
                  <span className="text-slate-200 font-bold">Seq #{selectedActivity.access_seq || 1}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">{isPs1Schedule ? 'Access Night:' : 'Scheduled Day:'}</span>
                  <span className="text-cyan-400 font-bold">
                    {isPs1Schedule
                      ? `Night N${selectedActivity.access_night}`
                      : (selectedActivity.service_date
                          ? `${selectedActivity.service_date} (${['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][(getActDay(selectedActivity) || 1) - 1]})`
                          : `Night N${selectedActivity.access_night}`)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Co-Share Group:</span>
                  <span className="text-cyan-400 font-bold">{selectedActivity.co_share_group || 'SOLO'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">ECLO Status:</span>
                  <span className={selectedActivity.eclo ? 'text-amber-400 font-bold' : 'text-slate-500'}>
                    {selectedActivity.eclo ? 'Granted (1.5x Yield)' : 'Standard'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Predecessor:</span>
                  <span className="text-slate-300">{selectedActivity.predecessor_activity_id || 'None'}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setSelectedActivity(null)}
              className="mt-6 w-full bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-bold py-2.5 rounded-xl transition"
            >
              Close Inspector
            </button>
          </div>
        )}
      </main>

      {/* FOOTER BAR */}
      <footer className="border-t border-slate-800 bg-slate-950 px-6 py-2 text-[11px] font-mono text-slate-500 flex justify-between items-center">
        <span>ForRail • Interactive Possession Dispatch Board</span>
        <span>Mapped CSV Schema: <strong className="text-slate-300">SCHEDULE_ACCESS + SCHEDULE_OCCUPANCY</strong></span>
      </footer>
    </div>
  );
}
