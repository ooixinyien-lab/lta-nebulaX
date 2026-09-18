# Legacy Prototype UI Demo Mode

> [!NOTE]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This document describes the mock UI demo mode for the legacy single-night prototype (`demo-snapshot.json`).
> New PS1 and operational features belong in `nebula-ui/` and consume `/api/ps1/...`: eight-file upload, scenario comparison, exact global nights, recurrence, low-churn replanning, manual-edit preflight and grounded explanations. This legacy fixture is not their implementation.

Set `UI_DEMO=true` in `.env` and restart the Python server. This option is active
only with `APP_ENV=development` and `AUTH_MODE=demo`. Set it to `false` and restart
to reconnect the UI to the normal planning APIs.

The fixture in `frontend/demo-snapshot.json` adapts the comprehensive EWL data:
eight scheduled jobs, two approved jobs in the pool, and two unapproved jobs.
Two scheduled jobs start locked. Seven demo nights are available from 14 September
2026. Owners are mapped to the two demo requester profiles.

`frontend/src/lib/demo-api.js` implements the temporary browser API. Auto-schedule
restores preset placements while respecting locks. Dragging, undo/redo, approvals,
resource edits, request submission/withdrawal and saving use browser local storage.
Save demo schedule makes the plan visible to requester profiles in the same browser.
Refresh preserves draft placements. Reset synthetic demo restores this fixture.
The normal SQLite database is not modified by these actions.

Overlap hints check shared sectors, engineers and equipment only. The preset is
for UI development and is not solver validated; backend constraints and resource
outages do not govern mock scheduling. Demo changes are not shared across browsers.

The legacy drag behaviour must not be reused as PS1 conflict authority. In the canonical workflow, a drag creates a draft sent to backend preflight with run/revision/access IDs and the proposed week or `service_date`. The server checks the complete official and operational rule set, returns structured conflicts/warnings, and repeats validation before save. Exact dates come from an explicit calendarisation result; `access_night` is never shown as a weekday.

Likewise, any future chatbot belongs to the canonical UI. It receives a deterministic, role-scoped explanation fact pack for the selected run/activity and may use only read-only schedule tools. It cannot operate on this browser-local fixture as if it were a validated PS1 plan.

Check with `node scripts/check-ui-demo.mjs` and `node scripts/check-js.mjs`.
