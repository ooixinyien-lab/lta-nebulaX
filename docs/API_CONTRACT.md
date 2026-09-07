# API contract v0.1

Base path: `/api`. Frontend uses same-origin fetch. No CORS configuration or direct SQLite access is required for this single-server starter.

In demo mode use `X-Demo-User: demo-track`, `demo-signals` or `demo-officer`. These headers are intentionally forgeable for a LOCAL synthetic demo. In Supabase mode use `Authorization: Bearer <access token>`; demo headers are ignored.

## Routes

| Method and route | Role | Purpose |
|---|---|---|
| `GET /health` | Public | Basic server readiness |
| `GET /config` | Public | Auth mode, engine name and intentionally public Auth configuration |
| `GET /me` | Signed in | Backend-assigned identity and role |
| `GET /planning-snapshot` | Signed in | Current data; requesters get only their own requests and allocations plus anonymised occupancy |
| `POST /requests` | Requester | Validate/store a request; server sets ownership/status and eligible engineers |
| `POST /requests/{id}/cancel` | Owning requester | Withdraw an unbooked request if no active dependent request blocks withdrawal |
| `POST /conflicts/check` | Officer | Check requested positions combined with current bookings |
| `POST /schedule/proposals` | Officer | Calculate one plan for all active work; no publication |
| `GET /proposals` | Officer | Last ten stored feasible proposals |
| `POST /proposals/{id}/commit` | Officer | Approve and publish that exact version atomically |
| `PATCH /resources` | Officer | Add an unavailable interval or change equipment serviceability |
| `GET /audit` | Officer | Recent local audit events |
| `POST /demo/reset` | Demo officer only | Destructively reload seed; unavailable with real Supabase Auth |

The commit action combines the officer's approval and publication in this starter. There is no multi-owner approval workflow yet.

## Create request

Do not send `owner_id`, `role`, `status`, `eligible_engineers`, `power_zone` or a booking ID. Additional fields are rejected. The server derives these values.

```json
{
  "title": "Inspection request",
  "work_sector": "S04",
  "protected_sectors": ["S03", "S04"],
  "power_requirement": "OFF",
  "required_skill": "inspection",
  "preferred_engineer": "E02",
  "required_equipment_ids": ["Q02"],
  "technicians_required": 1,
  "phases": [
    {"name": "setup", "duration_minutes": 10},
    {"name": "work", "duration_minutes": 30},
    {"name": "test", "duration_minutes": 10},
    {"name": "handback", "duration_minutes": 10}
  ],
  "preferred_start": "2026-09-14T02:30:00+08:00",
  "earliest_start": "2026-09-14T01:00:00+08:00",
  "deadline": "2026-09-15T04:30:00+08:00",
  "allowed_dates": ["2026-09-14", "2026-09-15"],
  "depends_on": []
}
```

The work sector must be included in the protection footprint. Times must include a timezone. Existing referenced IDs must be valid. Date choices must come from the seeded calendar. New requester-defined dependencies can refer to their own active requests. The initial operator-style fixture has a cross-team dependency created by seed data.

`power_requirement` accepts `"ON"`, `"OFF"`, or `"NONE"`. (Legacy input `"ANY"` is automatically normalized to `"NONE"` for backward compatibility). Requests also support `timing_mode` (`"EXACT"`, `"RANGE"`, `"ANY_TIME"`) and deferral eligibility `deferrable: bool` ($D_j^{allow}$).

The API can accept a request whose desired time conflicts. That is the point of the request queue; schema validation is not the same as allocating a feasible slot.

## Conflict shape

```json
{
  "planning_version": 1,
  "issues": [{
    "code": "POWER",
    "request_ids": ["R01", "R03"],
    "message": "Opposed power requirements in Z01; allow the configured 10-minute guard.",
    "resource": "Z01",
    "severity": "error"
  }]
}
```

Codes identify modelled violations of the 9 hard constraints:
- `ENGINEERING_WINDOW`: Work package exceeds allowed sector engineering window or morning handback buffer ($B$).
- `SPACE`: Exclusive protected footprints overlap ($C^{sector}_{jk} = 1$).
- `BLACKOUT`: Work package or vehicle transit intersects confirmed sector unavailability ($\mathcal{B}_s$).
- `POWER`: Incompatible traction power requirements (`ON` vs `OFF`) in a shared feeding zone ($C^{power}_{jk}=1$).
- `WORK_COMPATIBILITY`: Concurrent activities violate operational compatibility rules ($C^{work}_{jk}=1$).
- `ENGINEER`: Specialist engineer double-booked, lacking required competency qualification ($Q_{eq}$), or unavailable ($\mathcal{B}_e$).
- `MANPOWER`: Concurrent technician / pooled demand exceeds pool capacity ($C_r$).
- `EQUIPMENT`: Assigned equipment double-booked or unavailable.
- `TRANSFER_TIME`: Specialist engineer, vehicle, or equipment lacks required travel time ($\tau^E_{jk}$) between consecutive jobs.
- `DEPENDENCY`: Predecessor task incomplete or handover clearance buffer ($\Delta_{pj}$) violated.
- `LOCKED_BOOKING`: Attempted modification to a frozen approved booking inside freeze horizon ($H^{freeze}$).
- `MANDATORY_DROPPED`: Service-critical mandatory work ($M_j = 1$) omitted or deferred.
- `REVIEW_REQUIRED`: Undefined rule or missing compatibility specification.

The message is generated from rules/data, not an LLM.

## Proposal shape

```json
{
  "id": "P-example",
  "planning_version": 1,
  "status_workflow": "draft",
  "status": "FEASIBLE",
  "engine": "cp_sat",
  "elapsed_seconds": 0.5,
  "message": "All active jobs allocated under the demo constraints. Officer approval is still required.",
  "allocations": [],
  "changes": []
}
```

This is an illustrative shape, not a solver result. A publishable successful response contains the complete nonempty allocation list and changed/new allocations. Infeasible/unavailable results have no allocations and cannot be published. The route only stores successful proposals.

An allocation contains:

```json
{
  "request_id": "R03",
  "start": "2026-09-14T02:30:00+08:00",
  "end": "2026-09-14T03:30:00+08:00",
  "engineer_id": "E03",
  "equipment_ids": ["Q03"],
  "locked": true
}
```

## Publish

```json
{"expected_version": 1}
```

The server verifies role, proposal state, exact current revision and the complete plan within a write transaction. It saves all allocations, updates request states, increments the revision and appends an audit record together. A stale or invalid plan gets `409` without a partial write.

Generating a proposal or appending an audit event does not change planning availability. Requests, resource updates, reset and actual publication do change the planning revision.

## Resource change example

```json
{
  "kind": "engineers",
  "id": "E01",
  "unavailable_from": "2026-09-14T02:20:00+08:00",
  "unavailable_to": "2026-09-14T04:30:00+08:00"
}
```

For equipment serviceability:

```json
{"kind": "equipment", "id": "Q01", "serviceable": false}
```

## Planning Snapshot and Domain Model

The full planning state returned by `GET /planning-snapshot` is typed and validated by `PlanningSnapshot` in `backend/app/models.py`. It unifies:

- `metadata`: Schema version, revision counter, timezone, and scope.
- `stations`: Physical station nodes ($N01 \dots N07$).
- `sectors`: Directed track sectors ($S01 \dots S06$), power zone mapping, and exclusive protection flags.
- `engineering_windows`: Calendar date boundaries and open sector windows.
- `blackouts`: Scheduled maintenance freezes and third-party restrictions ($b \in \mathcal{B}$).
- `planning_rules`: Minute grid, transfer allowances, power transition guards, and morning buffer ($T_{\text{buffer}}$).
- `engineers`: Personnel qualification, skills, and availability windows.
- `equipment`: Physical equipment capacity, serviceability, and availability.
- `resource_pools`: Cumulative shared resources ($C_r$, e.g. general technicians `TECH`).
- `requests`: All submitted and scheduled maintenance work orders ($j \in \mathcal{J}$).
- `committed_allocations`: Historic, locked bookings.
- `vehicles`: Engineering vehicle fleet ($\mathcal{V}$) and predefined transit corridors.

## Error handling

- `401`: missing/invalid identity.
- `403`: role not allowed.
- `404`: unknown or inaccessible record.
- `409`: stale state or invalid operation.
- `422`: validation failure.
- `503`: database or identity-provider temporarily unavailable.

FastAPI's validation detail may be an array; other errors may contain a string or structured detail. `frontend/src/lib/api.js` normalises these for the UI. Do not display raw secrets or authentication tokens in errors/logs.
