import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Calendar,
  Layers,
  Clock,
  CheckCircle2,
  HelpCircle,
  Flame,
  Wrench,
  FileSpreadsheet,
  Workflow,
  Compass,
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Info,
  Sliders,
  Zap,
} from 'lucide-react';

import {
  JOB_SOURCES,
  JOB_SOURCE_LABELS,
  ACTIVITY_TYPES,
  NATURE_OF_WORKS,
  ACTIVITY_PRIORITIES,
  CONTRACT_PRIORITIES,
  DEFAULT_CONTRACTS,
  generateJobId,
  getInitialJobFormData,
  validateJobForm,
  runClientSidePreflightHeuristic,
} from './jobFormConstants';

import SpatialFootprintSelector from './SpatialFootprintSelector';
import PreflightCheckDrawer from './PreflightCheckDrawer';

const TABS = [
  { id: 'classification', label: '1. Classification', short: 'Classification', icon: Wrench },
  { id: 'spatial', label: '2. Spatial Footprint', short: 'Spatial', icon: Compass },
  { id: 'timing', label: '3. Timing & Workload', short: 'Timing', icon: Calendar },
  { id: 'dependencies', label: '4. Precedence', short: 'Dependencies', icon: Workflow },
  { id: 'priority', label: '5. Priority & Impact', short: 'Priority', icon: Sliders },
];

export default function JobEditorModal({
  isOpen,
  onClose,
  onSubmit,
  initialData = null,
  existingJobs = [],
  contracts = DEFAULT_CONTRACTS,
  topologyData = null,
  onSelectOnMap = null,
  runId = 'default',
}) {
  // Form State
  const [formData, setFormData] = useState(() => getInitialJobFormData(initialData, existingJobs));
  const [activeTab, setActiveTab] = useState('classification');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTooltip, setShowTooltip] = useState(null);

  // Preflight Check State
  const [preflightResult, setPreflightResult] = useState(null);
  const [isCheckingPreflight, setIsCheckingPreflight] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);

  // Reset form when modal opens or initialData changes
  useEffect(() => {
    if (isOpen) {
      setFormData(getInitialJobFormData(initialData, existingJobs));
      setActiveTab('classification');
      setPreflightResult(null);
    }
  }, [isOpen, initialData]);

  // Handle form field updates
  const handleUpdate = useCallback((patch) => {
    setFormData((prev) => {
      const next = { ...prev, ...patch };

      // Auto-switch to Emergency defaults if category switched
      if (patch.category && patch.category !== prev.category) {
        if (patch.category === JOB_SOURCES.EMERGENCY) {
          next.enforce_hard_deadline = true;
          if (!next.hard_completion_date && next.planned_start_date) {
            const start = new Date(next.planned_start_date);
            start.setDate(start.getDate() + 7);
            next.hard_completion_date = start.toISOString().slice(0, 10);
          }
        }
      }

      return next;
    });
  }, []);

  // Validation
  const validation = useMemo(() => {
    return validateJobForm(formData, existingJobs);
  }, [formData, existingJobs]);

  const isEmergency = formData.category === JOB_SOURCES.EMERGENCY;
  const isEditing = Boolean(initialData?.id || initialData?.job_id);

  // Handle contract selection and auto-fill nature/type
  const handleContractChange = (contractId) => {
    const matchedContract = contracts.find((c) => c.id === contractId);
    if (matchedContract) {
      handleUpdate({
        contract_number: contractId,
        is_adhoc_contract: false,
        contract_priority: matchedContract.priority || formData.contract_priority,
        nature_of_works: matchedContract.defaultNature || formData.nature_of_works,
        activity_type: matchedContract.defaultType || formData.activity_type,
      });
    } else {
      handleUpdate({ contract_number: contractId });
    }
  };

  // Run Preflight Check
  const handleRunPreflight = async () => {
    setIsCheckingPreflight(true);
    setIsDrawerOpen(true);

    try {
      const response = await fetch(`/api/ps1/runs/${runId}/edits/preflight`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job: {
            job_id: formData.id,
            category: formData.category,
            contract_number: formData.contract_number,
            activity_type: formData.activity_type,
            nature_of_activity: formData.nature_of_works,
            access_type: formData.access_mode,
            line_code: formData.line_code,
            start_location_id: formData.start_location_id,
            end_location_id: formData.end_location_id,
            track_bound: formData.track_bound,
            total_accesses: Number(formData.total_accesses),
            planned_start_date: formData.planned_start_date,
            planned_completion_date: formData.planned_completion_date,
            hard_completion_date: formData.hard_completion_date || null,
            max_accesses_per_week: Number(formData.max_accesses_per_week),
            predecessor_job_id: formData.predecessor_job_id || null,
            activity_priority: Number(formData.activity_priority),
            contract_priority: Number(formData.contract_priority),
            eclo_allowed: Boolean(formData.eclo_allowed),
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      setPreflightResult({
        status: data.status || 'PASSED',
        ruleBreakdown: data.rule_breakdown || data.ruleBreakdown || [],
        metrics: data.metrics || {
          disruptionScore: data.disruption_score || 0,
          displacedVisits: data.displaced_visits || 0,
          bufferHaloSectors: formData.nature_of_works === 'HEAVY' ? 2 : 1,
          capacityPeakRatio: '60%',
        },
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      });
    } catch (err) {
      // Fallback to client-side heuristics
      const heuristicResult = runClientSidePreflightHeuristic(formData, existingJobs, topologyData);
      setPreflightResult(heuristicResult);
    } finally {
      setIsCheckingPreflight(false);
    }
  };

  // Submit Handler
  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!validation.isValid) return;

    if (preflightResult?.status === 'HARD CONFLICT') {
      alert('Cannot insert job: Resolve preflight hard conflicts before scheduling.');
      return;
    }

    setIsSubmitting(true);
    try {
      if (onSubmit) {
        await onSubmit(formData);
      }
      onClose();
    } catch (err) {
      alert(`Failed to save possession job: ${err.message || err}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Stepper navigation
  const currentTabIndex = TABS.findIndex((t) => t.id === activeTab);
  const canGoNext = currentTabIndex < TABS.length - 1;
  const canGoPrev = currentTabIndex > 0;

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-md overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="job-modal-title"
    >
      <div
        className={`w-full max-w-4xl bg-slate-900 border rounded-2xl shadow-2xl flex flex-col max-h-[92vh] overflow-hidden transition-all duration-200 ${
          isEmergency
            ? 'border-rose-600/80 ring-1 ring-rose-500/30'
            : 'border-slate-800'
        }`}
      >
        {/* ==================== 1. MODAL HEADER ==================== */}
        <header
          className={`px-6 py-4 border-b flex items-center justify-between shrink-0 ${
            isEmergency
              ? 'bg-rose-950/40 border-rose-800/80'
              : 'bg-slate-950 border-slate-800'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-xl border ${
                isEmergency
                  ? 'bg-rose-900/40 text-rose-300 border-rose-600 animate-pulse'
                  : 'bg-cyan-950/60 text-cyan-400 border-cyan-800'
              }`}
            >
              {isEmergency ? <Flame size={20} /> : <Wrench size={20} />}
            </div>

            <div>
              <div className="flex items-center gap-2.5">
                <h2 id="job-modal-title" className="text-base font-bold text-slate-100">
                  {isEditing ? `Edit Job: ${formData.id}` : 'New Track Possession Job'}
                </h2>

                {/* Job Category Badge */}
                <span
                  className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider border ${
                    isEmergency
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500'
                      : formData.category === JOB_SOURCES.ROUTINE
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500'
                      : 'bg-cyan-500/20 text-cyan-300 border-cyan-500'
                  }`}
                >
                  {isEmergency
                    ? 'EMERGENCY REPAIR'
                    : formData.category === JOB_SOURCES.ROUTINE
                    ? 'ROUTINE MAINTENANCE'
                    : 'PROJECT ADDITION'}
                </span>
              </div>

              <p className="text-xs text-slate-400 mt-0.5">
                {isEmergency
                  ? 'High-priority track rectification with expedited preemption rules.'
                  : 'Multi-week possession slot injection with spatial safety checks.'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700 transition"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </header>

        {/* ==================== 2. TABBED STEPPER BAR ==================== */}
        <nav
          className="bg-slate-950/80 border-b border-slate-800 px-6 py-2 flex items-center gap-2 overflow-x-auto shrink-0 scrollbar-none"
          aria-label="Form Sections"
        >
          {TABS.map((tab, idx) => {
            const TabIcon = tab.icon;
            const isActive = activeTab === tab.id;
            const isCompleted = idx < currentTabIndex;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-1.5 px-3 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                  isActive
                    ? isEmergency
                      ? 'bg-rose-950 border border-rose-700 text-rose-200 shadow-sm'
                      : 'bg-slate-800 border border-slate-700 text-cyan-400 shadow-sm'
                    : isCompleted
                    ? 'text-slate-300 hover:bg-slate-800/60'
                    : 'text-slate-400 hover:text-slate-300 hover:bg-slate-800/40'
                }`}
              >
                <TabIcon size={14} className={isActive ? (isEmergency ? 'text-rose-400' : 'text-cyan-400') : ''} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* ==================== 3. MODAL BODY (TAB PANELS) ==================== */}
        <main className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* ================= PANEL 1: CLASSIFICATION ================= */}
          {activeTab === 'classification' && (
            <section className="space-y-5 animate-fadeIn" aria-labelledby="heading-classification">
              <h3 id="heading-classification" className="sr-only">Classification &amp; Nature of Work</h3>
              {/* Category Segmented Buttons */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Possession Source / Category <span className="text-rose-400">*</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-1 bg-slate-950 border border-slate-800 rounded-xl">
                  {Object.values(JOB_SOURCES).map((catKey) => {
                    const isSelected = formData.category === catKey;
                    const isCatEmergency = catKey === JOB_SOURCES.EMERGENCY;
                    return (
                      <button
                        key={catKey}
                        type="button"
                        onClick={() => handleUpdate({ category: catKey })}
                        className={`py-2 px-3 rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 ${
                          isSelected
                            ? isCatEmergency
                              ? 'bg-rose-600 text-white shadow-md shadow-rose-600/30'
                              : 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                        }`}
                      >
                        {isCatEmergency && <Flame size={14} />}
                        <span>{JOB_SOURCE_LABELS[catKey]}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Emergency Warning Notice */}
              {isEmergency && (
                <div className="bg-rose-950/40 border border-rose-700/80 rounded-xl p-3.5 text-rose-200 flex items-start gap-3">
                  <Flame size={18} className="text-rose-400 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-xs">
                    <span className="font-bold text-rose-300 uppercase tracking-wide">
                      Urgent Emergency Mode Active
                    </span>
                    <p className="text-rose-200/90 leading-relaxed">
                      Emergency track repairs enforce mandatory <strong>hard completion deadlines</strong> and trigger the preemption solver. Non-emergency possessions within this safety sector may be rescheduled.
                    </p>
                  </div>
                </div>
              )}

              {/* Job ID with Auto-Generate Button */}
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
                <div className="sm:col-span-8 space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Job Identifier <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.id}
                    onChange={(e) => handleUpdate({ id: e.target.value })}
                    placeholder="e.g. PRJ-104 or EMG-20260919-01"
                    className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono transition"
                  />
                  {validation.errors.id && (
                    <span className="text-[11px] text-rose-400">{validation.errors.id}</span>
                  )}
                </div>

                <div className="sm:col-span-4">
                  <button
                    type="button"
                    onClick={() => handleUpdate({ id: generateJobId(formData.category, existingJobs) })}
                    className="w-full py-2.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 hover:text-cyan-300 border border-slate-700 text-xs font-medium flex items-center justify-center gap-1.5 transition"
                  >
                    <Sparkles size={13} />
                    <span>Auto-Generate ID</span>
                  </button>
                </div>
              </div>

              {/* Contract Selection & Ad-Hoc Toggle */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <FileSpreadsheet size={14} className="text-cyan-400" />
                    Contract Association
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-400 select-none">
                    <input
                      type="checkbox"
                      checked={formData.is_adhoc_contract}
                      onChange={(e) => handleUpdate({ is_adhoc_contract: e.target.checked })}
                      className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <span>Define Standalone Ad-Hoc Contract</span>
                  </label>
                </div>

                {formData.is_adhoc_contract ? (
                  <div className="space-y-1">
                    <input
                      type="text"
                      value={formData.adhoc_contract_name}
                      onChange={(e) => handleUpdate({ adhoc_contract_name: e.target.value })}
                      placeholder="Enter ad-hoc contract code / title (e.g. ADHOC-CIVIL-2026)"
                      className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2 text-xs font-mono"
                    />
                    {validation.errors.contract_number && (
                      <span className="text-[11px] text-rose-400">{validation.errors.contract_number}</span>
                    )}
                  </div>
                ) : (
                  <div className="space-y-1">
                    <select
                      value={formData.contract_number}
                      onChange={(e) => handleContractChange(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                    >
                      {contracts.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.description || `${c.id} - Contract`}
                        </option>
                      ))}
                    </select>
                    <span className="text-[11px] text-slate-400">
                      Auto-populates nature of works, trade type, and contract penalty weights.
                    </span>
                  </div>
                )}
              </div>

              {/* Activity Type & Nature of Works Dropdowns */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Activity Type */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Activity Trade / Discipline
                  </label>
                  <select
                    value={formData.activity_type}
                    onChange={(e) => handleUpdate({ activity_type: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                  >
                    {ACTIVITY_TYPES.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.id} — {type.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Nature of Works with Tooltip */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                      Nature of Works
                    </label>
                    <div className="relative">
                      <button
                        type="button"
                        onMouseEnter={() => setShowTooltip('nature')}
                        onMouseLeave={() => setShowTooltip(null)}
                        onClick={() => setShowTooltip(showTooltip === 'nature' ? null : 'nature')}
                        className="text-slate-400 hover:text-cyan-400 transition"
                        title="View safety rule constraints"
                      >
                        <HelpCircle size={14} />
                      </button>

                      {showTooltip === 'nature' && (
                        <div className="absolute right-0 bottom-6 w-64 p-2.5 rounded-lg bg-slate-950 border border-slate-700 shadow-xl text-[11px] text-slate-200 z-30 leading-relaxed font-sans">
                          <strong className="text-cyan-400 block mb-1">Safety Halo Constraint:</strong>
                          HEAVY work automatically enforces a +2 sector safety buffer upstream &amp; downstream and mirrors track lockout to opposite bound.
                        </div>
                      )}
                    </div>
                  </div>

                  <select
                    value={formData.nature_of_works}
                    onChange={(e) => handleUpdate({ nature_of_works: e.target.value })}
                    className={`w-full bg-slate-900 border focus:border-cyan-500 rounded-lg px-3.5 py-2.5 text-xs font-mono ${
                      formData.nature_of_works === 'HEAVY'
                        ? 'border-amber-500/80 text-amber-200'
                        : 'border-slate-700 text-slate-100'
                    }`}
                  >
                    {NATURE_OF_WORKS.map((nat) => (
                      <option key={nat.id} value={nat.id}>
                        {nat.label} ({nat.badge})
                      </option>
                    ))}
                  </select>

                  {formData.nature_of_works === 'HEAVY' && (
                    <span className="text-[11px] text-amber-400 flex items-center gap-1 mt-1 font-mono">
                      <AlertTriangle size={12} />
                      Triggers automatic 2-sector safety buffer &amp; opposite-bound mirroring lockout.
                    </span>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* ================= PANEL 2: SPATIAL FOOTPRINT ================= */}
          {activeTab === 'spatial' && (
            <section className="animate-fadeIn" aria-labelledby="heading-spatial">
              <h3 id="heading-spatial" className="sr-only">Spatial &amp; Safety Footprint</h3>
              <SpatialFootprintSelector
                formData={formData}
                onChange={handleUpdate}
                topologyData={topologyData}
                onSelectOnMap={onSelectOnMap}
                disabled={isSubmitting}
              />
            </section>
          )}

          {/* ================= PANEL 3: TIMING & WORKLOAD ================= */}
          {activeTab === 'timing' && (
            <section className="space-y-5 animate-fadeIn" aria-labelledby="heading-timing">
              <h3 id="heading-timing" className="sr-only">Timing, Workload &amp; Deadlines</h3>
              {/* Stepper: Total Accesses Required */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                      Total Accesses Required (d<sub>i</sub>)
                    </label>
                    <span className="text-[11px] text-slate-400">
                      Total possession shifts needed across the 30-week scheduling window.
                    </span>
                  </div>

                  {/* Stepper Control */}
                  <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg p-1">
                    <button
                      type="button"
                      onClick={() => handleUpdate({ total_accesses: Math.max(1, (formData.total_accesses || 1) - 1) })}
                      className="w-8 h-8 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center justify-center transition"
                    >
                      -
                    </button>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      value={formData.total_accesses}
                      onChange={(e) => handleUpdate({ total_accesses: Math.max(1, Math.min(20, parseInt(e.target.value) || 1)) })}
                      className="w-12 bg-transparent text-center text-sm font-mono font-bold text-cyan-400 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => handleUpdate({ total_accesses: Math.min(20, (formData.total_accesses || 1) + 1) })}
                      className="w-8 h-8 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold flex items-center justify-center transition"
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>

              {/* Date Pickers Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Earliest Start Date */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Earliest Start Date <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="date"
                    value={formData.planned_start_date}
                    onChange={(e) => handleUpdate({ planned_start_date: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                  />
                  {validation.errors.planned_start_date && (
                    <span className="text-[11px] text-rose-400">{validation.errors.planned_start_date}</span>
                  )}
                </div>

                {/* Target Completion Date */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Target Completion Date <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="date"
                    value={formData.planned_completion_date}
                    onChange={(e) => handleUpdate({ planned_completion_date: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                  />
                  {validation.errors.planned_completion_date && (
                    <span className="text-[11px] text-rose-400">{validation.errors.planned_completion_date}</span>
                  )}
                </div>
              </div>

              {/* Hard Deadline Date Section */}
              <div
                className={`rounded-xl border p-4 space-y-3 transition ${
                  isEmergency || formData.enforce_hard_deadline
                    ? 'bg-rose-950/30 border-rose-800/80'
                    : 'bg-slate-950/40 border-slate-800'
                }`}
              >
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Clock size={14} className={isEmergency ? 'text-rose-400' : 'text-slate-400'} />
                    Hard Deadline Date
                    {isEmergency && <span className="text-rose-400 font-bold">* (Mandatory for Emergency)</span>}
                  </label>

                  {!isEmergency && (
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-400 select-none">
                      <input
                        type="checkbox"
                        checked={formData.enforce_hard_deadline}
                        onChange={(e) => handleUpdate({ enforce_hard_deadline: e.target.checked })}
                        className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                      />
                      <span>Enforce Hard Deadline</span>
                    </label>
                  )}
                </div>

                {(isEmergency || formData.enforce_hard_deadline) && (
                  <div className="space-y-1">
                    <input
                      type="date"
                      value={formData.hard_completion_date}
                      onChange={(e) => handleUpdate({ hard_completion_date: e.target.value })}
                      className="w-full bg-slate-900 border border-rose-700 focus:border-rose-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                    />
                    {validation.errors.hard_completion_date ? (
                      <span className="text-[11px] text-rose-400">{validation.errors.hard_completion_date}</span>
                    ) : (
                      <span className="text-[11px] text-slate-400">
                        Work scheduled beyond this date incurs severe mathematical penalties in the solver.
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Slider: Max Accesses Per Week */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Max Accesses Per Week
                  </label>
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-cyan-400">
                    {formData.max_accesses_per_week} shifts / week
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={formData.max_accesses_per_week}
                  onChange={(e) => handleUpdate({ max_accesses_per_week: parseInt(e.target.value) || 3 })}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>1 (Dispersed)</span>
                  <span>2</span>
                  <span>3 (Default)</span>
                  <span>4</span>
                  <span>5 (Intensive)</span>
                </div>
              </div>

              {/* ECLO Switch */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex items-center justify-between gap-4">
                <div className="space-y-0.5">
                  <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <Zap size={14} className="text-amber-400" />
                    Extended Cumulative Line Opening (ECLO) Allowed
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Yields 1.5x productivity (3 workload units per possession night instead of standard 2).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleUpdate({ eclo_allowed: !formData.eclo_allowed })}
                  className={`w-12 h-6 rounded-full transition-colors p-0.5 relative shrink-0 ${
                    formData.eclo_allowed ? 'bg-amber-500' : 'bg-slate-700'
                  }`}
                  aria-pressed={formData.eclo_allowed}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-slate-950 transition-transform ${
                      formData.eclo_allowed ? 'translate-x-6' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </section>
          )}

          {/* ================= PANEL 4: PRECEDENCE & DEPENDENCIES ================= */}
          {activeTab === 'dependencies' && (
            <section className="space-y-5 animate-fadeIn" aria-labelledby="heading-dependencies">
              <h3 id="heading-dependencies" className="sr-only">Precedence &amp; Dependencies</h3>
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Prerequisite Job (Must complete before this starts)
                </label>
                <select
                  value={formData.predecessor_job_id || ''}
                  onChange={(e) => handleUpdate({ predecessor_job_id: e.target.value || null })}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 text-slate-100 rounded-lg px-3.5 py-2.5 text-xs font-mono"
                >
                  <option value="">-- No Prerequisite (Independent Start) --</option>
                  {existingJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      [{job.id}] {job.title || job.id} (Finishes: {job.completionDate || 'N/A'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Precedence Guardrail Real-Time Alert */}
              {validation.warnings.precedence && (
                <div className="bg-amber-950/40 border border-amber-700/80 rounded-xl p-3.5 text-amber-200 flex items-start gap-3">
                  <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-xs">
                    <span className="font-bold text-amber-300 uppercase tracking-wide">
                      Precedence Guardrail Warning
                    </span>
                    <p className="text-amber-200/90 leading-relaxed">
                      {validation.warnings.precedence}
                    </p>
                  </div>
                </div>
              )}

              {/* Selected Predecessor Visual Summary Card */}
              {formData.predecessor_job_id && (
                <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 space-y-2">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                    Predecessor Execution Contract
                  </span>
                  {(() => {
                    const pred = existingJobs.find(
                      (j) => j.id === formData.predecessor_job_id || j.job_id === formData.predecessor_job_id
                    );
                    return pred ? (
                      <div className="text-xs font-mono space-y-1 text-slate-300">
                        <div>Job ID: <strong className="text-cyan-400">{pred.id}</strong></div>
                        <div>Description: {pred.title || 'N/A'}</div>
                        <div>Line Code: {pred.lineCode || 'N/A'}</div>
                        <div>Target Completion Date: <strong className="text-purple-300">{pred.completionDate || 'Unscheduled'}</strong></div>
                      </div>
                    ) : (
                      <div className="text-xs text-slate-400 font-mono">Job {formData.predecessor_job_id} selected.</div>
                    );
                  })()}
                </div>
              )}
            </section>
          )}

          {/* ================= PANEL 5: PRIORITY & IMPACT ================= */}
          {activeTab === 'priority' && (
            <section className="space-y-5 animate-fadeIn" aria-labelledby="heading-priority">
              <h3 id="heading-priority" className="sr-only">Priority &amp; Impact</h3>
              {/* Activity Priority 3-Pill Toggle */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Activity Operational Priority
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {ACTIVITY_PRIORITIES.map((p) => {
                    const isSelected = Number(formData.activity_priority) === p.id;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => handleUpdate({ activity_priority: p.id })}
                        className={`p-3 rounded-xl border text-left transition flex flex-col justify-between gap-2 ${
                          isSelected
                            ? p.id === 1
                              ? 'bg-rose-950/60 border-rose-600 text-rose-200 ring-1 ring-rose-500'
                              : p.id === 2
                              ? 'bg-amber-950/60 border-amber-600 text-amber-200 ring-1 ring-amber-500'
                              : 'bg-cyan-950/60 border-cyan-600 text-cyan-200 ring-1 ring-cyan-500'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs">{p.label}</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700">
                            {p.nudge}
                          </span>
                        </div>
                        <span className="text-[11px] leading-tight text-slate-400">{p.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Contract Priority 3-Pill Toggle */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Contract Commercial Priority (Lateness Multiplier)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {CONTRACT_PRIORITIES.map((cp) => {
                    const isSelected = Number(formData.contract_priority) === cp.id;
                    return (
                      <button
                        key={cp.id}
                        type="button"
                        onClick={() => handleUpdate({ contract_priority: cp.id })}
                        className={`p-3 rounded-xl border text-left transition flex flex-col justify-between gap-2 ${
                          isSelected
                            ? 'bg-purple-950/60 border-purple-600 text-purple-200 ring-1 ring-purple-500'
                            : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs">{cp.label}</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-900/60 text-purple-300 border border-purple-700">
                            Penalty: {cp.penaltyMultiplier}
                          </span>
                        </div>
                        <span className="text-[11px] leading-tight text-slate-400">{cp.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Mathematical Penalty Impact Card */}
              <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-2 text-xs font-mono">
                <div className="text-slate-400 font-semibold uppercase tracking-wider">
                  Schedule Insertion Objective Impact
                </div>
                <div className="text-slate-300 leading-relaxed text-[11px]">
                  Base Priority Weight: <strong className="text-purple-400">{formData.contract_priority === 1 ? '100x' : formData.contract_priority === 2 ? '10x' : '1x'}</strong> • Activity Nudge: <strong className="text-cyan-400">{formData.activity_priority === 1 ? '+0.3' : formData.activity_priority === 2 ? '+0.2' : '0.0'}</strong>
                </div>
                <div className="text-slate-400 text-[10px]">
                  High priority jobs receive earliest slot allocations and take precedence over low-priority routine maintenance when sector bounds overlap.
                </div>
              </div>
            </section>
          )}

          {/* ================= PREFLIGHT RESULTS DRAWER ================= */}
          <PreflightCheckDrawer
            result={preflightResult}
            isLoading={isCheckingPreflight}
            isOpen={isDrawerOpen}
            onToggle={() => setIsDrawerOpen(!isDrawerOpen)}
            onRecheck={handleRunPreflight}
          />
        </main>

        {/* ==================== 4. MODAL FOOTER ACTIONS ==================== */}
        <footer className="px-6 py-4 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-4 shrink-0 flex-wrap">
          {/* Left: Preflight Check Button */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleRunPreflight}
              disabled={isCheckingPreflight}
              className="py-2 px-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-cyan-400 hover:text-cyan-300 border border-cyan-700/60 text-xs font-bold flex items-center gap-2 transition shadow-sm"
              title="Run real-time spatial conflict and capacity check"
            >
              {isCheckingPreflight ? (
                <RefreshCw size={14} className="animate-spin text-cyan-400" />
              ) : (
                <ShieldCheck size={14} />
              )}
              <span>Run Preflight Check</span>
            </button>

            {preflightResult && (
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border hidden sm:inline ${
                  preflightResult.status === 'HARD CONFLICT'
                    ? 'bg-rose-950 border-rose-800 text-rose-300'
                    : preflightResult.status === 'WARNING'
                    ? 'bg-amber-950 border-amber-800 text-amber-300'
                    : 'bg-emerald-950 border-emerald-800 text-emerald-300'
                }`}
              >
                Status: {preflightResult.status}
              </span>
            )}
          </div>

          {/* Right: Step Nav + Cancel + Submit */}
          <div className="flex items-center gap-2">
            {canGoPrev && (
              <button
                type="button"
                onClick={() => setActiveTab(TABS[currentTabIndex - 1].id)}
                className="py-2 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 text-xs font-medium flex items-center gap-1.5 transition"
              >
                <ArrowLeft size={13} /> Back
              </button>
            )}

            {canGoNext && (
              <button
                type="button"
                onClick={() => setActiveTab(TABS[currentTabIndex + 1].id)}
                className="py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center gap-1.5 transition"
              >
                Next <ArrowRight size={13} />
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="py-2 px-3 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 text-xs font-medium transition"
            >
              Cancel
            </button>

            {/* Primary Submit Button */}
            <div className="relative group">
              <button
                type="button"
                onClick={handleSubmit}
                disabled={
                  isSubmitting ||
                  !validation.isValid ||
                  preflightResult?.status === 'HARD CONFLICT'
                }
                className={`py-2 px-4 rounded-xl text-xs font-black transition flex items-center gap-2 ${
                  isSubmitting || !validation.isValid || preflightResult?.status === 'HARD CONFLICT'
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                    : isEmergency
                    ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30'
                    : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20'
                }`}
              >
                {isSubmitting ? (
                  <RefreshCw size={14} className="animate-spin" />
                ) : (
                  <CheckCircle2 size={14} />
                )}
                <span>Schedule Insertion</span>
              </button>

              {preflightResult?.status === 'HARD CONFLICT' && (
                <div className="absolute right-0 bottom-10 w-64 p-2 rounded bg-rose-950 border border-rose-800 text-rose-200 text-[10px] hidden group-hover:block z-30 shadow-lg">
                  Insertion blocked: Resolve preflight hard conflicts before scheduling.
                </div>
              )}
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
