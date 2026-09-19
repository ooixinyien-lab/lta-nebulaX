import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  acceptOperationalSchedule, addOperationalJob, checkConflicts, clearPlanningDatabase,
  createOperationalBaseline, executeOfficialRun, loadOfficialRunProgress, loadPlanningContext, loadSchedule,
  solveOperations, solveRequirements, uploadOfficialInstance,
} from "../services/planningApi";

const STORAGE_KEY = "forrail-planning-context-v1";
const LEGACY_STORAGE_KEY = "nebulax-planning-context-v1";
const EMPTY = {
  mode: "requirements", scenario: "A",
  requirements: { A: null, B: null, C: null },
  operations: { A: null, B: null, C: null },
};
const PlanningContext = createContext(null);

const newest = (rows) => [...rows].sort((left, right) =>
  String(right.created_at || "").localeCompare(String(left.created_at || "")));

export function reconcilePlanningState(current, catalog) {
  const instances = newest(catalog.instances || []);
  const baselines = newest(catalog.operational_baselines || []);
  const officialRuns = newest(catalog.official_runs || []);
  const operationalRuns = newest(catalog.operational_runs || []);

  const requirements = Object.fromEntries(["A", "B", "C"].map((scenario) => {
    const selected = current.requirements?.[scenario];
    const revision = instances.find((row) => row.revision_id === selected?.instanceRevisionId)
      || instances[0];
    if (!revision) return [scenario, null];
    const selectedRun = officialRuns.find((row) =>
      row.run_id === selected?.runId
      && row.revision_id === revision.revision_id
      && row.scenario === scenario
      && row.status === "SUCCEEDED")
      || officialRuns.find((row) =>
        row.revision_id === revision.revision_id
        && row.scenario === scenario
        && row.status === "SUCCEEDED");
    return [scenario, {
      mode: "requirements", scenario,
      instanceId: revision.instance_id,
      instanceRevision: revision.revision_number,
      instanceRevisionId: revision.revision_id,
      runId: selectedRun?.run_id || null,
    }];
  }));

  const operations = Object.fromEntries(["A", "B", "C"].map((scenario) => {
    const selected = current.operations?.[scenario];
    const matchingBaselines = selected?.baselineId
      ? baselines.filter((row) => row.baseline_id === selected.baselineId)
      : [];
    const baseline = matchingBaselines.find((row) => row.baseline_revision === selected?.baselineRevision)
      || matchingBaselines[0]
      || baselines[0];
    if (!baseline) return [scenario, null];
    const selectedRun = operationalRuns.find((row) =>
      row.run_id === selected?.runId
      && row.baseline_id === baseline.baseline_id
      && row.baseline_revision === baseline.baseline_revision
      && row.scenario === scenario
      && row.status === "SUCCEEDED")
      || operationalRuns.find((row) =>
        row.baseline_id === baseline.baseline_id
        && row.baseline_revision === baseline.baseline_revision
        && row.scenario === scenario
        && row.status === "SUCCEEDED");
    return [scenario, {
      mode: "operations", scenario,
      baselineId: baseline.baseline_id,
      baselineRevision: baseline.baseline_revision,
      runId: selectedRun?.run_id || null,
      instanceRevisionId: baseline.official_revision_id,
    }];
  }));

  return { ...current, requirements, operations };
}

const readSaved = () => {
  try { return { ...EMPTY, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY) || "{}") }; }
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
      const reconciled = reconcilePlanningState(current, catalog);
      return JSON.stringify(reconciled) === JSON.stringify(current) ? current : reconciled;
    });
  }, [catalog]);

  const refresh = useCallback(async () => {
    if (!identity?.runId && state.mode === "requirements") { setSchedule(null); setConflicts([]); return; }
    if ((!identity?.baselineId || !identity?.runId) && state.mode === "operations") { setSchedule(null); setConflicts([]); return; }
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
    if (!identity) throw new Error("No persisted planning instance is available. Upload the official eight-file bundle first.");
    setSolving(true); setError(null);
    try {
      if (state.mode === "requirements") {
        const completed = {};
        for (const scenario of ["A", "B", "C"]) {
          const scenarioIdentity = state.requirements[scenario] || { ...identity, scenario };
          const queued = await solveRequirements({ ...scenarioIdentity, scenario });
          await executeOfficialRun(queued.run_id);
          let progress = await loadOfficialRunProgress(queued.run_id);
          while (["QUEUED", "RUNNING"].includes(progress.status)) {
            await new Promise((resolve) => setTimeout(resolve, 350));
            progress = await loadOfficialRunProgress(queued.run_id);
          }
          if (progress.status !== "SUCCEEDED") throw new Error(`Official solve ${scenario} ended with ${progress.status}`);
          completed[scenario] = { ...scenarioIdentity, scenario, runId: queued.run_id };
        }
        setState((current) => ({ ...current, requirements: { ...current.requirements, ...completed } }));
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
    localStorage.removeItem(LEGACY_STORAGE_KEY);
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
