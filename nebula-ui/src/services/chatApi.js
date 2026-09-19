/**
 * API client for the PS1 Grounded Schedule Chatbot and Explanations.
 */

export async function sendChatMessage({
  sessionId,
  instanceId,
  instanceRevisionId,
  runId = null,
  scenario = 'A',
  mode = 'requirements',
  baselineRunId,
  question,
  selectedActivityId,
  selectedLocationId,
  selectedWeek,
}) {
  const payload = {
    session_id: sessionId || null,
    instance_id: instanceId || null,
    instance_revision_id: instanceRevisionId || null,
    run_id: runId || null,
    scenario: scenario || 'A',
    mode: mode || 'requirements',
    baseline_run_id: baselineRunId || null,
    question,
    selected_activity_id: selectedActivityId || null,
    selected_location_id: selectedLocationId || null,
    selected_week: selectedWeek || null,
  };

  const response = await fetch('/api/ps1/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Demo-User': 'demo-officer', // Server decides role; demo header for local development
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || `Chat request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchExplanation(runId, activityId, baselineRunId = null) {
  const url = new URL(`/api/ps1/runs/${runId}/explanations/${activityId}`, window.location.origin);
  if (baselineRunId) {
    url.searchParams.set('baseline_run_id', baselineRunId);
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'X-Demo-User': 'demo-officer',
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || `Explanation request failed with status ${response.status}`);
  }

  return response.json();
}
