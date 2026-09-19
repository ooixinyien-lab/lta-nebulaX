/**
 * Frontend network API client connecting to FastAPI /api/ps1/network endpoints.
 */
import { loadMapSchedule } from "./planningApi";

function requireObject(data, endpoint) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new Error(`Invalid response from ${endpoint}: expected an object`);
  }
  return data;
}

function requireArray(data, endpoint) {
  if (!Array.isArray(data)) {
    throw new Error(`Invalid response from ${endpoint}: expected an array`);
  }
  return data;
}

async function fetchJson(url, signal, endpoint) {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    throw new Error(`Failed to load ${endpoint}: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNetworkContext(signal) {
  return requireObject(
    await fetchJson("/api/ps1/network/context", signal, "network context"),
    "network context"
  );
}

export async function fetchNetworkTopology(signal, revisionId = null) {
  const suffix = revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : "";
  const data = requireObject(
    await fetchJson(`/api/ps1/network/topology${suffix}`, signal, "network topology"),
    "network topology"
  );
  ["lines", "stations", "sectors", "locations"].forEach((key) => {
    requireArray(data[key], `network topology.${key}`);
  });
  return data;
}

export async function fetchNetworkActivities(signal, revisionId = null) {
  const suffix = revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : "";
  return requireArray(
    await fetchJson(`/api/ps1/network/activities${suffix}`, signal, "network activities"),
    "network activities"
  );
}

export async function fetchNetworkOccupancy(scenario = "A", week = 1, activityId = null, signal, identity = null) {
  if (identity) {
    return loadMapSchedule(identity, week, signal);
  }
  const params = new URLSearchParams({
    scenario,
    week: String(week),
  });
  if (activityId) {
    params.set("activity_id", activityId);
  }

  return requireObject(
    await fetchJson(
      `/api/ps1/network/occupancy?${params.toString()}`,
      signal,
      `occupancy for week ${week}`
    ),
    `occupancy for week ${week}`
  );
}

export async function fetchFullSchedule(scenario = "A", signal) {
  const res = await fetch(`/api/ps1/network/full-schedule?scenario=${scenario}`, { signal });
  if (!res.ok) {
    throw new Error(`Failed to load full schedule: ${res.statusText}`);
  }
  return res.json();
}

export async function validateScheduleAPI(scenario, accesses, occupancies, signal) {
  const res = await fetch("/api/ps1/network/validate-schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, accesses, occupancies }),
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to validate schedule: ${res.statusText}`);
  }
  return res.json();
}

export async function rescheduleWithSolver(scenario = "A", signal) {
  const res = await fetch(`/api/ps1/network/reschedule?scenario=${scenario}`, {
    method: "POST",
    signal,
  });
  if (!res.ok) {
    throw new Error(`Failed to reschedule with solver: ${res.statusText}`);
  }
  return res.json();
}

