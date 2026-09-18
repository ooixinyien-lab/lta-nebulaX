import React, { useState, useEffect, useRef } from 'react';

// Priority Color Mapping for Matrix
const PRIORITY_COLORS = {
  1: 'bg-rose-950/80 border-rose-600/80 text-rose-300 hover:bg-rose-900',
  2: 'bg-amber-950/80 border-amber-600/80 text-amber-300 hover:bg-amber-900',
  3: 'bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800',
};

export default function ScheduleDashboard({
  displayData = {},
  topologyData = null,
  scenario = 'A',
  onScenarioChange = () => {},
}) {
  const [selectedItem, setSelectedItem] = useState(null);
  const [report, setReport] = useState(null);
  const [isLoadingPenalties, setIsLoadingPenalties] = useState(false);
  const canvasRef = useRef(null);

  const weeks = Array.from({ length: 30 }, (_, i) => i + 1);
  const mockLocations = displayData.sample_sectors?.map((s) => ({
    id: s.sector_id,
  })) || [{ id: 'SEC:ALP:S01_S02' }, { id: 'SEC:ALP:S02_S03' }, { id: 'PLAT:ALP:STN_A3' }];

  // 1. Fetch Penalty Scoreboard Data
  useEffect(() => {
    setIsLoadingPenalties(true);
    fetch(`/api/ps1/evaluate-penalties?scenario=${scenario}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setReport(data);
      })
      .catch((err) => console.error('Failed to load penalty report:', err))
      .finally(() => setIsLoadingPenalties(false));
  }, [scenario]);

  // 2. High-DPI Canvas Rendering (Seq-Ordered & Dynamic Legend)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const lines = topologyData?.lines || displayData.sample_lines || [];
    if (!lines.length) return;

    // --- A. Sharp Crisp Rendering for High-DPI / Retina Displays ---
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    // Set logical canvas dimensions matching display size
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    // Clear previous drawing
    ctx.clearRect(0, 0, rect.width, rect.height);

    // --- B. Assign Distinct Line Colors ---
    const lineColors = {};
    const defaultHues = [200, 15, 140, 280, 45]; // Cyan, Crimson, Emerald, Purple, Amber
    lines.forEach((line, idx) => {
      const hue = defaultHues[idx % defaultHues.length];
      lineColors[line.line_code] = `hsl(${hue}, 85%, 55%)`;
    });

    // --- C. Sort & Node Positions Based on 02_STATIONS.csv Sequence ---
    const stationNodes = {};

    lines.forEach((line, lineIdx) => {
      // Sort stations strictly by sequence order
      const rawStations = line.stations || displayData.sample_stations || [];
      const sortedStations = [...rawStations].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));

      sortedStations.forEach((stn, seqIdx) => {
        const sid = stn.station_id || `STN_${seqIdx}`;
        const yPos = 65 + lineIdx * 65;
        const xPos = 80 + seqIdx * 115;

        if (!stationNodes[sid]) {
          stationNodes[sid] = {
            id: sid,
            codes: [sid],
            lines: [line.line_code || 'ALP'],
            is_interchange: stn.is_interchange === 1,
            x: xPos,
            y: yPos,
          };
        } else {
          if (!stationNodes[sid].lines.includes(line.line_code)) {
            stationNodes[sid].lines.push(line.line_code);
          }
          stationNodes[sid].is_interchange = true;
        }
      });
    });

    const nodesList = Object.values(stationNodes);

    // --- D. Draw Sector Tracks Connected in Sequence Order ---
    lines.forEach((line) => {
      const rawSectors = line.sectors || displayData.sample_sectors || [];
      const sortedSectors = [...rawSectors].sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));

      sortedSectors.forEach((sec) => {
        const start = nodesList.find((n) => n.id === (sec.from_station || sec.from_station_id));
        const end = nodesList.find((n) => n.id === (sec.to_station || sec.to_station_id));

        if (start && end) {
          ctx.beginPath();
          ctx.moveTo(start.x, start.y);
          ctx.lineTo(end.x, end.y);
          ctx.strokeStyle = lineColors[line.line_code] || '#38bdf8';
          ctx.lineWidth = 4;
          ctx.lineCap = 'round';
          ctx.stroke();
        }
      });
    });

    // --- E. Draw Station Nodes ---
    nodesList.forEach((node) => {
      const radius = node.is_interchange ? 10 : 7;

      if (node.is_interchange && node.lines.length >= 2) {
        // Left half-circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, Math.PI * 0.5, Math.PI * 1.5);
        ctx.fillStyle = lineColors[node.lines[0]] || '#ef4444';
        ctx.fill();

        // Right half-circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, Math.PI * 1.5, Math.PI * 0.5);
        ctx.fillStyle = lineColors[node.lines[1]] || '#3b82f6';
        ctx.fill();

        // Border ring
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      } else {
        // Single station
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = lineColors[node.lines[0]] || '#10b981';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      }

      // Station ID labels
      ctx.font = 'bold 9px monospace';
      ctx.fillStyle = '#f8fafc';
      ctx.textAlign = 'center';
      ctx.fillText(node.codes.join('/'), node.x, node.y + radius + 12);
    });

    // --- F. Draw Line Color Legend in Top-Right Corner ---
    const legendX = rect.width - 150;
    let legendY = 20;

    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'left';

    lines.forEach((line) => {
      const color = lineColors[line.line_code] || '#38bdf8';
      const label = `${line.line_code} Line (${line.line_name || 'Line'})`;

      // Legend Color Swatch Box
      ctx.fillStyle = color;
      ctx.fillRect(legendX, legendY - 8, 12, 12);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1;
      ctx.strokeRect(legendX, legendY - 8, 12, 12);

      // Legend Text Label
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(label, legendX + 18, legendY);

      legendY += 18;
    });

  }, [topologyData, displayData]);

  const summary = report?.summary || {
    total_score: 48.3,
    delay_penalty_P: 48.3,
    location_excess_slots_V: 0,
    total_eclo_accesses_E: 0,
    hard_violations_count: 0,
  };

  return (
    <div className="p-6 space-y-6 h-full overflow-auto bg-slate-900 text-slate-100">
      {/* 1. EXECUTION & KPI SCOREBOARD BAR */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-bold text-cyan-400 uppercase tracking-wider">
            30-Week Master Schedule Engine
          </h2>
          <p className="text-xs text-slate-400">PS1 Constraint & Penalty Score Dashboard</p>
        </div>

        {/* Scenario Toggle */}
        <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-1">
          {['A', 'B', 'C'].map((sc) => (
            <button
              key={sc}
              onClick={() => onScenarioChange(sc)}
              className={`px-3 py-1 rounded text-xs font-bold font-mono transition ${
                scenario === sc
                  ? 'bg-cyan-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Scenario {sc}
            </button>
          ))}
        </div>

        {/* Penalty KPI Cards */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500 block text-[10px]">TOTAL PENALTY</span>
            <span className="text-sm font-extrabold text-amber-400">
              {isLoadingPenalties ? '...' : summary.total_score}
            </span>
          </div>
          <div className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500 block text-[10px]">DELAY (P)</span>
            <span className="text-rose-400 font-bold">{summary.delay_penalty_P}</span>
          </div>
          <div className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500 block text-[10px]">EXCESS (V)</span>
            <span className="text-amber-400 font-bold">{summary.location_excess_slots_V} slots</span>
          </div>
          <div className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500 block text-[10px]">ECLO (E)</span>
            <span className="text-sky-400 font-bold">{summary.total_eclo_accesses_E}</span>
          </div>
          {summary.hard_violations_count > 0 && (
            <div className="bg-rose-950 border border-rose-600 text-rose-300 px-3 py-1.5 rounded-lg font-bold text-[11px] animate-pulse">
              ⚠ {summary.hard_violations_count} Violations
            </div>
          )}
        </div>
      </div>

      {/* 2. TOPOLOGY NETWORK DIAGRAM CANVAS */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-xl">
        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
          Railway Network Topology Map
        </h4>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '220px' }}
          className="bg-slate-900 rounded-lg border border-slate-800"
        />
      </div>

      {/* 3. LOCATION-TIME SCHEDULE MATRIX */}
      <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[1200px]">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-[10px] uppercase tracking-wider text-slate-400">
                <th className="p-3 sticky left-0 bg-slate-900 border-r border-slate-800 w-48 z-10">
                  Location / Sector ID
                </th>
                {weeks.map((w) => (
                  <th key={w} className="p-2 text-center border-r border-slate-800/50 w-12 font-mono">
                    W{w}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 text-xs font-mono">
              {mockLocations.map((loc) => (
                <tr key={loc.id} className="hover:bg-slate-900/30">
                  <td className="p-3 sticky left-0 bg-slate-950 border-r border-slate-800 font-medium text-slate-300">
                    {loc.id}
                  </td>
                  {weeks.map((w) => {
                    const acts = (displayData.sample_activities || []).filter(
                      (a) => a.planned_start_week === w && a.start_location === loc.id
                    );

                    return (
                      <td key={w} className="p-1 border-r border-slate-800/40 text-center">
                        {acts.map((matchingAct) => {
                          const priStyle =
                            PRIORITY_COLORS[matchingAct.activity_priority] || PRIORITY_COLORS[3];
                          const isEclo = matchingAct.eclo === 1;

                          return (
                            <button
                              key={matchingAct.activity_id}
                              onClick={() => setSelectedItem(matchingAct)}
                              className={`w-full py-1 px-1 rounded text-[10px] font-bold transition transform hover:scale-105 border my-0.5 ${priStyle}`}
                            >
                              {matchingAct.activity_id}
                              {isEclo && <span className="ml-1 text-sky-300">⚡</span>}
                            </button>
                          );
                        })}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. SLIDE-OVER JOB INSPECTOR DRAWER */}
      {selectedItem && (
        <div className="fixed inset-y-0 right-0 w-96 bg-slate-950 border-l border-slate-800 p-6 shadow-2xl z-50 overflow-y-auto space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-cyan-400 font-mono">
                {selectedItem.activity_id}
              </h3>
              <p className="text-xs text-slate-400">
                Contract: {selectedItem.contract_number || 'C001'}
              </p>
            </div>
            <button
              onClick={() => setSelectedItem(null)}
              className="text-slate-400 hover:text-white font-bold p-1 rounded"
            >
              ✕
            </button>
          </div>

          <div className="space-y-4 text-xs font-mono">
            <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 space-y-1">
              <div className="text-slate-400">Planned Start: Week {selectedItem.planned_start_week}</div>
              <div className="text-slate-400">Workload: {selectedItem.total_accesses || 7} Accesses</div>
              <div className="text-amber-400">Priority: Tier {selectedItem.activity_priority || 1}</div>
            </div>

            <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 space-y-2">
              <h5 className="font-bold text-slate-300 uppercase tracking-wider text-[10px]">
                Constraint & Execution Audit
              </h5>
              <div className="flex justify-between">
                <span className="text-slate-400">ECLO Accelerated:</span>
                <span className={selectedItem.eclo ? 'text-sky-400 font-bold' : 'text-slate-500'}>
                  {selectedItem.eclo ? 'Yes (+0.5 Yield)' : 'No'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Predecessor:</span>
                <span className="text-slate-200">
                  {selectedItem.predecessor_activity_id || 'None'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}