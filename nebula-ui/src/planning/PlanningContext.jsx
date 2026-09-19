import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  acceptOperationalSchedule, addOperationalJob, checkConflicts, clearPlanningDatabase,
  createOperationalBaseline, executeOfficialRun, loadOfficialRunProgress, loadPlanningContext, loadSchedule,
  solveOperations, solveRequirements, uploadOfficialInstance,
} from "../services/planningApi";

const STORAGE_KEY = "nebulax-planning-context-v1";
const EMPTY = {
  mode: "requirements", scenario: "A",
  requirements: { A: null, B: null, C: null },
  operations: { A: null, B: null, C: null },
};
const PlanningContext = createContext(null);

const readSaved = () => {
  try { return { ...EMPTY, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") }; }
  catch { return EMPTY; }
};

export function PlanningProvider({ children }) {
  const [state, setState] = useState(readSaved);
  const [catalog, setCatalog] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [conflicts, setConflicts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [solving, setSolving] = useState(false);
  const [error, setError] = useState(null);
  const [highlightedJobId, setHighlightedJobId] = useState(null);
  const identity = state.mode === "requirements" ? state.requirements[state.scenario] : state.operations[state.scenario];

  const refreshCatalog = useCallback(async () => {
    const next = await loadPlanningContext();
    setCatalog(next);
    return next;
  }, []);

  useEffect(() => { refreshCatalog().catch((err) => setError(err.message)); }, [refreshCatalog]);
  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }, [state]);
  useEffect(() => {
    if (!catalog) return;
    setState((current) => {
      const requirements = Object.fromEntries(Object.entries(current.requirements).map(([scenario, selected]) => [scenario,
        selected && catalog.instances.some((row) => row.revision_id === selected.instanceRevisionId) ? selected : null]));
      const operations = Object.fromEntries(Object.entries(current.operations).map(([scenario, selected]) => [scenario,
        selected && catalog.operational_baselines.some((row) => row.baseline_id === selected.baselineId && row.baseline_revision === selected.baselineRevision) ? selected : null]));
      return JSON.stringify(requirements) === JSON.stringify(current.requirements) && JSON.stringify(operations) === JSON.stringify(current.operations)
        ? current : { ...current, requirements, operations };
    });
  }, [catalog]);

  const refresh = useCallback(async () => {
    if (!identity?.runId && state.mode === "requirements") { setSchedule(null); setConflicts([]); return; }
    if (!identity?.baselineId && state.mode === "operations") { setSchedule(null); setConflicts([]); return; }
    const controller = new AbortController();
    setLoading(true); setError(null);
    try {
      const [nextSchedule, validation] = await Promise.all([
        loadSchedule(identity, controller.signal), checkConflicts(identity, controller.signal),
      ]);
      setSchedule(nextSchedule);
      setConflicts(validation.findings || nextSchedule.conflicts || []);
    } catch (err) {
      if (err.name !== "AbortError") { setError(err.message); setSchedule(null); }
    } finally { setLoading(false); }
    return () => controller.abort();
  }, [identity, state.mode]);

  useEffect(() => { refresh(); }, [refresh]);

  const selectMode = (mode) => setState((current) => ({ ...current, mode }));
  const selectScenario = (scenario) => setState((current) => ({ ...current, scenario }));

  const upload = async (files) => {
    setLoading(true); setError(null);
    try {
      const uploaded = await uploadOfficialInstance(files);
      const baseline = await createOperationalBaseline(uploaded.revision_id);
      setState((current) => ({
        ...current,
        requirements: Object.fromEntries(["A", "B", "C"].map((scenario) => [scenario, {
          mode: "requirements", scenario, instanceId: uploaded.instance_id,
          instanceRevision: 1, instanceRevisionId: uploaded.revision_id, runId: null,
        }])),
        operations: Object.fromEntries(["A", "B", "C"].map((scenario) => [scenario, {
          mode: "operations", scenario, baselineId: baseline.baseline.baseline_id,
          baselineRevision: baseline.baseline.revision, runId: null,
          instanceRevisionId: uploaded.revision_id,
        }])),
      }));
      await refreshCatalog();
      return uploaded;
    } finally { setLoading(false); }
  };

  const solve = async () => {
    if (!identity) return;
    setSolving(true); setError(null);
    try {
      if (state.mode === "requirements") {
        const queued = await solveRequirements(identity);
        await executeOfficialRun(queued.run_id);
        let progress = await loadOfficialRunProgress(queued.run_id);
        while (["QUEUED", "RUNNING"].includes(progress.status)) {
          await new Promise((resolve) => setTimeout(resolve, 350));
          progress = await loadOfficialRunProgress(queued.run_id);
        }
        if (progress.status !== "SUCCEEDED") throw new Error(`Official solve ended with ${progress.status}`);
        setState((current) => ({ ...current, requirements: { ...current.requirements, [current.scenario]: { ...identity, runId: queued.run_id } } }));
      } else {
        const result = await solveOperations(identity, new Date().toISOString());
        if (result.result.status !== "SUCCEEDED") throw new Error(`Operational solve ended with ${result.result.status}`);
        setState((current) => ({ ...current, operations: { ...current.operations, [current.scenario]: { ...identity, runId: result.run_id } } }));
      }
      await refreshCatalog();
    } finally { setSolving(false); }
  };

  const addJob = async (addition) => {
    try {
      const response = await addOperationalJob(identity, addition);
      setState((current) => ({ ...current, operations: Object.fromEntries(Object.entries(current.operations).map(([scenario, selected]) => [scenario,
        selected?.baselineId === identity.baselineId ? { ...selected, baselineRevision: response.baseline.revision, runId: null } : selected])) }));
      setHighlightedJobId(addition.job.job_id);
      return response;
    } catch (error) {
      if (error.status === 409) {
        const nextCatalog = await refreshCatalog();
        const latest = nextCatalog.operational_baselines.find((row) => row.baseline_id === identity.baselineId);
        if (latest) setState((current) => ({ ...current, operations: Object.fromEntries(Object.entries(current.operations).map(([scenario, selected]) => [scenario,
          selected?.baselineId === identity.baselineId ? { ...selected, baselineRevision: latest.baseline_revision, runId: null } : selected])) }));
      }
      throw error;
    }
  };

  const accept = async () => {
    const response = await acceptOperationalSchedule(identity);
    setState((current) => ({ ...current, operations: Object.fromEntries(Object.entries(current.operations).map(([scenario, selected]) => [scenario,
      selected?.baselineId === identity.baselineId ? { ...selected, baselineRevision: response.baseline.revision, runId: null } : selected])) }));
    await refreshCatalog();
  };

  const clearDatabase = async () => {
    await clearPlanningDatabase();
    localStorage.removeItem(STORAGE_KEY);
    setState(EMPTY); setCatalog(null); setSchedule(null); setConflicts([]); setError(null); setHighlightedJobId(null);
    await refreshCatalog();
  };

  const value = {
    ...state, identity, catalog, schedule, conflicts, loading, solving, error, highlightedJobId,
    selectMode, selectScenario, upload, solve, addJob, accept, clearDatabase, refresh,
  };
  return <PlanningContext.Provider value={value}>{children}</PlanningContext.Provider>;
}

export const usePlanning = () => {
  const value = useContext(PlanningContext);
  if (!value) throw new Error("usePlanning must be used within PlanningProvider");
  return value;
};
