import React, { useState } from 'react';
import { AlertTriangle, CheckCircle, Database, Play, RefreshCw, Upload, X } from 'lucide-react';
import ScheduleDashboard from './ScheduleDashboard';
import NetworkMapPage from './pages/NetworkMapPage';
import AppHeader from './components/AppHeader';
import { PlanningProvider, usePlanning } from './planning/PlanningContext';

const REQUIRED_FILES = ['01_LINES.csv','02_STATIONS.csv','03_SECTORS.csv','04_LOCATION_SUPPLY.csv','05_BUFFER_LOCATION.csv','06_PARAMETERS.csv','07_PROJECT_DETAILS.csv','08_ACTIVITY_DETAILS.csv'];

export default function App() { return <PlanningProvider><PlanningApp /></PlanningProvider>; }

function PlanningApp() {
  const planning = usePlanning();
  const [activeTab, setActiveTab] = useState('dashboard');
  const [dashboardWeek, setDashboardWeek] = useState(1);
  const [files, setFiles] = useState({});
  const [message, setMessage] = useState(null);
  const [showAddJob, setShowAddJob] = useState(false);
  const handleFiles = (event) => { const next = {...files}; Array.from(event.target.files).forEach((file) => { next[file.name] = file; }); setFiles(next); };
  const upload = async () => { try { await planning.upload(REQUIRED_FILES.map((name) => files[name])); setMessage('Official instance populated and operational baseline created.'); setActiveTab('dashboard'); } catch (error) { setMessage(error.message); } };
  const solve = async () => { setMessage(null); try { await planning.solve(); } catch (error) { setMessage(error.message); } };
  const exportCsv = () => {
    const schedule = planning.schedule;
    if (!schedule) return;
    const sections = [
      ['SCHEDULE_ACCESS.csv', ['activity_id,access_seq,week,eclo,access_night', ...(schedule.accesses || []).map((r) => [r.activity_id,r.access_seq,r.week,r.eclo,r.access_night].join(','))]],
      ['SCHEDULE_OCCUPANCY.csv', ['activity_id,week,location_id,co_share_group', ...(schedule.occupancies || []).map((r) => [r.activity_id,r.week,r.location_id,r.co_share_group].join(','))]],
      ['RESULTS.csv', ['scenario,contract_number,simulated_completion_date,overrun_days', ...(schedule.results || schedule.contract_results || []).map((r) => [r.scenario,r.contract_number,r.simulated_completion_date,r.overrun_days].join(','))]],
    ];
    sections.forEach(([name, lines]) => { const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' })); link.download = name; link.click(); URL.revokeObjectURL(link.href); });
  };
  const weeklySummary = Array.from({ length: planning.schedule?.horizon?.weeks || 30 }, (_, index) => {
    const week = index + 1;
    const accesses = planning.schedule?.accesses || [];
    const maintenance = planning.schedule?.maintenance || [];
    const activeCount = accesses.filter((row) => row.week === week).length;
    const maintenanceCount = maintenance.filter((row) => row.week === week).length;
    return { week, activeCount, maintenanceCount, hasActivity: activeCount > 0 || maintenanceCount > 0 };
  });
  const clear = async () => { if (!window.confirm('Remove all uploaded scheduling data, solver results, operational baselines, additions, and maintenance schedules? The database schema will be preserved.')) return; await planning.clearDatabase(); setFiles({}); setMessage('Planning database cleared.'); };
  return <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
    <AppHeader activeTab={activeTab} onNavigate={setActiveTab} mode={planning.mode} scenario={planning.scenario} onModeChange={planning.selectMode} onScenarioChange={planning.selectScenario} onAddJob={() => setShowAddJob(true)} onSolve={solve} onAccept={() => planning.accept().then(() => setMessage('Candidate accepted as a new baseline revision.')).catch((error) => setMessage(error.message))} solving={planning.solving} solveDisabled={planning.mode === 'requirements' ? ['A', 'B', 'C'].every((scenario) => planning.requirements[scenario]?.runId) : Boolean(planning.identity?.runId)} hasCandidate={Boolean(planning.mode === 'operations' && planning.identity?.runId)} />
    {planning.mode === 'operations' && planning.schedule && <div className={`border-b px-5 py-2 text-xs flex items-center justify-between ${planning.conflicts.length ? 'border-rose-800 bg-rose-950/70 text-rose-200' : 'border-emerald-900 bg-emerald-950/40 text-emerald-300'}`}><span className="flex items-center gap-2">{planning.conflicts.length ? <AlertTriangle size={14}/> : <CheckCircle size={14}/>} {planning.conflicts.length ? `${planning.conflicts.length} scheduling conflicts require resolution` : 'Operational schedule is valid for the active identity'}{planning.schedule?.diff && !planning.conflicts.length ? ` · Candidate diff: ${planning.schedule.diff.disruption.changed_existing_jobs} jobs changed · ${planning.schedule.diff.disruption.total_absolute_service_date_displacement} days displaced · cost ${planning.schedule.diff.scenarioCost.objective_points}` : ''}</span>{planning.conflicts.length > 0 && <button type="button" onClick={() => setActiveTab('dashboard')} className="font-bold underline">View conflicts</button>}</div>}
    {(message || planning.error) && <div role="status" className="border-b border-amber-800 bg-amber-950/70 px-5 py-2 text-xs text-amber-200">{message || planning.error}</div>}
    <main className="flex-1 min-h-0 overflow-auto relative">
      {activeTab === 'dashboard' && (planning.schedule ? <>
        <NetworkMapPage identity={planning.identity} week={dashboardWeek} onWeekChange={setDashboardWeek} weeklySummary={weeklySummary} onExport={exportCsv}/>
        <ScheduleDashboard displayData={planning.schedule} mode={planning.mode} scenario={planning.scenario} week={dashboardWeek} onWeekChange={setDashboardWeek} onScenarioChange={planning.selectScenario} authoritativeConflicts={planning.conflicts} highlightedJobId={planning.highlightedJobId} onExport={exportCsv}/>
      </> : <EmptySchedule mode={planning.mode} loading={planning.loading} hasDatabase={Boolean(planning.catalog && Object.values(planning.catalog).some((value) => Array.isArray(value) && value.length > 0))} onUpload={() => setActiveTab('upload')} onSolve={solve} solving={planning.solving}/>)}
      {activeTab === 'upload' && <UploadPanel files={files} onFiles={handleFiles} onUpload={upload} loading={planning.loading} onClear={clear}/>}
    </main>
    {showAddJob && <AddJobModal identity={planning.identity} schedule={planning.schedule} onClose={() => setShowAddJob(false)} onSubmit={(addition) => planning.addJob(addition).then(() => { setShowAddJob(false); setMessage(`Added ${addition.job.job_id}; Auto Solve has not been run.`); }).catch((error) => setMessage(error.message))}/>}
  </div>;
}

function EmptySchedule({ mode, loading, hasDatabase, onUpload, onSolve, solving }) { return <div className="m-8 rounded-xl border border-slate-800 bg-slate-950 p-10 text-center text-slate-400">{loading ? <RefreshCw className="mx-auto mb-3 animate-spin"/> : <Database className="mx-auto mb-3"/>}<p>{hasDatabase ? 'This schedule is not solved yet. Solve the selected scenario to generate the dashboard.' : mode === 'requirements' ? 'Upload an official bundle and solve the selected scenario.' : 'Upload an official bundle to create an operational baseline.'}</p>{hasDatabase ? <button type="button" onClick={onSolve} disabled={solving || loading} className="mt-4 rounded bg-cyan-500 px-4 py-2 font-bold text-slate-950 disabled:opacity-50">{solving ? 'Solving…' : 'Solve Schedule'}</button> : <button type="button" onClick={onUpload} className="mt-4 rounded bg-cyan-500 px-4 py-2 font-bold text-slate-950">Open Data Ingestion</button>}</div>; }

function UploadPanel({ files, onFiles, onUpload, loading, onClear }) {
  const complete = REQUIRED_FILES.every((name) => files[name]);
  return <div className="p-8 max-w-4xl mx-auto space-y-6"><div className="border-2 border-dashed border-slate-700 bg-slate-950/50 rounded-xl p-8 text-center"><Upload className="mx-auto text-slate-500 mb-4" size={40}/><h3 className="font-semibold text-lg">Upload Official 8-File PS1 Bundle</h3><label className="mt-4 inline-block cursor-pointer rounded-lg bg-cyan-500 px-4 py-2 text-xs font-bold text-slate-950">Browse CSV Files<input type="file" multiple accept=".csv" onChange={onFiles} className="hidden"/></label></div><div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs">{REQUIRED_FILES.map((name) => <div key={name} className="flex justify-between rounded bg-slate-900 p-2"><span className="font-mono">{name}</span>{files[name] ? <CheckCircle size={14} className="text-emerald-400"/> : <span className="text-slate-600">Pending</span>}</div>)}</div><button type="button" onClick={onUpload} disabled={!complete || loading} className="w-full rounded-xl bg-cyan-500 py-3 font-black text-slate-950 disabled:bg-slate-800 disabled:text-slate-500">{loading ? <RefreshCw className="inline animate-spin" size={16}/> : <Play className="inline" size={16}/>} Populate Database</button><section className="rounded-xl border border-rose-900 bg-rose-950/20 p-5" aria-label="Danger zone"><h4 className="font-bold text-rose-300">Danger zone</h4><p className="my-2 text-xs text-rose-200/80">Clear uploaded scheduling data, solver results, operational schedules, additions, and associated maintenance data while preserving the schema.</p><button type="button" onClick={onClear} className="rounded border border-rose-600 px-3 py-2 text-xs font-bold text-rose-300 hover:bg-rose-950">Clear Database</button></section></div>;
}

function AddJobModal({ identity, schedule, onClose, onSubmit }) {
  const firstLocation = schedule?.locations?.[0]?.location_id || '';
  const [form, setForm] = useState({ job_id:'', contract_number:'', activity_type:'Renewal', nature_of_activity:'Non-live (Others)', access_type:'C', start_location_id:firstLocation, end_location_id:firstLocation, total_accesses:1, planned_start_date:'2027-01-04', planned_completion_date:'2027-02-01', hard_completion_date:'2027-02-01', contract_priority:3, activity_priority:3, number_of_workfronts:1, number_of_maximum_access_per_week:3, source:'addition' });
  const update = (event) => setForm((current) => ({...current, [event.target.name]: event.target.type === 'number' ? Number(event.target.value) : event.target.value}));
  const submit = (event) => { event.preventDefault(); const { source, ...job } = form; onSubmit({ requested_source:source, job:{...job, source, release_date:job.planned_start_date} }); };
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-label="Add Job Request"><form onSubmit={submit} className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-xl border border-slate-700 bg-slate-950 p-6"><div className="mb-4 flex justify-between"><div><h2 className="font-bold text-cyan-300">Add Job Request</h2><p className="text-xs text-slate-500">Baseline {identity?.baselineId} revision {identity?.baselineRevision}</p></div><button type="button" onClick={onClose} aria-label="Close"><X/></button></div><div className="grid grid-cols-2 gap-3">{[['job_id','Job ID'],['contract_number','Contract ID'],['planned_start_date','Release date'],['planned_completion_date','Planned completion'],['hard_completion_date','Hard completion'],['total_accesses','Required accesses'],['number_of_maximum_access_per_week','Max accesses/week'],['number_of_workfronts','Workfronts']].map(([name,label]) => <label key={name} className="text-xs text-slate-400">{label}<input required name={name} type={name.includes('date') ? 'date' : name.includes('access') || name === 'number_of_workfronts' ? 'number' : 'text'} value={form[name]} onChange={update} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2 text-slate-100"/></label>)}<Select label="Access type" name="access_type" value={form.access_type} onChange={update} options={['PM','PC','C']}/><Select label="Nature" name="nature_of_activity" value={form.nature_of_activity} onChange={update} options={['Live','Non-live (Consist)','Non-live (Others)']}/><Select label="Source" name="source" value={form.source} onChange={update} options={['addition','emergency']}/>{['start_location_id','end_location_id'].map((name) => <label key={name} className="text-xs text-slate-400">{name === 'start_location_id' ? 'Start location' : 'End location'}<select name={name} value={form[name]} onChange={update} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2">{schedule?.locations?.map((location) => <option key={location.location_id}>{location.location_id}</option>)}</select></label>)}</div><button type="submit" className="mt-5 w-full rounded bg-cyan-500 py-2 font-bold text-slate-950">Add without solving</button></form></div>;
}
function Select({label,name,value,onChange,options}) { return <label className="text-xs text-slate-400">{label}<select name={name} value={value} onChange={onChange} className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2">{options.map((option) => <option key={option}>{option}</option>)}</select></label>; }
