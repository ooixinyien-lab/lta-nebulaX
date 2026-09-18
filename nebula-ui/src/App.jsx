import React, { useState } from 'react';
import { 
  Upload, CheckCircle, Download, 
  Play, Calendar, Database, RefreshCw, Map
} from 'lucide-react';
import ScheduleDashboard from './ScheduleDashboard';
import NetworkMapPage from './pages/NetworkMapPage';

export default function App() {
  // Navigation & State
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window !== 'undefined' && window.location.pathname.includes('network-map')) {
      return 'network_map';
    }
    return 'network_map';
  });
  const [selectedScenario, setSelectedScenario] = useState('A');
  const [isParsing, setIsParsing] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [topologyData, setTopologyData] = useState(null);

  // Uploaded Files State
  const [files, setFiles] = useState({});
  const requiredFiles = [
    '01_LINES.csv', '02_STATIONS.csv', '03_SECTORS.csv', '04_LOCATION_SUPPLY.csv',
    '05_BUFFER_LOCATION.csv', '06_PARAMETERS.csv', '07_PROJECT_DETAILS.csv', '08_ACTIVITY_DETAILS.csv'
  ];

  const handleFileUpload = (e) => {
    const uploadedFiles = Array.from(e.target.files);
    const updated = { ...files };
    uploadedFiles.forEach(file => {
      updated[file.name] = file;
    });
    setFiles(updated);
  };

  // Connects to FastAPI /api/ps1/upload AND /api/ps1/topology endpoints
  const handleIngestCSVs = async () => {
    setIsParsing(true);
    const formData = new FormData();
    Object.values(files).forEach((file) => formData.append('files', file));

    try {
      const [uploadRes, topoRes] = await Promise.all([
        fetch('/api/ps1/upload', { method: 'POST', body: formData }),
        fetch('/api/ps1/topology', { method: 'POST', body: formData }),
      ]);

      const uploadText = await uploadRes.text();
      const topoText = await topoRes.text();

      if (!uploadRes.ok) {
        const err = uploadText ? JSON.parse(uploadText) : {};
        throw new Error(err.detail || 'Upload parsing error');
      }

      if (!topoRes.ok) {
        const err = topoText ? JSON.parse(topoText) : {};
        throw new Error(err.detail || 'Topology extraction error');
      }

      const uploadData = JSON.parse(uploadText);
      const topoData = JSON.parse(topoText);

      setParsedData(uploadData);
      setTopologyData(topoData);
      setActiveTab('matrix');
    } catch (err) {
      alert(`Backend Ingestion Error: ${err.message}`);
    } finally {
      setIsParsing(false);
    }
  };

  const displayData = parsedData || mockFallbackData;

  if (activeTab === 'network_map') {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
        <div className="bg-slate-950/80 border-b border-slate-800/80 px-6 py-1.5 flex items-center justify-between text-xs">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-cyan-400 font-bold">
              <Map size={14} /> Interactive Network Map
            </span>
            <span className="text-slate-600">|</span>
            <button
              onClick={() => setActiveTab('matrix')}
              className="text-slate-300 hover:text-cyan-300 transition flex items-center gap-1.5 font-bold"
            >
              <Calendar size={13} /> Schedule Matrix &amp; Drag Dispatch
            </button>
            <span className="text-slate-600">|</span>
            <button
              onClick={() => setActiveTab('upload')}
              className="text-slate-400 hover:text-slate-200 transition flex items-center gap-1.5"
            >
              <Upload size={13} /> Data Ingestion
            </button>
          </div>
        </div>
        <NetworkMapPage />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      
      {/* 1. HEADER BAR */}
      <header className="border-b border-slate-800 bg-slate-950 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-cyan-500 text-slate-950 font-black px-2.5 py-1 rounded text-lg tracking-wider">
            NEBULA X
          </div>
          <span className="text-slate-400 text-sm font-medium">Rail Ingestion & Maintenance Engine</span>
        </div>

        {/* Ingestion & Export Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => alert("ZIP Export will trigger once solver output is linked!")}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-lg shadow transition"
          >
            <Download size={14} /> Export CSV Bundle
          </button>
        </div>
      </header>

      {/* 2. SUB-HEADER NAVIGATION & METRICS */}
      <div className="border-b border-slate-800 bg-slate-900/50 px-6 py-2 flex items-center justify-between">
        <div className="flex gap-4 text-sm font-medium text-slate-400">
          <button
            onClick={() => setActiveTab('network_map')}
            className={`flex items-center gap-2 py-1 px-3 rounded-md transition ${
              activeTab === 'network_map' ? 'bg-slate-800 text-cyan-400' : 'hover:bg-slate-800/50'
            }`}
          >
            <Map size={16} /> Interactive Network Map
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-2 py-1 px-3 rounded-md transition ${
              activeTab === 'upload' ? 'bg-slate-800 text-cyan-400' : 'hover:bg-slate-800/50'
            }`}
          >
            <Upload size={16} /> Data Import
          </button>
          <button
            onClick={() => setActiveTab('matrix')}
            className={`flex items-center gap-2 py-1 px-3 rounded-md transition ${
              activeTab === 'matrix' ? 'bg-slate-800 text-cyan-400' : 'hover:bg-slate-800/50'
            }`}
          >
            <Calendar size={16} /> Schedule Matrix & Topology
          </button>
          <button
            onClick={() => setActiveTab('raw_data')}
            className={`flex items-center gap-2 py-1 px-3 rounded-md transition ${
              activeTab === 'raw_data' ? 'bg-slate-800 text-cyan-400' : 'hover:bg-slate-800/50'
            }`}
          >
            <Database size={16} /> Parsed Domain Classes
          </button>
        </div>

        {/* Data Class Counts Badge */}
        {displayData && displayData.counts && (
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-slate-400">
              Projects: <strong className="text-cyan-400">{displayData.counts.projects}</strong>
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-400">
              Activities: <strong className="text-purple-400">{displayData.counts.activities}</strong>
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-emerald-400 flex items-center gap-1">
              <CheckCircle size={13} /> Ingest Status: {displayData.status}
            </span>
          </div>
        )}
      </div>

      {/* 3. MAIN CONTENT AREA */}
      <main className="flex-1 overflow-hidden relative">

        {/* TAB 1: FILE UPLOAD */}
        {activeTab === 'upload' && (
          <div className="p-8 max-w-4xl mx-auto space-y-6">
            <div className="border-2 border-dashed border-slate-700 hover:border-cyan-500/50 bg-slate-950/50 rounded-xl p-8 text-center transition">
              <Upload className="mx-auto text-slate-500 mb-4" size={40} />
              <h3 className="font-semibold text-slate-200 text-lg mb-1">Upload Official 8-File PS1 Bundle</h3>
              <p className="text-slate-400 text-xs mb-4">Select all 01_LINES.csv through 08_ACTIVITY_DETAILS.csv</p>
              <label className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-4 py-2 rounded-lg text-xs cursor-pointer inline-block transition">
                Browse CSV Files
                <input type="file" multiple accept=".csv" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>

            {/* Checklist */}
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Schema Ingestion Checklist</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                {requiredFiles.map((req) => (
                  <div key={req} className="flex items-center justify-between bg-slate-900 px-3 py-2 rounded border border-slate-800">
                    <span className="font-mono text-slate-300">{req}</span>
                    {files[req] ? (
                      <CheckCircle size={14} className="text-emerald-400" />
                    ) : (
                      <span className="text-slate-600">Pending</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <button
              onClick={handleIngestCSVs}
              disabled={isParsing || Object.keys(files).length === 0}
              className={`w-full font-black py-3 rounded-xl transition flex items-center justify-center gap-2 ${
                Object.keys(files).length > 0 
                  ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950' 
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }`}
            >
              {isParsing ? (
                <><RefreshCw size={16} className="animate-spin" /> Ingesting & Parsing CSVs via io.py...</>
              ) : (
                <><Play size={16} fill="currentColor" /> Import & Parse CSVs into Data Classes</>
              )}
            </button>
          </div>
        )}

        {/* TAB 2: UNIFIED 30-WEEK SCHEDULE & TOPOLOGY DASHBOARD */}
        {activeTab === 'matrix' && (
          <ScheduleDashboard
            displayData={displayData}
            topologyData={topologyData}
            scenario={selectedScenario}
            onScenarioChange={(sc) => setSelectedScenario(sc)}
          />
        )}

        {/* TAB 3: PARSED DOMAIN CLASSES INSPECTOR */}
        {activeTab === 'raw_data' && (
          <div className="p-8 max-w-6xl mx-auto space-y-6 overflow-y-auto h-full pb-20">
            <div>
              <h3 className="text-lg font-bold text-slate-200 mb-3">Parsed Project Models (ProjectDetailsInput)</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(displayData.sample_projects || []).map((proj, idx) => (
                  <div key={idx} className="bg-slate-950 border border-slate-800 p-4 rounded-xl text-xs space-y-1 font-mono">
                    <div className="text-cyan-400 font-bold text-sm">{proj.contract_number}</div>
                    <div className="text-slate-300">{proj.description}</div>
                    <div className="text-slate-400">Access Type: <span className="text-purple-400">{proj.access_type}</span></div>
                    <div className="text-slate-400">Planned End: {proj.planned_completion_date}</div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-lg font-bold text-slate-200 mb-3">Parsed Activity Models (ActivityDetailsInput)</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(displayData.sample_activities || []).map((act, idx) => (
                  <div key={idx} className="bg-slate-950 border border-slate-800 p-4 rounded-xl text-xs space-y-1 font-mono">
                    <div className="text-emerald-400 font-bold text-sm">{act.activity_id}</div>
                    <div className="text-slate-400">Contract: {act.contract_number}</div>
                    <div className="text-slate-400">Start Location: {act.start_location}</div>
                    <div className="text-slate-400">Planned Start Week: W{act.planned_start_week}</div>
                    <div className="text-slate-400">Accesses Required: {act.total_accesses}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </main>

      {/* FOOTER BAR */}
      <footer className="border-t border-slate-800 bg-slate-950 px-6 py-2 text-[11px] text-slate-500 flex justify-between">
        <span>NEBULA X • Ingestion Pipeline</span>
        <span>Validation Engine: <strong className="text-slate-300">IO_PY_PYDANTIC_PARSED</strong></span>
      </footer>
    </div>
  );
}

// Fallback preview data before initial upload
const mockFallbackData = {
  status: "READY",
  counts: { projects: 2, activities: 2 },
  sample_projects: [
    {
      contract_number: "C006",
      description: "Sleeper Replacement Works",
      access_type: "PC",
      planned_completion_date: "2027-05-30"
    },
    {
      contract_number: "C008",
      description: "Turnout Overhaul Phase 1",
      access_type: "C",
      planned_completion_date: "2027-04-15"
    }
  ],
  sample_activities: [
    {
      activity_id: "A036",
      contract_number: "C006",
      start_location: "SEC:ALP:S01_S02",
      planned_start_week: 22,
      total_accesses: 7,
      activity_priority: 1,
      predecessor_activity_id: null
    },
    {
      activity_id: "A040",
      contract_number: "C008",
      start_location: "SEC:ALP:S02_S03",
      planned_start_week: 12,
      total_accesses: 4,
      activity_priority: 2,
      predecessor_activity_id: "A036"
    }
  ]
};