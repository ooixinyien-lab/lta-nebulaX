const parseResponse = async (response) => {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? payload;
    const message = typeof detail === 'string'
      ? detail
      : detail?.message || JSON.stringify(detail);
    throw new Error(message || `Request failed (${response.status})`);
  }
  return payload;
};

export const authHeaders = (identity) => {
  if (identity) return { 'X-Demo-User': identity };
  const token = typeof window !== 'undefined'
    ? window.localStorage.getItem('nebula_access_token')
    : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const getAuthConfig = () => fetch('/api/ps1/auth/config').then(parseResponse);

export const importScheduleBundle = (revisionId, files, identity) => {
  const body = new FormData();
  body.append('instance_revision_id', revisionId);
  files.forEach((file) => body.append('files', file));
  return fetch('/api/ps1/schedule-bundles', {
    method: 'POST',
    headers: authHeaders(identity),
    body,
  }).then(parseResponse);
};

export const createDemoCalendar = (revisionId, identity) => fetch(
  '/api/ps1/enrichments/demo-calendar',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(identity) },
    body: JSON.stringify({ instance_revision_id: revisionId }),
  },
).then(parseResponse);

export const createCalendar = (definition, identity) => fetch('/api/ps1/enrichments', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...authHeaders(identity) },
  body: JSON.stringify(definition),
}).then(parseResponse);

export const queueCalendarisation = (
  bundleId,
  calendarRevisionId,
  instanceRevisionId,
  identity,
) => fetch(`/api/ps1/schedule-bundles/${bundleId}/calendarize`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...authHeaders(identity) },
  body: JSON.stringify({
    calendar_revision_id: calendarRevisionId,
    expected_instance_revision_id: instanceRevisionId,
    commitments: [],
    options: { time_limit_seconds: 30, num_search_workers: 8, random_seed: 0 },
  }),
}).then(parseResponse);

export const getCalendarisation = (attemptId, identity) => fetch(
  `/api/ps1/calendarisations/${attemptId}`,
  { headers: authHeaders(identity) },
).then(parseResponse);

export const autoAssignActualNights = (identity, scenario = 'A') => {
  const url = scenario
    ? `/api/ps1/calendar-preview/assign-default?scenario=${encodeURIComponent(scenario)}`
    : '/api/ps1/calendar-preview/assign-default';
  return fetch(url, {
    method: 'POST',
    headers: { ...authHeaders(identity) },
  }).then(parseResponse);
};

export const getCalendarPreviewContext = (identity, bundleId, scenario) => {
  const params = new URLSearchParams();
  if (bundleId) params.set('bundle_id', bundleId);
  if (scenario) params.set('scenario', scenario);
  const query = params.toString() ? `?${params.toString()}` : '';
  return fetch(`/api/ps1/calendar-preview/context${query}`, { headers: authHeaders(identity) }).then(parseResponse);
};

