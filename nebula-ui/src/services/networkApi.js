/**
 * Frontend network API client connecting to FastAPI /api/ps1/network endpoints.
 */

export async function fetchNetworkContext(signal) {
  const res = await fetch("/api/ps1/network/context", { signal });
  if (!res.ok) {
    throw new Error(`Failed to load network context: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNetworkTopology(signal) {
  const res = await fetch("/api/ps1/network/topology", { signal });
  if (!res.ok) {
    throw new Error(`Failed to load network topology: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNetworkActivities(signal) {
  const res = await fetch("/api/ps1/network/activities", { signal });
  if (!res.ok) {
    throw new Error(`Failed to load network activities: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchNetworkOccupancy(scenario = "A", week = 1, activityId = null, signal) {
  const params = new URLSearchParams({
    scenario,
    week: String(week),
  });
  if (activityId) {
    params.set("activity_id", activityId);
  }

  const res = await fetch(`/api/ps1/network/occupancy?${params.toString()}`, { signal });
  if (!res.ok) {
    throw new Error(`Failed to load occupancy for week ${week}: ${res.statusText}`);
  }
  return res.json();
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

