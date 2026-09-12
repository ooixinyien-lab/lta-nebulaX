# UI demo

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

Check with `node scripts/check-ui-demo.mjs` and `node scripts/check-js.mjs`.
