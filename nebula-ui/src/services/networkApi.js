/**
 * Frontend network API client connecting to FastAPI /api/ps1/network endpoints.
 */

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

export async function fetchNetworkTopology(signal) {
  const data = requireObject(
    await fetchJson("/api/ps1/network/topology", signal, "network topology"),
    "network topology"
  );
  ["lines", "stations", "sectors", "locations"].forEach((key) => {
    requireArray(data[key], `network topology.${key}`);
  });
  return data;
}

export async function fetchNetworkActivities(signal) {
  return requireArray(
    await fetchJson("/api/ps1/network/activities", signal, "network activities"),
    "network activities"
  );
}

export async function fetchNetworkOccupancy(scenario = "A", week = 1, activityId = null, signal) {
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
