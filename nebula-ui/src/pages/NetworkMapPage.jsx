import React from "react";
import NetworkMap from "../components/network-map/NetworkMap";
import "../styles/network-map.css";

export default function NetworkMapPage({ identity, week, onWeekChange, weeklySummary, onExport }) {
  if (!identity || (!identity.runId && !identity.accepted) || (identity.mode === 'operations' && !identity.baselineId)) {
    return <div className="m-8 rounded-xl border border-slate-800 bg-slate-950 p-10 text-center text-slate-400">Select or solve an explicit schedule before opening its network projection.</div>;
  }
  return <NetworkMap embedded identity={identity} scenario={identity.scenario} week={week} onWeekChange={onWeekChange} weeklySummary={weeklySummary} onExport={onExport} />;
}
