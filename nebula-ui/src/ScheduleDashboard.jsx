import React, { useState, useMemo, useEffect } from 'react';
import { 
  Calendar, Shield, Zap, Layers, Filter, 
  ChevronLeft, ChevronRight, X, AlertTriangle, RefreshCw
} from 'lucide-react';

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
};

const NIGHTS_OF_WEEK = [
  { id: 1, label: 'Mon', time: '01:30', isEclo: false },
  { id: 2, label: 'Tue', time: '01:30', isEclo: false },
  { id: 3, label: 'Wed', time: '01:30', isEclo: false },
  { id: 4, label: 'Thu', time: '01:30', isEclo: false },
  { id: 5, label: 'Fri', time: '00:30', isEclo: true },
  { id: 6, label: 'Sat', time: '00:30', isEclo: true },
  { id: 7, label: 'Sun', time: '01:30', isEclo: false },
];

export default function ScheduleDashboard({
  displayData = {},
  scenario = 'A',
  onScenarioChange = () => {},
}) {
  // Navigation & Filter State
  const [activeWeek, setActiveWeek] = useState(1);
  const [activeView, setActiveView] = useState('matrix'); // 'matrix' | 'gantt'
  const [lineFilter, setLineFilter] = useState('ALL');
  const [boundFilter, setBoundFilter] = useState('BOTH');
  const [showBuffers, setShowBuffers] = useState(true);
  const [selectedActivity, setSelectedActivity] = useState(null);

  // Auto-adjust active week based on dataset range
  useEffect(() => {
    if (displayData.sample_activities?.length > 0) {
      const minW = Math.min(...displayData.sample_activities.map((a) => a.planned_start_week || 1));
      setActiveWeek(minW);
    }
  }, [displayData]);

  // 1. Process Real CSV Fields into Matrix Structure
  const { filteredLocations, weekActivities, weekKpis, groupedContracts } = useMemo(() => {
    const rawActivities = displayData.sample_activities || [];
    const rawSectors = displayData.sample_sectors || [];

    // Derive Unique Locations from SCHEDULE_OCCUPANCY location_id
    const locationSet = new Set();
    rawActivities.forEach((a) => {
      if (a.start_location) locationSet.add(a.start_location);
    });
    rawSectors.forEach((s) => {
      if (s.sector_id) locationSet.add(s.sector_id);
    });

    // Parse and Filter Location Items
    const locs = Array.from(locationSet).map((locId) => {
      const parts = String(locId).split(':');
      return {
        sector_id: locId,
        line_code: parts[1] || 'BET',
        is_station: locId.startsWith('PLAT'),
        is_interchange: locId.includes('H01') || locId.includes('H02') || locId.includes('S15'),
        bound: locId.endsWith('EB') ? 'EB' : locId.endsWith('WB') ? 'WB' : 'BOTH',
      };
    }).filter((loc) => {
      if (lineFilter !== 'ALL' && loc.line_code !== lineFilter) return false;
      if (boundFilter !== 'BOTH' && loc.bound !== 'BOTH' && loc.bound !== boundFilter) return false;
      return true;
    });

    // Activities for active planning week
    const currentWeekActs = rawActivities.filter((a) => a.planned_start_week === activeWeek);

    // Compute KPIs
    const ecloCount = currentWeekActs.filter((a) => a.eclo === 1).length;
    const totalSlots = currentWeekActs.length;

    // Group Contracts for View C Gantt
    const contractsMap = {};
    rawActivities.forEach((act) => {
      const cNum = act.contract_number || 'C001';
      if (!contractsMap[cNum]) contractsMap[cNum] = [];
      contractsMap[cNum].push(act);
    });

    return {
      filteredLocations: locs,
      weekActivities: currentWeekActs,
      weekKpis: { totalSlots, ecloCount },
      groupedContracts: contractsMap,
    };
  }, [displayData, activeWeek, lineFilter, boundFilter]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans select-none">
      
      {/* ========================================================================= */}
      {/* HEADER BAR */}
      {/* ========================================================================= */}
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-3 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-40 shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="bg-cyan-500 text-slate-950 font-black px-2.5 py-1 rounded text-lg tracking-wider shadow-lg shadow-cyan-500/20">
            NEBULA X
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-100 tracking-tight flex items-center gap-2">
              Weekly Possession Dispatch Board
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-400">
                LIVE CSV DATA
              </span>
            </h1>
            <p className="text-xs text-slate-400 font-mono">
              SCHEDULE_ACCESS • SCHEDULE_OCCUPANCY • RESULTS
            </p>
          </div>
        </div>

        {/* Planning Horizon Scrubber */}
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1 shadow-inner">
          <button
            onClick={() => setActiveWeek((w) => Math.max(1, w - 1))}
            disabled={activeWeek === 1}
            className="p-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition"
          >
            <ChevronLeft size={18} />
          </button>

          <div className="px-4 text-center font-mono">
            <span className="text-xs text-slate-400 block font-sans uppercase text-[9px] tracking-widest">
              Planning Horizon
            </span>
            <span className="text-sm font-bold text-cyan-400">
              Week {activeWeek} of 30
            </span>
          </div>

          <button
            onClick={() => setActiveWeek((w) => Math.min(30, w + 1))}
            disabled={activeWeek === 30}
            className="p-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* View Controls & Scenario Toggle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1">
            {['A', 'B', 'C'].map((sc) => (
              <button
                key={sc}
                onClick={() => onScenarioChange(sc)}
                className={`px-2.5 py-1 text-xs font-bold font-mono rounded transition ${
                  scenario === sc
                    ? 'bg-cyan-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Scen {sc}
              </button>
            ))}
          </div>

          <div className="bg-slate-900 border border-slate-800 p-1 rounded-lg flex font-mono text-xs">
            <button
              onClick={() => setActiveView('matrix')}
              className={`px-3 py-1.5 rounded-md font-bold transition flex items-center gap-2 ${
                activeView === 'matrix'
                  ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Calendar size={14} /> View A: 7-Day Matrix
            </button>
            <button
              onClick={() => setActiveView('gantt')}
              className={`px-3 py-1.5 rounded-md font-bold transition flex items-center gap-2 ${
                activeView === 'gantt'
                  ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers size={14} /> View C: Contract Gantt
            </button>
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* FILTER & KPI STRIP */}
      {/* ========================================================================= */}
      <div className="border-b border-slate-800 bg-slate-900/60 px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
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

          <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
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
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MAIN CONTENT AREA */}
      {/* ========================================================================= */}
      <main className="flex-1 overflow-hidden relative flex">
        
        {/* SCHEDULE MATRIX VIEW */}
        <div className="flex-1 overflow-auto p-6 space-y-6">
          {activeView === 'matrix' && (
            <div className="bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[1000px]">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-900/90 font-mono text-xs">
                      <th className="p-3 sticky left-0 bg-slate-900 border-r border-slate-800 w-64 z-20 font-bold text-slate-300 uppercase tracking-wider">
                        Track Location / Sector ID
                      </th>

                      {/* 7 Calendar Nights Columns (N1-N7) */}
                      {NIGHTS_OF_WEEK.map((night) => (
                        <th
                          key={night.id}
                          className={`p-2.5 text-center border-r border-slate-800/80 min-w-[120px] ${
                            night.isEclo ? 'bg-amber-950/20 text-amber-300' : 'text-slate-300'
                          }`}
                        >
                          <div className="font-bold flex items-center justify-center gap-1">
                            {night.label} Night (N{night.id})
                            {night.isEclo && <Zap size={12} className="text-amber-400 fill-amber-400" />}
                          </div>
                          <div className="text-[10px] text-slate-500 font-normal">
                            Access @ {night.time} HRS
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
                        {NIGHTS_OF_WEEK.map((night) => {
                          const matchingActs = weekActivities.filter(
                            (a) => a.start_location === loc.sector_id && a.access_night === night.id
                          );

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
                              className={`p-1.5 border-r border-slate-800/50 align-top relative ${
                                night.isEclo ? 'bg-amber-950/10' : ''
                              }`}
                            >
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

                                    return (
                                      <button
                                        key={act.activity_id}
                                        onClick={() => setSelectedActivity(act)}
                                        className={`w-full text-left p-1.5 rounded-md border transition transform hover:scale-[1.02] ${style.bg} ${style.border} ${style.text} ${
                                          isSelected ? 'ring-2 ring-cyan-400 shadow-xl' : ''
                                        }`}
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="font-extrabold text-xs">{act.activity_id}</span>
                                          <span className="text-[9px] text-slate-400 font-mono">
                                            Seq #{act.access_seq || 1}
                                          </span>
                                        </div>

                                        <div className="text-[10px] text-slate-300 opacity-90 truncate mt-0.5">
                                          Contract: {act.contract_number || 'C001'}
                                        </div>

                                        {act.eclo === 1 && (
                                          <div className="mt-1 flex items-center gap-1 text-[9px] font-bold text-amber-300 bg-amber-950/80 border border-amber-600/60 rounded px-1 py-0.2">
                                            <Zap size={9} fill="currentColor" /> ECLO (1.5x Yield)
                                          </div>
                                        )}
                                      </button>
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

          {/* VIEW C: CONTRACT GANTT & RESULTS */}
          {activeView === 'gantt' && (
            <div className="bg-slate-950 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-6 font-mono">
              <h3 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">
                Simulated Completion Dates & Delay Overruns (RESULTS.csv)
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(groupedContracts).map(([contractNum, acts]) => {
                  const res = (displayData.results || []).find((r) => r.contract_number === contractNum) || {};
                  const isOverrun = res.overrun_days > 0;

                  return (
                    <div
                      key={contractNum}
                      className={`bg-slate-900 border rounded-xl p-4 space-y-3 ${
                        isOverrun ? 'border-rose-600/80' : 'border-slate-800'
                      }`}
                    >
                      <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                        <span className="text-sm font-bold text-slate-100">{contractNum}</span>
                        {isOverrun ? (
                          <span className="px-2 py-0.5 rounded bg-rose-950 border border-rose-600 text-rose-300 text-[10px] font-bold flex items-center gap-1">
                            <AlertTriangle size={11} /> +{res.overrun_days} Days Delay
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-emerald-950 border border-emerald-600 text-emerald-300 text-[10px] font-bold">
                            On Schedule
                          </span>
                        )}
                      </div>

                      <div className="text-xs space-y-1 text-slate-400">
                        <div>Simulated Completion: <strong className="text-slate-200">{res.simulated_completion_date || 'N/A'}</strong></div>
                        <div>Total Activities Enrolled: <strong className="text-cyan-400">{acts.length}</strong></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* POSSESSION INSPECTOR DRAWER */}
        {selectedActivity && (
          <div className="w-96 bg-slate-950 border-l border-slate-800 p-6 shadow-2xl overflow-y-auto z-30 flex flex-col justify-between font-mono">
            <div className="space-y-6">
              
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-cyan-400">{selectedActivity.activity_id}</h3>
                  <span className="text-xs text-slate-400">CSV Possession Inspector</span>
                </div>
                <button
                  onClick={() => setSelectedActivity(null)}
                  className="text-slate-400 hover:text-white p-1 rounded-md"
                >
                  <X size={18} />
                </button>
              </div>

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
                  <span className="text-slate-400">Night Scheduled:</span>
                  <span className="text-slate-200 font-bold">Night N{selectedActivity.access_night}</span>
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
        <span>NEBULA X • Possession Dispatch Engine</span>
        <span>Mapped CSV Schema: <strong className="text-slate-300">SCHEDULE_ACCESS + SCHEDULE_OCCUPANCY</strong></span>
      </footer>
    </div>
  );
}