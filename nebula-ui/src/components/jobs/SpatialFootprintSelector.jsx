import React, { useMemo } from 'react';
import {
  MapPin,
  ArrowRightLeft,
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Info,
  Layers,
  Train,
} from 'lucide-react';
import {
  DEFAULT_LINES,
  LINE_STATIONS,
  TRACK_BOUNDS,
  ACCESS_MODES,
  calculateSafetyBuffer,
} from './jobFormConstants';

export default function SpatialFootprintSelector({
  formData,
  onChange,
  topologyData = null,
  onSelectOnMap = null,
  onPickOnMap = null,
  disabled = false,
}) {
  // Merge or determine lines
  const lines = useMemo(() => {
    if (topologyData?.lines && topologyData.lines.length > 0) {
      return topologyData.lines.map((l) => ({
        code: l.line_code || l.code,
        name: l.line_name || l.name || `${l.line_code || l.code} Line`,
        color: l.color || '#06b6d4',
        badgeClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
      }));
    }
    return DEFAULT_LINES;
  }, [topologyData]);

  // Available stations for current line
  const availableStations = useMemo(() => {
    const lineCode = formData.line_code || 'NSL';
    if (topologyData?.stations && topologyData.stations.length > 0) {
      const lineStations = topologyData.stations.filter(
        (s) => s.line_code === lineCode || s.lineCode === lineCode
      );
      if (lineStations.length > 0) {
        return lineStations.map((s) => ({
          id: s.station_id || s.id,
          name: s.station_name || s.name || s.station_id || s.id,
          code: s.code || s.station_id || s.id,
        }));
      }
    }
    return LINE_STATIONS[lineCode] || LINE_STATIONS.NSL;
  }, [formData.line_code, topologyData]);

  // Derived safety buffer HUD data
  const safetyBufferInfo = useMemo(() => {
    return calculateSafetyBuffer(
      formData.nature_of_works,
      formData.track_bound,
      formData.line_code,
      formData.start_location_id,
      formData.end_location_id
    );
  }, [
    formData.nature_of_works,
    formData.track_bound,
    formData.line_code,
    formData.start_location_id,
    formData.end_location_id,
  ]);

  // Calculate approximate stretch distance in stations
  const stretchSpan = useMemo(() => {
    if (!formData.start_location_id || !formData.end_location_id) return null;
    const startIndex = availableStations.findIndex((s) => s.id === formData.start_location_id);
    const endIndex = availableStations.findIndex((s) => s.id === formData.end_location_id);
    if (startIndex === -1 || endIndex === -1) return null;
    const count = Math.abs(endIndex - startIndex) + 1;
    const sectors = Math.max(1, count - 1);
    return { stationCount: count, sectorCount: sectors };
  }, [availableStations, formData.start_location_id, formData.end_location_id]);

  const handleLineChange = (e) => {
    const newLine = e.target.value;
    const stations = LINE_STATIONS[newLine] || availableStations;
    onChange({
      line_code: newLine,
      start_location_id: stations[0]?.id || '',
      end_location_id: stations[Math.min(2, stations.length - 1)]?.id || stations[0]?.id || '',
    });
  };

  const handleSwapStations = () => {
    onChange({
      start_location_id: formData.end_location_id,
      end_location_id: formData.start_location_id,
    });
  };

  const handleTriggerMapPick = (mode) => {
    if (onPickOnMap) {
      onPickOnMap(mode);
    } else if (onSelectOnMap) {
      onSelectOnMap(mode === 'start' ? 'start_location_id' : 'end_location_id');
    }
  };

  const selectedLineObj = lines.find((l) => l.code === formData.line_code) || lines[0];

  return (
    <div className="space-y-5">
      {/* 1. LINE SELECTION & MAP QUICK-ACTION */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
        <div className="md:col-span-8 space-y-1.5">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Railway Line Corridor <span className="text-rose-400">*</span>
          </label>
          <div className="relative">
            <select
              value={formData.line_code}
              onChange={handleLineChange}
              disabled={disabled}
              className="w-full bg-slate-900 border border-slate-700 hover:border-slate-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-sm transition appearance-none cursor-pointer"
            >
              {lines.map((line) => (
                <option key={line.code} value={line.code} className="bg-slate-900 text-slate-100">
                  {line.code} — {line.name}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 text-xs">
              ▼
            </div>
          </div>
        </div>

        <div className="md:col-span-4 flex items-center justify-end">
          <div
            className={`w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-mono font-bold ${
              selectedLineObj?.badgeClass || 'bg-slate-800 text-slate-300 border-slate-700'
            }`}
          >
            <Train size={14} />
            <span>{selectedLineObj?.code} Active Corridor</span>
          </div>
        </div>
      </div>

      {/* 2. DUAL STATION COMBOBOXES & SWAP BUTTON */}
      <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <MapPin size={14} className="text-cyan-400" />
            Possession Geographical Extents
          </span>
          {stretchSpan && (
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/60 text-cyan-300">
              Span: {stretchSpan.stationCount} Stations ({stretchSpan.sectorCount} Sectors)
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center">
          {/* Start Station */}
          <div className="md:col-span-5 space-y-1">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Start Station</span>
              <button
                type="button"
                onClick={() => handleTriggerMapPick('start')}
                disabled={disabled}
                className="text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1 font-medium"
                title="Pick station by clicking directly on SVG network map"
              >
                <MapPin size={11} /> Pick on Map
              </button>
            </div>
            <select
              value={formData.start_location_id}
              onChange={(e) => onChange({ start_location_id: e.target.value })}
              disabled={disabled}
              className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3 py-2 text-xs font-mono transition"
            >
              {availableStations.map((stn) => (
                <option key={stn.id} value={stn.id}>
                  [{stn.id}] {stn.name}
                </option>
              ))}
            </select>
          </div>

          {/* Invert / Swap Button */}
          <div className="md:col-span-1 flex justify-center pt-3 md:pt-4">
            <button
              type="button"
              onClick={handleSwapStations}
              disabled={disabled}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 border border-slate-700 transition shadow-sm"
              title="Reverse Start & End Stations"
            >
              <ArrowRightLeft size={14} />
            </button>
          </div>

          {/* End Station */}
          <div className="md:col-span-5 space-y-1">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>End Station</span>
              <button
                type="button"
                onClick={() => handleTriggerMapPick('end')}
                disabled={disabled}
                className="text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1 font-medium"
                title="Pick station by clicking directly on SVG network map"
              >
                <MapPin size={11} /> Pick on Map
              </button>
            </div>
            <select
              value={formData.end_location_id}
              onChange={(e) => onChange({ end_location_id: e.target.value })}
              disabled={disabled}
              className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3 py-2 text-xs font-mono transition"
            >
              {availableStations.map((stn) => (
                <option key={stn.id} value={stn.id}>
                  [{stn.id}] {stn.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 3. TRACK BOUND & ACCESS MODE */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Track Bound 3-way toggle */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Track Directional Bound
          </label>
          <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-950 border border-slate-800 rounded-xl">
            {TRACK_BOUNDS.map((bound) => {
              const isActive = formData.track_bound === bound.id;
              return (
                <button
                  key={bound.id}
                  type="button"
                  onClick={() => onChange({ track_bound: bound.id })}
                  disabled={disabled}
                  className={`py-2 px-2 rounded-lg text-xs font-medium transition flex flex-col items-center justify-center gap-0.5 ${
                    isActive
                      ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/20'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <span>{bound.label}</span>
                  <span
                    className={`text-[10px] font-mono ${
                      isActive ? 'text-slate-900 font-semibold' : 'text-slate-500'
                    }`}
                  >
                    {bound.direction}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Access Mode Switch */}
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Access Exclusivity Mode
          </label>
          <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-950 border border-slate-800 rounded-xl">
            {ACCESS_MODES.map((mode) => {
              const isActive = formData.access_mode === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => onChange({ access_mode: mode.id })}
                  disabled={disabled}
                  className={`py-2 px-2.5 rounded-lg text-xs transition flex flex-col items-center justify-center text-center ${
                    isActive
                      ? 'bg-purple-600 text-white font-bold shadow-md shadow-purple-600/20'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`}
                >
                  <span>{mode.label}</span>
                  <span
                    className={`text-[10px] leading-tight mt-0.5 ${
                      isActive ? 'text-purple-200 font-normal' : 'text-slate-500'
                    }`}
                  >
                    {mode.id === 'EXCLUSIVE' ? 'Sole occupant' : 'Allows sharing'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 4. DYNAMIC SAFETY BUFFER HUD (VISUAL ALERT BOX) */}
      <div
        className={`rounded-xl border p-4 transition duration-200 ${
          safetyBufferInfo.warningLevel === 'caution'
            ? 'bg-amber-950/30 border-amber-500/40 text-amber-200'
            : safetyBufferInfo.warningLevel === 'info'
            ? 'bg-cyan-950/30 border-cyan-500/40 text-cyan-200'
            : 'bg-slate-900/50 border-slate-800 text-slate-300'
        }`}
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-slate-950/80 border border-current/20 shrink-0">
            {safetyBufferInfo.warningLevel === 'caution' ? (
              <ShieldAlert className="text-amber-400" size={20} />
            ) : (
              <ShieldCheck className="text-cyan-400" size={20} />
            )}
          </div>

          <div className="flex-1 space-y-1.5">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="font-bold text-xs tracking-wide flex items-center gap-1.5">
                {safetyBufferInfo.badgeText}
              </span>
              <div className="flex items-center gap-1.5 font-mono text-[11px]">
                <span className="px-2 py-0.5 rounded bg-slate-950/80 border border-slate-700">
                  Buffer: +{safetyBufferInfo.bufferSectors} Sectors
                </span>
                {safetyBufferInfo.mirrorOppositeBound && (
                  <span className="px-2 py-0.5 rounded bg-orange-950/80 border border-orange-700 text-orange-300 font-semibold">
                    Dual Lockout Active
                  </span>
                )}
              </div>
            </div>

            <p className="text-xs leading-relaxed text-slate-300 font-normal">
              {safetyBufferInfo.lockoutDescription}
            </p>

            {formData.nature_of_works === 'HEAVY' && (
              <div className="mt-2 text-[11px] font-mono bg-amber-950/50 border border-amber-800/40 p-2 rounded text-amber-300 flex items-center gap-2">
                <AlertTriangle size={13} className="shrink-0 text-amber-400" />
                <span>
                  Mandatory safety rule: On-track heavy maintenance plant creates an upstream/downstream safety halo and suppresses train passes on opposite bound.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
