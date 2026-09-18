import React, { useMemo } from "react";
import {
  stationLayout,
  sectorLayout,
  CROSSOVER_BOX,
} from "../../network/layout";
import { COLORS } from "../../network/mapConstants";

export default function NetworkSvgCanvas({
  layers,
  occupancy,
  activities = [],
  selectedActivityId,
  selectedEntity,
  onSelectEntity,
  setTooltip,
}) {
  // 1. Identify active footprints for this week
  const activeLocationsSet = useMemo(() => {
    const set = new Set();
    if (occupancy?.locationOccupancy) {
      Object.keys(occupancy.locationOccupancy).forEach((loc) => set.add(loc));
    }
    return set;
  }, [occupancy]);

  // Buffer locations
  const bufferLocationsSet = useMemo(() => {
    return new Set(Object.keys(occupancy?.protection?.bufferLocations || {}));
  }, [occupancy]);

  // Mirrored locations
  const mirroredLocationsSet = useMemo(() => {
    return new Set(Object.keys(occupancy?.protection?.mirroredLocations || {}));
  }, [occupancy]);

  // Cross-line locations
  const crossLineLocationsSet = useMemo(() => {
    return new Set(Object.keys(occupancy?.protection?.crossLineLocations || {}));
  }, [occupancy]);

  // Selected Activity footprint
  const selectedActivity = useMemo(() => {
    if (!selectedActivityId) return null;
    return activities.find((a) => a.activityId === selectedActivityId);
  }, [activities, selectedActivityId]);

  const selectedActivityLocations = useMemo(() => {
    if (!selectedActivity) return null;
    return new Set(selectedActivity.allProtectedLocations || []);
  }, [selectedActivity]);

  const handleMouseEnter = (e, title, subtitle, extra) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const parentRect = e.currentTarget.closest(".svg-wrapper")?.getBoundingClientRect() || rect;
    setTooltip({
      visible: true,
      x: rect.left - parentRect.left + rect.width / 2,
      y: rect.top - parentRect.top,
      title,
      subtitle,
      extra,
    });
  };

  const handleMouseLeave = () => {
    setTooltip({ visible: false, x: 0, y: 0, title: "", subtitle: "", extra: "" });
  };

  // Static Station IDs
  const alpWestStations = ["S01", "S02", "S03", "S04"];
  const alpEastStations = ["S05", "S06", "S07", "S08"];
  const betWestStations = ["S11", "S12", "S13", "S14"];
  const betEastStations = ["S15", "S16", "S17", "S18"];

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 1060 380"
      width="100%"
      height="100%"
      className="network-svg"
      style={{
        backgroundColor: COLORS.bg,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <defs>
        {/* Shared Gradient */}
        <linearGradient id="sharedGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.8" />
          <stop offset="50%" stopColor="#fbbf24" stopOpacity="1" />
          <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.8" />
        </linearGradient>

        {/* Glow Filter */}
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>

        {/* Strong Selection Glow */}
        <filter id="selectionGlow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>

        {/* Arrow Markers */}
        <marker id="arrowRedEB" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M 0 1 L 7 4 L 0 7 z" fill="#ef4444" />
        </marker>
        <marker id="arrowGreenEB" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M 0 1 L 7 4 L 0 7 z" fill="#10b981" />
        </marker>
        <marker id="arrowCyanEB" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
          <path d="M 0 1 L 7 4 L 0 7 z" fill="#06b6d4" />
        </marker>

        {/* Diagonal Hatch Pattern for Mirrored Closure */}
        <pattern id="mirroredHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="#f97316" strokeWidth="2.5" strokeOpacity="0.8" />
        </pattern>
      </defs>

      {/* Title & Subtitle */}
      <text x="40" y="42" fill="#f8fafc" fontSize="20" fontWeight="700" letterSpacing="0.5">
        Dual-Line Track Access Network Topology
      </text>
      <text x="40" y="66" fill="#94a3b8" fontSize="13">
        Two lines (Line Alpha &amp; Line Beta) with independent bounds (EB/WB), each keeping its own H01↔H02 tunnel sector at the interchange — no shared capacity pool
      </text>

      {/* Directional Bounds Legend */}
      <g transform="translate(680, 28)">
        <rect x="0" y="0" width="340" height="50" rx="8" fill="#1e293b" stroke="#334155" strokeWidth="1" />
        <text x="16" y="22" fill="#cbd5e1" fontSize="12" fontWeight="600">Directional Bounds:</text>
        <path d="M 140 18 L 220 18" stroke="#38bdf8" strokeWidth="2.5" markerEnd="url(#arrowRedEB)" />
        <text x="232" y="22" fill="#38bdf8" fontSize="11" fontWeight="600">EB (Eastbound)</text>
        <path d="M 220 36 L 140 36" stroke="#38bdf8" strokeWidth="2.5" markerEnd="url(#arrowRedEB)" />
        <text x="232" y="40" fill="#38bdf8" fontSize="11" fontWeight="600">WB (Westbound)</text>
      </g>

      {/* ==================== 1. STATIC NETWORK ARTWORK ==================== */}
      <g transform="translate(0, 40)">
        {/* LINE ALPHA Header */}
        <rect x="40" y="85" width="60" height="26" rx="4" fill="#ef4444" />
        <text x="70" y="103" fill="#ffffff" fontSize="13" fontWeight="800" textAnchor="middle">ALP</text>
        <text x="112" y="102" fill="#fca5a5" fontSize="12" fontWeight="600">Metro Line Alpha (Red Line)</text>

        {/* ALP EB Track Line */}
        <path d="M 180 92 L 980 92" stroke="#ef4444" strokeWidth="4" strokeLinecap="round" markerEnd="url(#arrowRedEB)" />
        <text x="995" y="96" fill="#ef4444" fontSize="10" fontWeight="700">EB</text>

        {/* ALP WB Track Line */}
        <path d="M 180 116 L 980 116" stroke="#ef4444" strokeWidth="4" strokeDasharray="6,4" strokeLinecap="round" />
        <path d="M 180 116 L 170 116" stroke="#ef4444" strokeWidth="4" markerEnd="url(#arrowRedEB)" />
        <text x="150" y="120" fill="#ef4444" fontSize="10" fontWeight="700">WB</text>

        {/* ALP H01 & H02 Stations */}
        <rect x="466" y="82" width="24" height="44" rx="5" fill="#f59e0b" stroke="#ef4444" strokeWidth="2.5" />
        <text x="478" y="76" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H01</text>
        <rect x="566" y="82" width="24" height="44" rx="5" fill="#f59e0b" stroke="#ef4444" strokeWidth="2.5" />
        <text x="578" y="76" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H02</text>
        <text x="530" y="138" fill="#fca5a5" fontSize="9" textAnchor="middle">SEC:ALP:H01_H02 (own capacity)</text>

        {/* ALP West Stations S01..S04 */}
        {alpWestStations.map((stnId) => {
          const stn = stationLayout[`ALP:${stnId}`];
          return (
            <g key={`ALP:${stnId}`}>
              <circle cx={stn.x} cy={stn.y} r="8" fill="#1e293b" stroke="#ef4444" strokeWidth="3" />
              <text x={stn.x} y="76" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
            </g>
          );
        })}
        <text x="235" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S01_S02</text>
        <text x="305" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S02_S03</text>
        <text x="375" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S03_S04</text>
        <text x="445" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S04_H01</text>

        {/* ALP East Stations S05..S08 */}
        {alpEastStations.map((stnId) => {
          const stn = stationLayout[`ALP:${stnId}`];
          return (
            <g key={`ALP:${stnId}`}>
              <circle cx={stn.x} cy={stn.y} r="8" fill="#1e293b" stroke="#ef4444" strokeWidth="3" />
              <text x={stn.x} y="76" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
            </g>
          );
        })}
        <text x="615" y="138" fill="#64748b" fontSize="9" textAnchor="middle">H02_S05</text>
        <text x="685" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S05_S06</text>
        <text x="755" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S06_S07</text>
        <text x="825" y="138" fill="#64748b" fontSize="9" textAnchor="middle">S07_S08</text>

        {/* CROSSOVER ZONE */}
        <rect
          x={CROSSOVER_BOX.x}
          y={CROSSOVER_BOX.y}
          width={CROSSOVER_BOX.width}
          height={CROSSOVER_BOX.height}
          rx={CROSSOVER_BOX.rx}
          fill="#1e293b"
          fillOpacity="0.25"
          stroke="#475569"
          strokeWidth="1.5"
          strokeDasharray="4,4"
        />
        {CROSSOVER_BOX.arrows.map((arr, idx) => (
          <path
            key={idx}
            d={`M ${arr.x} ${arr.y1} L ${arr.x} ${arr.y2}`}
            stroke="#94a3b8"
            strokeWidth="1.5"
            strokeDasharray="3,3"
            markerEnd="url(#arrowGreenEB)"
          />
        ))}
        <g transform={`translate(${CROSSOVER_BOX.badge.x}, ${CROSSOVER_BOX.badge.y})`}>
          <rect x="-78" y="-16" width="156" height="34" rx="6" fill="#1e1b4b" stroke="#94a3b8" strokeWidth="1.5" />
          <text x="0" y="-3" fill="#e2e8f0" fontSize="9.5" fontWeight="700" textAnchor="middle">
            {CROSSOVER_BOX.badge.title}
          </text>
          <text x="0" y="10" fill="#94a3b8" fontSize="8" textAnchor="middle">
            {CROSSOVER_BOX.badge.subtitle}
          </text>
        </g>

        {/* LINE BETA Header */}
        <rect x="40" y="261" width="60" height="26" rx="4" fill="#10b981" />
        <text x="70" y="279" fill="#ffffff" fontSize="13" fontWeight="800" textAnchor="middle">BET</text>
        <text x="112" y="278" fill="#a7f3d0" fontSize="12" fontWeight="600">Metro Line Beta (Green Line)</text>

        {/* BET EB Track Line */}
        <path d="M 180 268 L 980 268" stroke="#10b981" strokeWidth="4" strokeLinecap="round" markerEnd="url(#arrowGreenEB)" />
        <text x="995" y="272" fill="#10b981" fontSize="10" fontWeight="700">EB</text>

        {/* BET WB Track Line */}
        <path d="M 180 292 L 980 292" stroke="#10b981" strokeWidth="4" strokeDasharray="6,4" strokeLinecap="round" />
        <path d="M 180 292 L 170 292" stroke="#10b981" strokeWidth="4" markerEnd="url(#arrowGreenEB)" />
        <text x="150" y="296" fill="#10b981" fontSize="10" fontWeight="700">WB</text>

        {/* BET H01 & H02 Stations */}
        <rect x="466" y="258" width="24" height="44" rx="5" fill="#f59e0b" stroke="#10b981" strokeWidth="2.5" />
        <text x="478" y="322" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H01</text>
        <rect x="566" y="258" width="24" height="44" rx="5" fill="#f59e0b" stroke="#10b981" strokeWidth="2.5" />
        <text x="578" y="322" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H02</text>
        <text x="530" y="254" fill="#a7f3d0" fontSize="9" textAnchor="middle">SEC:BET:H01_H02 (own capacity)</text>

        {/* BET West Stations S11..S14 */}
        {betWestStations.map((stnId) => {
          const stn = stationLayout[`BET:${stnId}`];
          return (
            <g key={`BET:${stnId}`}>
              <circle cx={stn.x} cy={stn.y} r="8" fill="#1e293b" stroke="#10b981" strokeWidth="3" />
              <text x={stn.x} y="315" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
            </g>
          );
        })}
        <text x="235" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S11_S12</text>
        <text x="305" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S12_S13</text>
        <text x="375" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S13_S14</text>
        <text x="445" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S14_H01</text>

        {/* BET East Stations S15..S18 */}
        {betEastStations.map((stnId) => {
          const stn = stationLayout[`BET:${stnId}`];
          return (
            <g key={`BET:${stnId}`}>
              <circle cx={stn.x} cy={stn.y} r="8" fill="#1e293b" stroke="#10b981" strokeWidth="3" />
              <text x={stn.x} y="315" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
            </g>
          );
        })}
        <text x="615" y="254" fill="#64748b" fontSize="9" textAnchor="middle">H02_S15</text>
        <text x="685" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S15_S16</text>
        <text x="755" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S16_S17</text>
        <text x="825" y="254" fill="#64748b" fontSize="9" textAnchor="middle">S17_S18</text>

        {/* ==================== 2. ACTIVITY ISOLATION DIMMING LAYER ==================== */}
        {selectedActivityLocations && (
          <rect
            x="0"
            y="0"
            width="1060"
            height="340"
            fill="#0f172a"
            fillOpacity="0.75"
            pointerEvents="none"
          />
        )}

        {/* ==================== 3. SAFETY BUFFERS OVERLAY ==================== */}
        {layers.buffers && (
          <g className="buffer-overlay-layer">
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const isBuffer = bufferLocationsSet.has(locId);
              const isFocus = selectedActivityLocations ? selectedActivity.bufferLocations.includes(locId) : false;
              if (!isBuffer && !isFocus) return null;

              return (
                <line
                  key={`buf-sec-${locId}`}
                  x1={sec.x1}
                  y1={sec.y}
                  x2={sec.x2}
                  y2={sec.y}
                  stroke="#f59e0b"
                  strokeWidth="8"
                  strokeDasharray="6,4"
                  strokeOpacity="0.85"
                  pointerEvents="none"
                />
              );
            })}
          </g>
        )}

        {/* ==================== 4. OPPOSITE-BOUND MIRRORED CLOSURE ==================== */}
        {layers.mirrored && (
          <g className="mirrored-overlay-layer">
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const isMirrored = mirroredLocationsSet.has(locId);
              const isFocus = selectedActivityLocations ? selectedActivity.mirroredLocations.includes(locId) : false;
              if (!isMirrored && !isFocus) return null;

              return (
                <rect
                  key={`mir-sec-${locId}`}
                  x={sec.x1}
                  y={sec.y - 5}
                  width={sec.x2 - sec.x1}
                  height="10"
                  fill="url(#mirroredHatch)"
                  stroke="#f97316"
                  strokeWidth="1"
                  pointerEvents="none"
                />
              );
            })}
          </g>
        )}

        {/* ==================== 5. CROSS-LINE INTERCHANGE PROTECTION ==================== */}
        {layers.crossLine && (
          <g className="crossline-overlay-layer">
            {/* Live crossover highlighted tracks at H01-H02 */}
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const isCrossLine = crossLineLocationsSet.has(locId);
              const isFocus = selectedActivityLocations ? selectedActivity.crossLineLocations.includes(locId) : false;
              if (!isCrossLine && !isFocus) return null;

              return (
                <line
                  key={`cross-sec-${locId}`}
                  x1={sec.x1}
                  y1={sec.y}
                  x2={sec.x2}
                  y2={sec.y}
                  stroke="#a855f7"
                  strokeWidth="7"
                  strokeOpacity="0.9"
                  filter="url(#glow)"
                  pointerEvents="none"
                />
              );
            })}

            {/* Vertical interchange shafts if active */}
            {(crossLineLocationsSet.size > 0 || (selectedActivity && selectedActivity.crossLineLocations.length > 0)) && (
              <>
                <line x1="478" y1="126" x2="478" y2="232" stroke="#c084fc" strokeWidth="3" filter="url(#glow)" pointerEvents="none" />
                <line x1="578" y1="126" x2="578" y2="232" stroke="#c084fc" strokeWidth="3" filter="url(#glow)" pointerEvents="none" />
              </>
            )}
          </g>
        )}

        {/* ==================== 6. CORE WORK FOOTPRINTS ==================== */}
        {layers.core && (
          <g className="core-overlay-layer">
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const isCoreActive = activeLocationsSet.has(locId);
              const isFocus = selectedActivityLocations ? selectedActivity.coreLocations.includes(locId) : false;
              if (!isCoreActive && !isFocus) return null;

              return (
                <line
                  key={`core-sec-${locId}`}
                  x1={sec.x1}
                  y1={sec.y}
                  x2={sec.x2}
                  y2={sec.y}
                  stroke="#06b6d4"
                  strokeWidth="6"
                  strokeLinecap="round"
                  filter="url(#glow)"
                  pointerEvents="none"
                />
              );
            })}

            {/* Core platforms */}
            {Object.entries(stationLayout).map(([stnKey, stn]) => {
              const ebPlat = `PLAT:${stn.lineCode}:${stn.stationId}:EB`;
              const wbPlat = `PLAT:${stn.lineCode}:${stn.stationId}:WB`;
              const isEbActive = activeLocationsSet.has(ebPlat) || (selectedActivityLocations && selectedActivity.coreLocations.includes(ebPlat));
              const isWbActive = activeLocationsSet.has(wbPlat) || (selectedActivityLocations && selectedActivity.coreLocations.includes(wbPlat));

              if (!isEbActive && !isWbActive) return null;

              if (stn.isInterchange) {
                return (
                  <rect
                    key={`core-stn-${stnKey}`}
                    x={stn.rectX - 2}
                    y={stn.rectY - 2}
                    width={stn.width + 4}
                    height={stn.height + 4}
                    rx={stn.rx || 6}
                    fill="none"
                    stroke="#06b6d4"
                    strokeWidth="3"
                    filter="url(#glow)"
                    pointerEvents="none"
                  />
                );
              }

              return (
                <circle
                  key={`core-stn-${stnKey}`}
                  cx={stn.x}
                  cy={stn.y}
                  r="12"
                  fill="none"
                  stroke="#06b6d4"
                  strokeWidth="3"
                  filter="url(#glow)"
                  pointerEvents="none"
                />
              );
            })}
          </g>
        )}

        {/* ==================== 7. CAPACITY ALERT LAYER ==================== */}
        {layers.capacity && (
          <g className="capacity-alert-layer">
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const occ = occupancy?.locationOccupancy?.[locId];
              if (!occ || !occ.capacityExceeded) return null;

              return (
                <g key={`cap-sec-${locId}`} transform={`translate(${sec.midX}, ${sec.y - 14})`}>
                  <rect x="-20" y="-9" width="40" height="18" rx="4" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
                  <text x="0" y="3.5" fill="#ffffff" fontSize="9" fontWeight="900" textAnchor="middle">
                    [{occ.peakOccupiedGroupCount}/{occ.supplyCapacity}]
                  </text>
                </g>
              );
            })}
          </g>
        )}

        {/* ==================== 8. SELECTION HIGHLIGHT RING ==================== */}
        {selectedEntity && (
          <g className="selection-highlight-layer" pointerEvents="none">
            {selectedEntity.type === "sector" && sectorLayout[selectedEntity.id] && (
              <line
                x1={sectorLayout[selectedEntity.id].x1}
                y1={sectorLayout[selectedEntity.id].y}
                x2={sectorLayout[selectedEntity.id].x2}
                y2={sectorLayout[selectedEntity.id].y}
                stroke="#38bdf8"
                strokeWidth="10"
                strokeOpacity="0.8"
                filter="url(#selectionGlow)"
              />
            )}

            {selectedEntity.type === "station" && stationLayout[selectedEntity.id] && (
              stationLayout[selectedEntity.id].isInterchange ? (
                <rect
                  x={stationLayout[selectedEntity.id].rectX - 4}
                  y={stationLayout[selectedEntity.id].rectY - 4}
                  width={stationLayout[selectedEntity.id].width + 8}
                  height={stationLayout[selectedEntity.id].height + 8}
                  rx="8"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="3.5"
                  filter="url(#selectionGlow)"
                />
              ) : (
                <circle
                  cx={stationLayout[selectedEntity.id].x}
                  cy={stationLayout[selectedEntity.id].y}
                  r="15"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="3.5"
                  filter="url(#selectionGlow)"
                />
              )
            )}
          </g>
        )}

        {/* ==================== 9. INTERACTION HIT TARGETS ==================== */}
        <g className="interaction-hit-targets">
          {/* Clickable EB/WB Sector Segments */}
          {Object.entries(sectorLayout).map(([locId, sec]) => {
            const occ = occupancy?.locationOccupancy?.[locId];
            const subtitle = `Bound: ${sec.bound} • Capacity: ${occ ? `${occ.peakOccupiedGroupCount}/${occ.supplyCapacity}` : "Nominal 2"}`;
            const extra = occ ? `${occ.activeActivities.length} active activities` : "No active work";

            return (
              <line
                key={`hit-${locId}`}
                x1={sec.x1}
                y1={sec.y}
                x2={sec.x2}
                y2={sec.y}
                stroke="transparent"
                strokeWidth="20"
                className="interactive-sector"
                role="button"
                tabIndex={0}
                aria-label={`${sec.lineCode} Sector ${sec.slug} ${sec.bound}`}
                onClick={() => onSelectEntity({ type: "sector", id: locId })}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectEntity({ type: "sector", id: locId });
                  }
                }}
                onMouseEnter={(e) => handleMouseEnter(e, locId, subtitle, extra)}
                onMouseLeave={handleMouseLeave}
              />
            );
          })}

          {/* Clickable Stations */}
          {Object.entries(stationLayout).map(([stnKey, stn]) => {
            const isInterchange = stn.isInterchange;
            const ebPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:EB`;
            const wbPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:WB`;
            const ebOcc = occupancy?.locationOccupancy?.[ebPlatId];
            const wbOcc = occupancy?.locationOccupancy?.[wbPlatId];
            const subtitle = isInterchange ? `${stn.lineCode} Interchange Station` : `${stn.lineCode} Line Station`;
            const extra = `EB: ${ebOcc?.peakOccupiedGroupCount || 0}/2, WB: ${wbOcc?.peakOccupiedGroupCount || 0}/2`;

            if (isInterchange) {
              return (
                <rect
                  key={`hit-stn-${stnKey}`}
                  x={stn.rectX - 2}
                  y={stn.rectY - 2}
                  width={stn.width + 4}
                  height={stn.height + 4}
                  fill="transparent"
                  className="interactive-station"
                  role="button"
                  tabIndex={0}
                  aria-label={`${stn.lineCode} Station ${stn.stationId} Interchange`}
                  onClick={() => onSelectEntity({ type: "station", id: stnKey })}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectEntity({ type: "station", id: stnKey });
                    }
                  }}
                  onMouseEnter={(e) => handleMouseEnter(e, `${stn.lineCode} Station ${stn.stationId}`, subtitle, extra)}
                  onMouseLeave={handleMouseLeave}
                />
              );
            }

            return (
              <circle
                key={`hit-stn-${stnKey}`}
                cx={stn.x}
                cy={stn.y}
                r="16"
                fill="transparent"
                className="interactive-station"
                role="button"
                tabIndex={0}
                aria-label={`${stn.lineCode} Station ${stn.stationId}`}
                onClick={() => onSelectEntity({ type: "station", id: stnKey })}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectEntity({ type: "station", id: stnKey });
                  }
                }}
                onMouseEnter={(e) => handleMouseEnter(e, `${stn.lineCode} Station ${stn.stationId}`, subtitle, extra)}
                onMouseLeave={handleMouseLeave}
              />
            );
          })}
        </g>
      </g>
    </svg>
  );
}
