import React, { useMemo } from "react";
import {
  stationLayout,
  sectorLayout,
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
  currentWeek = 1,
}) {
  // 1. Identify active footprints for this week
  const activeLocationsSet = useMemo(() => {
    const set = new Set();
    if (occupancy?.locationOccupancy) {
      Object.keys(occupancy.locationOccupancy).forEach((loc) => set.add(loc));
    }
    return set;
  }, [occupancy]);
  const maintenanceLocations = useMemo(() => new Set((occupancy?.maintenance || [])
    .filter((visit) => !visit.week || visit.week === currentWeek)
    .flatMap((visit) => visit.location_ids || (visit.sector_id ? [visit.sector_id] : []))), [occupancy, currentWeek]);

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

  // Selected Activity footprint & active status
  const selectedActivity = useMemo(() => {
    if (!selectedActivityId) return null;
    return activities.find((a) => a.activityId === selectedActivityId);
  }, [activities, selectedActivityId]);

  const selectedActivityLocations = useMemo(() => {
    if (!selectedActivity) return null;
    return new Set(selectedActivity.allProtectedLocations || []);
  }, [selectedActivity]);

  const isSelectedActiveThisWeek = useMemo(() => {
    if (!selectedActivityId || !occupancy?.activeActivities) return false;
    return occupancy.activeActivities.includes(selectedActivityId);
  }, [selectedActivityId, occupancy]);

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

  // Toggle selection on click (Item 1: Deselect if currently selected)
  const handleSectorClick = (locId) => {
    if (selectedEntity && selectedEntity.type === "sector" && selectedEntity.id === locId) {
      onSelectEntity(null);
    } else {
      onSelectEntity({ type: "sector", id: locId });
    }
  };

  const handleStationClick = (stnKey) => {
    if (selectedEntity && selectedEntity.type === "station" && selectedEntity.id === stnKey) {
      onSelectEntity(null);
    } else {
      onSelectEntity({ type: "station", id: stnKey });
    }
  };

  const alpWestStations = ["S01", "S02", "S03", "S04"];
  const alpEastStations = ["S05", "S06", "S07", "S08"];
  const betWestStations = ["S11", "S12", "S13", "S14"];
  const betEastStations = ["S15", "S16", "S17", "S18"];

  return (
    <div className="relative w-full h-full">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 1060 320"
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

          {/* Arrow Markers for Track Ends */}
          <marker id="arrowRedEB" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M 0 1 L 7 4 L 0 7 z" fill="#ef4444" />
          </marker>
          <marker id="arrowGreenEB" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M 0 1 L 7 4 L 0 7 z" fill="#10b981" />
          </marker>

          {/* Interchange Connecting Arrowhead pointing towards and touching the stations (Item 5) */}
          <marker id="arrowGreyTip" markerWidth="7" markerHeight="7" refX="7" refY="3.5" orient="auto">
            <path d="M 1 1 L 7 3.5 L 1 6 z" fill="#94a3b8" />
          </marker>

          {/* Diagonal Hatch Pattern for Mirrored Closure */}
          <pattern id="mirroredHatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="8" stroke="#f97316" strokeWidth="2.5" strokeOpacity="0.8" />
          </pattern>
        </defs>

        <g>
          {/* ==================== 1. STATIC NETWORK ARTWORK ==================== */}
          <g>
            {/* Item 3: ALP Badge Box labeling the top line */}
            <rect x="45" y="91" width="55" height="26" rx="5" fill="#ef4444" />
            <text x="72.5" y="109" fill="#ffffff" fontSize="12" fontWeight="800" textAnchor="middle">ALP</text>

            {/* Item 2: ALP EB Track Line extended to align with WB line at x=120 */}
            <path d="M 120 92 L 980 92" stroke="#ef4444" strokeWidth="4" strokeLinecap="round" markerEnd="url(#arrowRedEB)" />
            {/* Right-side Terminal Marker */}
            <text x="990" y="96" fill="#ef4444" fontSize="10" fontWeight="800">EB →</text>

            {/* ALP WB Track Line: extended westward past station circle */}
            <path d="M 120 116 L 980 116" stroke="#ef4444" strokeWidth="4" strokeDasharray="6,4" strokeLinecap="round" />
            <path d="M 180 116 L 120 116" stroke="#ef4444" strokeWidth="4" markerEnd="url(#arrowRedEB)" />
            {/* Right-side Terminal Marker */}
            <text x="990" y="120" fill="#fca5a5" fontSize="10" fontWeight="700">← WB</text>

            {/* Item 4: ALP H01 & H02 Diamonds (Top tip y=92 aligned to EB, bottom tip y=116 aligned to WB) */}
            {/* H01 Diamond at x=478: top (478, 92), right (491, 104), bottom (478, 116), left (465, 104) */}
            <polygon
              points="478,92 491,104 478,116 465,104"
              fill="#f59e0b"
              stroke="#ef4444"
              strokeWidth="2.5"
            />
            <text x="478" y="76" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H01</text>

            {/* H02 Diamond at x=578: top (578, 92), right (591, 104), bottom (578, 116), left (565, 104) */}
            <polygon
              points="578,92 591,104 578,116 565,104"
              fill="#f59e0b"
              stroke="#ef4444"
              strokeWidth="2.5"
            />
            <text x="578" y="76" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H02</text>

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

            {/* Item 5: INTERCHANGE CONNECTING ARROWS pointing towards and touching the station diamond tips */}
            {/* H01 Connection: Arrow pointing UP touching ALP diamond bottom (y=116), and arrow pointing DOWN touching BET diamond top (y=228) */}
            <line
              x1="478"
              y1="172"
              x2="478"
              y2="116"
              stroke="#94a3b8"
              strokeWidth="2"
              strokeDasharray="4,3"
              markerEnd="url(#arrowGreyTip)"
            />
            <line
              x1="478"
              y1="172"
              x2="478"
              y2="228"
              stroke="#94a3b8"
              strokeWidth="2"
              strokeDasharray="4,3"
              markerEnd="url(#arrowGreyTip)"
            />

            {/* H02 Connection: Arrow pointing UP touching ALP diamond bottom (y=116), and arrow pointing DOWN touching BET diamond top (y=228) */}
            <line
              x1="578"
              y1="172"
              x2="578"
              y2="116"
              stroke="#94a3b8"
              strokeWidth="2"
              strokeDasharray="4,3"
              markerEnd="url(#arrowGreyTip)"
            />
            <line
              x1="578"
              y1="172"
              x2="578"
              y2="228"
              stroke="#94a3b8"
              strokeWidth="2"
              strokeDasharray="4,3"
              markerEnd="url(#arrowGreyTip)"
            />

            {/* Item 3: BET Badge Box labeling the bottom line */}
            <rect x="45" y="227" width="55" height="26" rx="5" fill="#10b981" />
            <text x="72.5" y="245" fill="#ffffff" fontSize="12" fontWeight="800" textAnchor="middle">BET</text>

            {/* Item 2: BET EB Track Line extended to align with WB line at x=120 */}
            <path d="M 120 228 L 980 228" stroke="#10b981" strokeWidth="4" strokeLinecap="round" markerEnd="url(#arrowGreenEB)" />
            {/* Right-side Terminal Marker */}
            <text x="990" y="232" fill="#10b981" fontSize="10" fontWeight="800">EB →</text>

            {/* BET WB Track Line: extended westward past station circle */}
            <path d="M 120 252 L 980 252" stroke="#10b981" strokeWidth="4" strokeDasharray="6,4" strokeLinecap="round" />
            <path d="M 180 252 L 120 252" stroke="#10b981" strokeWidth="4" markerEnd="url(#arrowGreenEB)" />
            {/* Right-side Terminal Marker */}
            <text x="990" y="256" fill="#a7f3d0" fontSize="10" fontWeight="700">← WB</text>

            {/* Item 4: BET H01 & H02 Diamonds (Top tip y=228 aligned to EB, bottom tip y=252 aligned to WB) */}
            {/* H01 Diamond at x=478: top (478, 228), right (491, 240), bottom (478, 252), left (465, 240) */}
            <polygon
              points="478,228 491,240 478,252 465,240"
              fill="#f59e0b"
              stroke="#10b981"
              strokeWidth="2.5"
            />
            <text x="478" y="275" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H01</text>

            {/* H02 Diamond at x=578: top (578, 228), right (591, 240), bottom (578, 252), left (565, 240) */}
            <polygon
              points="578,228 591,240 578,252 565,240"
              fill="#f59e0b"
              stroke="#10b981"
              strokeWidth="2.5"
            />
            <text x="578" y="275" fill="#fbbf24" fontSize="11" fontWeight="800" textAnchor="middle">H02</text>

            {/* BET West Stations S11..S14 */}
            {betWestStations.map((stnId) => {
              const stn = stationLayout[`BET:${stnId}`];
              const yAdjusted = stn.y - 40;
              return (
                <g key={`BET:${stnId}`}>
                  <circle cx={stn.x} cy={yAdjusted} r="8" fill="#1e293b" stroke="#10b981" strokeWidth="3" />
                  <text x={stn.x} y="275" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
                </g>
              );
            })}

            {/* BET East Stations S15..S18 */}
            {betEastStations.map((stnId) => {
              const stn = stationLayout[`BET:${stnId}`];
              const yAdjusted = stn.y - 40;
              return (
                <g key={`BET:${stnId}`}>
                  <circle cx={stn.x} cy={yAdjusted} r="8" fill="#1e293b" stroke="#10b981" strokeWidth="3" />
                  <text x={stn.x} y="275" fill="#f8fafc" fontSize="12" fontWeight="600" textAnchor="middle">{stnId}</text>
                </g>
              );
            })}
          </g>

          {/* ==================== 2. ACTIVITY ISOLATION DIMMING LAYER ==================== */}
          {selectedActivityLocations && (
            <rect
              x="0"
              y="0"
              width="1060"
              height="320"
              fill="#0f172a"
              fillOpacity="0.75"
              pointerEvents="none"
            />
          )}

          {/* ==================== PLANNED INACTIVE FOOTPRINT LAYER ==================== */}
          {selectedActivity && !isSelectedActiveThisWeek && (
            <g className="planned-inactive-footprint-layer">
              {selectedActivity.coreLocations.map((locId) => {
                const sec = sectorLayout[locId];
                if (sec) {
                  const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                  return (
                    <line
                      key={`inactive-core-sec-${locId}`}
                      x1={sec.x1}
                      y1={secY}
                      x2={sec.x2}
                      y2={secY}
                      stroke="#94a3b8"
                      strokeWidth="4"
                      strokeDasharray="4,4"
                      strokeOpacity="0.85"
                      pointerEvents="none"
                    />
                  );
                }
                return null;
              })}

              {/* Banner notice on canvas */}
              <g transform="translate(530, 30)">
                <rect x="-175" y="-12" width="350" height="24" rx="12" fill="#1e293b" stroke="#64748b" strokeWidth="1" />
                <text x="0" y="4" fill="#cbd5e1" fontSize="10.5" fontWeight="600" textAnchor="middle">
                  Planned Footprint: {selectedActivity.activityId} (Not scheduled in Week {currentWeek})
                </text>
              </g>
            </g>
          )}

          {/* ==================== 3. SAFETY BUFFERS OVERLAY ==================== */}
          {layers.buffers && (
            <g className="buffer-overlay-layer">
              {Object.entries(sectorLayout).map(([locId, sec]) => {
                const isBuffer = bufferLocationsSet.has(locId);
                const isFocus = selectedActivityLocations && isSelectedActiveThisWeek
                  ? selectedActivity.bufferLocations.includes(locId)
                  : false;
                if (!isBuffer && !isFocus) return null;

                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <line
                    key={`buf-sec-${locId}`}
                    x1={sec.x1}
                    y1={secY}
                    x2={sec.x2}
                    y2={secY}
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
                const isFocus = selectedActivityLocations && isSelectedActiveThisWeek
                  ? selectedActivity.mirroredLocations.includes(locId)
                  : false;
                if (!isMirrored && !isFocus) return null;

                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <rect
                    key={`mir-sec-${locId}`}
                    x={sec.x1}
                    y={secY - 5}
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
              {Object.entries(sectorLayout).map(([locId, sec]) => {
                const isCrossLine = crossLineLocationsSet.has(locId);
                const isFocus = selectedActivityLocations && isSelectedActiveThisWeek
                  ? selectedActivity.crossLineLocations.includes(locId)
                  : false;
                if (!isCrossLine && !isFocus) return null;

                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <line
                    key={`cross-sec-${locId}`}
                    x1={sec.x1}
                    y1={secY}
                    x2={sec.x2}
                    y2={secY}
                    stroke="#a855f7"
                    strokeWidth="7"
                    strokeOpacity="0.9"
                    pointerEvents="none"
                  />
                );
              })}

              {/* Vertical interchange shafts if active */}
              {(crossLineLocationsSet.size > 0 || (selectedActivity && isSelectedActiveThisWeek && selectedActivity.crossLineLocations.length > 0)) && (
                <>
                  <line x1="478" y1="116" x2="478" y2="228" stroke="#c084fc" strokeWidth="3" pointerEvents="none" />
                  <line x1="578" y1="116" x2="578" y2="228" stroke="#c084fc" strokeWidth="3" pointerEvents="none" />
                </>
              )}
            </g>
          )}

          {/* ==================== 6. CORE WORK FOOTPRINTS (Item 3: Sectors & Stations Highlighted Cyan) ==================== */}
          {layers.core && (
            <g className="core-overlay-layer">
              {/* Highlight active core sectors */}
              {Object.entries(sectorLayout).map(([locId, sec]) => {
                const isCoreActive = activeLocationsSet.has(locId);
                const isFocus = selectedActivityLocations && isSelectedActiveThisWeek
                  ? selectedActivity.coreLocations.includes(locId)
                  : false;

                const shouldHighlight = selectedActivityLocations ? isFocus : isCoreActive;
                if (!shouldHighlight) return null;

                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <g key={`core-sec-${locId}`}>
                    {/* Glowing outer cyan stroke */}
                    <line
                      x1={sec.x1}
                      y1={secY}
                      x2={sec.x2}
                      y2={secY}
                      stroke="#06b6d4"
                      strokeWidth="8"
                      strokeLinecap="round"
                      strokeOpacity="0.9"
                      pointerEvents="none"
                    />
                    {/* Bright inner cyan core line */}
                    <line
                      x1={sec.x1}
                      y1={secY}
                      x2={sec.x2}
                      y2={secY}
                      stroke="#a5f3fc"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      strokeOpacity="1"
                      pointerEvents="none"
                    />
                  </g>
                );
              })}

              {/* Highlight active core station platforms */}
              {Object.entries(stationLayout).map(([stnKey, stn]) => {
                const ebPlat = `PLAT:${stn.lineCode}:${stn.stationId}:EB`;
                const wbPlat = `PLAT:${stn.lineCode}:${stn.stationId}:WB`;

                const isEbActive = selectedActivityLocations
                  ? (isSelectedActiveThisWeek && selectedActivity.coreLocations.includes(ebPlat))
                  : activeLocationsSet.has(ebPlat);
                const isWbActive = selectedActivityLocations
                  ? (isSelectedActiveThisWeek && selectedActivity.coreLocations.includes(wbPlat))
                  : activeLocationsSet.has(wbPlat);

                if (!isEbActive && !isWbActive) return null;

                const yAdjusted = stn.lineCode === "BET" ? stn.y - 40 : stn.y;

                if (stn.isInterchange) {
                  const cx = stn.x;
                  const isTop = stn.lineCode === "ALP";
                  const topY = isTop ? 92 : 228;
                  const midY = isTop ? 104 : 240;
                  const botY = isTop ? 116 : 252;

                  return (
                    <g key={`core-stn-${stnKey}`}>
                      <polygon
                        points={`${cx},${topY - 4} ${cx + 17},${midY} ${cx},${botY + 4} ${cx - 17},${midY}`}
                        fill="none"
                        stroke="#06b6d4"
                        strokeWidth="3.5"
                        pointerEvents="none"
                      />
                      <polygon
                        points={`${cx},${topY - 1} ${cx + 14},${midY} ${cx},${botY + 1} ${cx - 14},${midY}`}
                        fill="none"
                        stroke="#a5f3fc"
                        strokeWidth="1.5"
                        pointerEvents="none"
                      />
                    </g>
                  );
                }

                return (
                  <g key={`core-stn-${stnKey}`}>
                    <circle
                      cx={stn.x}
                      cy={yAdjusted}
                      r="13"
                      fill="none"
                      stroke="#06b6d4"
                      strokeWidth="3.5"
                      pointerEvents="none"
                    />
                    <circle
                      cx={stn.x}
                      cy={yAdjusted}
                      r="11.5"
                      fill="none"
                      stroke="#a5f3fc"
                      strokeWidth="1.5"
                      pointerEvents="none"
                    />
                  </g>
                );
              })}
            </g>
          )}

          {layers.maintenance && maintenanceLocations.size > 0 && (
            <g className="maintenance-overlay-layer">
              {Object.entries(sectorLayout).map(([locId, sec]) => {
                if (!maintenanceLocations.has(locId)) return null;
                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return <g key={`maint-sec-${locId}`}><line x1={sec.x1} y1={secY} x2={sec.x2} y2={secY} stroke="#fbbf24" strokeWidth="10" strokeOpacity="0.9" strokeDasharray="3,3" /><text x={sec.midX} y={secY - 9} fill="#fde68a" fontSize="9" fontWeight="800" textAnchor="middle">MAINT</text></g>;
              })}
              {Object.entries(stationLayout).map(([key, stn]) => {
                const ids = [`PLAT:${stn.lineCode}:${stn.stationId}:EB`, `PLAT:${stn.lineCode}:${stn.stationId}:WB`];
                if (!ids.some((id) => maintenanceLocations.has(id))) return null;
                const y = stn.lineCode === "BET" ? stn.y - 40 : stn.y;
                return <g key={`maint-stn-${key}`}><circle cx={stn.x} cy={y} r="15" fill="#f59e0b" fillOpacity="0.25" stroke="#fbbf24" strokeWidth="3" strokeDasharray="4,2" /><text x={stn.x} y={y - 20} fill="#fde68a" fontSize="8" fontWeight="800" textAnchor="middle">MAINT</text></g>;
              })}
            </g>
          )}

          {/* ==================== 7. CAPACITY ALERT LAYER ==================== */}
          {layers.capacity && (
            <g className="capacity-alert-layer">
              {/* Sector Overload Alerts */}
              {Object.entries(sectorLayout).map(([locId, sec]) => {
                const occ = occupancy?.locationOccupancy?.[locId];
                if (!occ || !occ.capacityExceeded) return null;

                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <g key={`cap-sec-${locId}`} transform={`translate(${sec.midX}, ${secY - 14})`}>
                    <rect x="-24" y="-9" width="48" height="18" rx="4" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
                    <text x="0" y="3.5" fill="#ffffff" fontSize="9" fontWeight="900" textAnchor="middle">
                      ▲ [{occ.peakOccupiedGroupCount}/{occ.supplyCapacity}]
                    </text>
                  </g>
                );
              })}

              {/* Platform Overload Alerts */}
              {Object.entries(stationLayout).map(([stnKey, stn]) => {
                const ebPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:EB`;
                const wbPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:WB`;
                const ebOcc = occupancy?.locationOccupancy?.[ebPlatId];
                const wbOcc = occupancy?.locationOccupancy?.[wbPlatId];
                const ebAlert = ebOcc?.capacityExceeded;
                const wbAlert = wbOcc?.capacityExceeded;
                if (!ebAlert && !wbAlert) return null;

                const overOcc = ebAlert ? ebOcc : wbOcc;
                const stnY = stn.lineCode === "BET" ? stn.y - 40 : stn.y;
                const badgeY = stn.lineCode === "ALP" ? stnY - 20 : stnY + 22;

                return (
                  <g key={`cap-stn-${stnKey}`} transform={`translate(${stn.x}, ${badgeY})`}>
                    <circle cx="0" cy="0" r="14" fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="3,3" />
                    <rect x="-24" y="-9" width="48" height="18" rx="4" fill="#ef4444" stroke="#ffffff" strokeWidth="1.5" />
                    <text x="0" y="3.5" fill="#ffffff" fontSize="9" fontWeight="900" textAnchor="middle">
                      ▲ [{overOcc.peakOccupiedGroupCount}/{overOcc.supplyCapacity}]
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {/* ==================== 8. SELECTION HIGHLIGHT ==================== */}
          {selectedEntity && (
            <g className="selection-highlight-layer" pointerEvents="none">
              {selectedEntity.type === "sector" && sectorLayout[selectedEntity.id] && (() => {
                const sec = sectorLayout[selectedEntity.id];
                const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;
                return (
                  <line
                    x1={sec.x1}
                    y1={secY}
                    x2={sec.x2}
                    y2={secY}
                    stroke="#ffffff"
                    strokeWidth="5"
                    strokeLinecap="round"
                  />
                );
              })()}

              {selectedEntity.type === "station" && stationLayout[selectedEntity.id] && (() => {
                const stn = stationLayout[selectedEntity.id];
                const yAdjusted = stn.lineCode === "BET" ? stn.y - 40 : stn.y;

                if (stn.isInterchange) {
                  const cx = stn.x;
                  const isTop = stn.lineCode === "ALP";
                  const topY = isTop ? 92 : 228;
                  const midY = isTop ? 104 : 240;
                  const botY = isTop ? 116 : 252;

                  return (
                    <polygon
                      points={`${cx},${topY - 4} ${cx + 17},${midY} ${cx},${botY + 4} ${cx - 17},${midY}`}
                      fill="none"
                      stroke="#ffffff"
                      strokeWidth="3.5"
                    />
                  );
                }

                return (
                  <circle
                    cx={stn.x}
                    cy={yAdjusted}
                    r="15"
                    fill="none"
                    stroke="#ffffff"
                    strokeWidth="3.5"
                  />
                );
              })()}
            </g>
          )}

          {/* ==================== 9. INTERACTION HIT TARGETS ==================== */}
          <g className="interaction-hit-targets">
            {/* Clickable EB/WB Sector Segments (Item 1: Deselects on second click) */}
            {Object.entries(sectorLayout).map(([locId, sec]) => {
              const occ = occupancy?.locationOccupancy?.[locId];
              const subtitle = `Bound: ${sec.bound} • Capacity: ${occ ? `${occ.peakOccupiedGroupCount}/${occ.supplyCapacity}` : "Nominal 2"}`;
              const extra = occ ? `${occ.activeActivities.length} active activities` : "No active work";
              const secY = sec.lineCode === "BET" ? sec.y - 40 : sec.y;

              return (
                <line
                  key={`hit-${locId}`}
                  x1={sec.x1}
                  y1={secY}
                  x2={sec.x2}
                  y2={secY}
                  stroke="transparent"
                  strokeWidth="22"
                  className="interactive-sector"
                  role="button"
                  tabIndex={0}
                  aria-label={`${sec.lineCode} Sector ${sec.slug} ${sec.bound}`}
                  onClick={() => handleSectorClick(locId)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleSectorClick(locId);
                    }
                  }}
                  onMouseEnter={(e) => handleMouseEnter(e, locId, subtitle, extra)}
                  onMouseLeave={handleMouseLeave}
                />
              );
            })}

            {/* Clickable Stations (Item 1: Deselects on second click) */}
            {Object.entries(stationLayout).map(([stnKey, stn]) => {
              const isInterchange = stn.isInterchange;
              const ebPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:EB`;
              const wbPlatId = `PLAT:${stn.lineCode}:${stn.stationId}:WB`;
              const ebOcc = occupancy?.locationOccupancy?.[ebPlatId];
              const wbOcc = occupancy?.locationOccupancy?.[wbPlatId];
              const subtitle = isInterchange ? `${stn.lineCode} Interchange Station` : `${stn.lineCode} Line Station`;
              const extra = `EB: ${ebOcc?.peakOccupiedGroupCount || 0}/2, WB: ${wbOcc?.peakOccupiedGroupCount || 0}/2`;
              const yAdjusted = stn.lineCode === "BET" ? stn.y - 40 : stn.y;

              if (isInterchange) {
                const cx = stn.x;
                const isTop = stn.lineCode === "ALP";
                const topY = isTop ? 92 : 228;
                const midY = isTop ? 104 : 240;
                const botY = isTop ? 116 : 252;

                return (
                  <polygon
                    key={`hit-stn-${stnKey}`}
                    points={`${cx},${topY - 6} ${cx + 19},${midY} ${cx},${botY + 6} ${cx - 19},${midY}`}
                    fill="transparent"
                    className="interactive-station"
                    role="button"
                    tabIndex={0}
                    aria-label={`${stn.lineCode} Station ${stn.stationId} Interchange`}
                    onClick={() => handleStationClick(stnKey)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleStationClick(stnKey);
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
                  cy={yAdjusted}
                  r="18"
                  fill="transparent"
                  className="interactive-station"
                  role="button"
                  tabIndex={0}
                  aria-label={`${stn.lineCode} Station ${stn.stationId}`}
                  onClick={() => handleStationClick(stnKey)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleStationClick(stnKey);
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
    </div>
  );
}
