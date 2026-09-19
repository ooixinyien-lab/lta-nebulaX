const JSON_HEADERS = { "Content-Type": "application/json" };

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { "X-Demo-User": "demo-officer", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail?.message || body.detail || body.message || response.statusText;
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    error.status = response.status;
    error.payload = body;
    throw error;
  }
  return body;
}

export const loadPlanningContext = (signal) => requestJson("/api/ps1/planning-context", { signal });

export async function uploadOfficialInstance(files) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  try {
    return await requestJson("/api/ps1/instances/upload", { method: "POST", body: form });
  } catch (error) {
    if (error.status === 409 && error.payload?.detail?.revision_id) {
      return {
        instance_id: error.payload.detail.instance_id,
        revision_id: error.payload.detail.revision_id,
        fingerprint: error.payload.detail.fingerprint,
        duplicate: true,
      };
    }
    throw error;
  }
}

export const clearPlanningDatabase = () => requestJson("/api/ps1/planning-data", { method: "DELETE" });

export const createOperationalBaseline = (officialRevisionId) => requestJson(
  "/api/ps1/schedule-insertion/baselines/from-official",
  { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ official_revision_id: officialRevisionId }) },
);

function identityParams(identity, week) {
  const params = new URLSearchParams({ mode: identity.mode, scenario: identity.scenario });
  if (identity.mode === "requirements") {
    if (identity.instanceRevisionId) params.set("instance_revision_id", identity.instanceRevisionId);
    if (identity.runId) params.set("run_id", identity.runId);
  } else {
    if (identity.baselineId) params.set("baseline_id", identity.baselineId);
    if (identity.baselineRevision) params.set("baseline_revision", String(identity.baselineRevision));
    if (identity.runId) params.set("run_id", identity.runId);
  }
  if (week) params.set("week", String(week));
  return params;
}

export const loadSchedule = (identity, signal) => requestJson(
  `/api/ps1/schedules/project?${identityParams(identity)}`, { signal },
);
export const loadMapSchedule = (identity, week, signal) => requestJson(
  `/api/ps1/schedules/project?${identityParams(identity, week)}`, { signal },
);

export async function solveRequirements(identity, timeLimitSeconds = 600) {
  return requestJson("/api/ps1/solve", {
    method: "POST", headers: JSON_HEADERS,
    body: JSON.stringify({
      instance_id: identity.instanceId,
      instance_revision_id: identity.instanceRevisionId,
      scenario: identity.scenario,
      time_limit_seconds: timeLimitSeconds,
    }),
  });
}

export const loadOfficialRunProgress = (runId) => requestJson(`/api/ps1/runs/${runId}/progress`);
export const executeOfficialRun = (runId) => requestJson(`/api/ps1/runs/${runId}/execute`, { method: "POST" });

export const addOperationalJob = (identity, addition) => requestJson(
  `/api/ps1/schedule-insertion/baselines/${encodeURIComponent(identity.baselineId)}/additions`,
  { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ baseline_revision: identity.baselineRevision, additions: [addition] }) },
);

export const solveOperations = (identity, asOf, timeLimitSeconds = 30) => requestJson(
  "/api/ps1/schedule-insertion/runs",
  {
    method: "POST", headers: JSON_HEADERS,
    body: JSON.stringify({
      official_revision_id: identity.instanceRevisionId,
      request: {
        baseline_id: identity.baselineId,
        baseline_revision: identity.baselineRevision,
        scenario: identity.scenario,
        as_of: asOf,
        options: { time_limit_seconds: timeLimitSeconds, scenario_cost_allowance: 10 },
      },
    }),
  },
);

export const acceptOperationalSchedule = (identity) => requestJson(
  `/api/ps1/schedule-insertion/baselines/${encodeURIComponent(identity.baselineId)}/from-run/${encodeURIComponent(identity.runId)}`,
  { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ expected_baseline_revision: identity.baselineRevision }) },
);

export const checkConflicts = (identity, signal) => {
  if (identity.mode !== "operations") return Promise.resolve({ passed: true, findings: [] });
  const params = new URLSearchParams({
    baseline_id: identity.baselineId,
    baseline_revision: String(identity.baselineRevision),
    scenario: identity.scenario,
  });
  if (identity.runId) params.set("run_id", identity.runId);
  return requestJson(`/api/ps1/schedule-insertion/validate?${params}`, { signal });
};
