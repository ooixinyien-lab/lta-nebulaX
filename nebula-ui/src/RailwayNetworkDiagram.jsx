import React, { useEffect, useRef } from 'react';

export default function RailwayNetworkDiagram({ lines = [], stations = [], sectors = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // 1. DYNAMICALLY GENERATE DISTINCT COLORS FOR ANY LINE NAME
    const lineCodes = Array.from(
      new Set([
        ...lines.map((l) => l.line_code),
        ...stations.map((s) => s.line_code),
        ...sectors.map((s) => s.line_code),
      ].filter(Boolean))
    );

    const lineColors = {};
    lineCodes.forEach((code, idx) => {
      // Distribute hues evenly around the color wheel (0° to 360°)
      const hue = (idx * (360 / Math.max(lineCodes.length, 1))) % 360;
      lineColors[code] = `hsl(${hue}, 80%, 55%)`;
    });

    // 2. GROUP STATIONS BY ID TO DETECT INTERCHANGES & ASSIGN GRID POSITIONS
    const stationMap = {};
    const rawStations = stations.length > 0 ? stations : mockDefaultStations;

    rawStations.forEach((st, idx) => {
      if (!stationMap[st.station_id]) {
        stationMap[st.station_id] = {
          id: st.station_id,
          codes: [st.station_id],
          lines: [st.line_code],
          is_interchange: st.is_interchange === 1,
          x: 100 + (idx % 5) * 160,
          y: 90 + Math.floor(idx / 5) * 110,
        };
      } else {
        if (!stationMap[st.station_id].lines.includes(st.line_code)) {
          stationMap[st.station_id].lines.push(st.line_code);
        }
        stationMap[st.station_id].codes.push(st.station_id);
        stationMap[st.station_id].is_interchange = true;
      }
    });

    const stationNodes = Object.values(stationMap);

    // 3. DRAW CONNECTING TRACKS (SECTORS)
    const rawSectors = sectors.length > 0 ? sectors : mockDefaultSectors;

    rawSectors.forEach((sec) => {
      const startNode = stationNodes.find((s) => s.id === sec.from_station);
      const endNode = stationNodes.find((s) => s.id === sec.to_station);

      if (startNode && endNode) {
        ctx.beginPath();
        ctx.moveTo(startNode.x, startNode.y);
        ctx.lineTo(endNode.x, endNode.y);
        ctx.strokeStyle = lineColors[sec.line_code] || '#64748b';
        ctx.lineWidth = 5;
        ctx.lineCap = 'round';
        ctx.stroke();
      }
    });

    // 4. DRAW NODES (HALF-AND-HALF FOR INTERCHANGES, SOLID FOR SINGLE LINE)
    stationNodes.forEach((st) => {
      const radius = st.is_interchange ? 15 : 11;

      if (st.is_interchange && st.lines.length >= 2) {
        const colorA = lineColors[st.lines[0]] || '#38bdf8';
        const colorB = lineColors[st.lines[1]] || '#f43f5e';

        // Top/Left Half Arc
        ctx.beginPath();
        ctx.arc(st.x, st.y, radius, Math.PI * 0.5, Math.PI * 1.5);
        ctx.fillStyle = colorA;
        ctx.fill();

        // Bottom/Right Half Arc
        ctx.beginPath();
        ctx.arc(st.x, st.y, radius, Math.PI * 1.5, Math.PI * 0.5);
        ctx.fillStyle = colorB;
        ctx.fill();

        // White Divider Ring
        ctx.beginPath();
        ctx.arc(st.x, st.y, radius, 0, Math.PI * 2);
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      } else {
        // Standard Single-Line Station
        const nodeColor = lineColors[st.lines[0]] || '#38bdf8';
        ctx.beginPath();
        ctx.arc(st.x, st.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = nodeColor;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      }

      // 5. LABEL STATIONS WITH ALL RESPECTIVE CODES
      ctx.font = 'bold 11px monospace';
      ctx.fillStyle = '#f1f5f9';
      ctx.textAlign = 'center';
      const codeLabel = st.codes.join(' / ');
      ctx.fillText(codeLabel, st.x, st.y + radius + 15);
    });

    // Attach colors to reference for legend
    canvas._lineColors = lineColors;
  }, [lines, stations, sectors]);

  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 shadow-xl mb-6">
      <div className="flex items-center justify-between mb-3 px-2">
        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
          Ingested Line Topology
        </h4>

        {/* Dynamic Color Legend */}
        <div className="flex gap-4 text-xs font-mono">
          {lines.map((l) => (
            <span key={l.line_code} className="flex items-center gap-1.5 text-slate-300">
              <span
                className="w-3 h-3 rounded-full border border-white/20"
                style={{
                  backgroundColor:
                    canvasRef.current?._lineColors?.[l.line_code] || '#38bdf8',
                }}
              />
              {l.line_code} ({l.line_name || 'Line'})
            </span>
          ))}
        </div>
      </div>

      {/* Static 2D Canvas */}
      <canvas
        ref={canvasRef}
        width={800}
        height={320}
        className="w-full bg-slate-900/80 rounded-lg border border-slate-800/80"
      />
    </div>
  );
}

// Fallback structure for preview before user uploads CSVs
const mockDefaultStations = [
  { station_id: 'STN_ALPHA_1', line_code: 'ALPHA', is_interchange: 0 },
  { station_id: 'STN_ALPHA_2', line_code: 'ALPHA', is_interchange: 1 },
  { station_id: 'STN_BETA_1', line_code: 'BETA', is_interchange: 1 },
  { station_id: 'STN_BETA_2', line_code: 'BETA', is_interchange: 0 },
];

const mockDefaultSectors = [
  { from_station: 'STN_ALPHA_1', to_station: 'STN_ALPHA_2', line_code: 'ALPHA' },
  { from_station: 'STN_ALPHA_2', to_station: 'STN_BETA_2', line_code: 'BETA' },
];