# NebulaX API Contract

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This document specifies the HTTP API contracts for NebulaX.
> Per [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), the **Problem Statement 1 (PS1) Official Adoption Plan** acts as the single authoritative source of truth.
>
> NebulaX provides two API layers:
> 1. **PS1 and operational API (`/api/ps1/...`):** Typed contract for official instance upload/solve/export plus calendarisation, recurrence, replanning, manual-edit validation and grounded explanations.
> 2. **Legacy Transition API (`/api/...`):** Preserved during transition to support existing synthetic prototype frontend components and historical integration tests.

---

# Part 1: Official PS1 API Contract (`/api/ps1`)

Base path: `/api/ps1`. Supports the official PS1 workflow and the separately identified NebulaX operational enrichment layer. Only an eligible `competition` run can generate an official three-CSV submission.

### Implemented persistence endpoints

The current persistence implementation provides upload, instance metadata, queued runs, progress, and stored results. Routes marked **Planned** below are the agreed target contract; documentation does not imply that a solver worker, export endpoint, enrichment workflow, chatbot or official validator already exists.

Upload accepts exactly eight multipart `files` parts with the required official filenames. A new validated bundle returns HTTP 201 with `instance_id`, `revision_id`, `fingerprint`, `validation_status`, `duplicate: false`, and `entity_counts`. An identical bundle, including the startup bundle, returns HTTP 409 with `detail.message`, `detail.instance_id`, `detail.revision_id`, and `detail.fingerprint`. Invalid or incomplete bundles return HTTP 422. Rejected uploads make no database, audit, or stored-file changes. See [SQLite import and compatibility details](DATABASE.md).

`GET /instances/{id}` currently returns instance metadata and revisions. `POST /solve` returns HTTP 202 with the queued run ID, instance/revision IDs, scenario, status, and creation time. Progress and results retain their existing persisted response fields. All routes retain the existing authentication dependency. The legacy router remains unavailable because of the pre-existing deleted `backend.app.models` dependency; its documented contracts below are historical.

## PS1 and Operational Endpoints

| Status | Method and route | Purpose | Payload / response summary |
|---|---|---|---|
| Implemented | `POST /api/ps1/instances/upload` | Upload exactly 8 official CSV files | Multipart official files; returns instance/revision/fingerprint and entity counts. |
| Implemented | `GET /api/ps1/instances/{id}` | Inspect instance metadata and revisions | Returns stored immutable revisions; entity counts come from the uploaded instance, not hardcoded public counts. |
| Implemented queue contract | `POST /api/ps1/solve` | Queue one A/B/C weekly solve | Current fields plus target `run_mode`, `enrichment_revision_id?`, `baseline_run_id?` and `as_of?`; returns run and revision IDs. |
| Implemented | `GET /api/ps1/runs/{id}/progress` | Read solver phase/progress | Status, phase, elapsed time, complete-workload flag and incumbent score. |
| Implemented | `GET /api/ps1/runs/{id}/results` | Read stored weekly results | Typed access/occupancy/results plus target operational summaries where applicable. |
| Planned | `GET /api/ps1/runs/{id}/export/{filename}` | Download an exact official artifact | Reject unless `official_export_eligible=true`; filename is one of the exact three official names. |
| Planned | `POST /api/ps1/enrichments` | Create a versioned operational input | Calendar, recurrence policies and ad-hoc/emergency jobs; returns enrichment revision and validation. |
| Planned | `POST /api/ps1/runs/{id}/calendarize` | Assign exact global nights | Calendar revision and pins; returns operational accesses with `service_date`, provenance and date-level validation. |
| Planned | `POST /api/ps1/replans` | Freeze history and solve a dynamic update | Baseline run/revisions, selected scenario, `as_of`, typed changes and optional score-degradation tolerance. |
| Planned | `GET /api/ps1/replans/{id}/diff` | Compare baseline and replan | Frozen/changed/unaffected/new accesses, scenario score delta, churn decomposition and causes. |
| Planned | `POST /api/ps1/runs/{id}/edits/preflight` | Validate a drag/move draft | Access ID, proposed week/date/pin and revision; returns structured hard conflicts, warnings and score/churn delta without mutation. |
| Planned | `POST /api/ps1/runs/{id}/edits/repair` | Pin an accepted edit and replan movable work | Same draft plus solve budget; returns a new run or evidence of no complete solution. |
| Implemented | `GET /api/ps1/runs/{id}/explanations/{activity_id}` | Build deterministic explanation facts | Placement/diff/constraint/counterfactual fact pack and simple fallback summary. |
| Implemented | `POST /api/ps1/chat` | Ask a schedule-grounded question | Run/instance scope, question and optional selected activity; uses allowlisted read-only tools and returns citations/provenance. |

---

### Official Result Payload Schema (`GET /api/ps1/runs/{id}/results`)

```json
{
  "run_id": "run-ps1-20260918-01",
  "instance_id": "inst-public-01",
  "instance_revision_id": "rev-official-01",
  "enrichment_revision_id": null,
  "run_mode": "competition",
  "scenario": "A",
  "solver_status": "FEASIBLE",
  "elapsed_seconds": 12.4,
  "workload_complete": true,
  "workload_summary": {
    "total_activities": 54,
    "fully_scheduled": 54,
    "total_workload_required": 192,
    "total_yield_delivered": 192
  },
  "score": {
    "scenario_objective": 48.3,
    "score_provenance": "local_reconstruction",
    "components": {
      "P_activity_overrun_penalty": 48.3,
      "V_location_excess_slots": 0,
      "E_eclo_access_count": 0
    },
    "contract_overrun_days": 28,
    "contracts_overrunning": 3
  },
  "eclo_windows": {
    "ALP": {"start_week": null, "end_week": null},
    "BET": {"start_week": null, "end_week": null}
  },
  "validation": {
    "provenance": "validator_unavailable",
    "local_checks_passed": true,
    "rule_results": {
      "full_workload": "PASS",
      "access_yield": "PASS",
      "one_access_per_activity_week": "PASS",
      "planned_start": "PASS",
      "precedence": "PASS",
      "core_occupancy": "PASS",
      "legal_possession_mix": "PASS",
      "possession_capacity": "PASS",
      "buffers_and_live_mirroring": "UNVERIFIED",
      "contract_weekly_caps": "PASS",
      "contract_workfronts": "PASS",
      "scenario_policy": "PASS"
    }
  },
  "official_export_eligible": true,
  "operational": null,
  "artifacts": [
    "/api/ps1/runs/run-ps1-20260918-01/export/SCHEDULE_ACCESS.csv",
    "/api/ps1/runs/run-ps1-20260918-01/export/SCHEDULE_OCCUPANCY.csv",
    "/api/ps1/runs/run-ps1-20260918-01/export/RESULTS.csv"
  ]
}
```

---

### Official Scenario CSV Export Columns

1. **`SCHEDULE_ACCESS.csv`:**
   `activity_id,access_seq,week,eclo,access_night`
2. **`SCHEDULE_OCCUPANCY.csv`:**
   `activity_id,week,location_id,co_share_group`
3. **`RESULTS.csv`:**
   `scenario,contract_number,simulated_completion_date,overrun_days`

*Rules:*
- Exact column headers, no extra or missing columns.
- `RESULTS.csv` contains only rows for the single evaluated scenario.
- Date mapping: `completion_date(w) = horizon_start + (7w - 1) days`.
- Generated recurring/emergency IDs and operational fields such as `service_date` are forbidden in an official bundle.

### Operational Contract Rules

- An enrichment revision is immutable and references one official instance revision. Calendar rows carry `service_date`, `global_night_id`, timezone, eligibility/capacity and provenance; recurrence policies carry composite asset keys, `max_interval_days`, last completion and a complete job template.
- An operational access retains the official `week`, `eclo`, `access_night` and occupancy rows, and separately adds a persistent internal `access_id`, `service_date`, `global_night_id`, `source`, lock/state and validation provenance. `access_night` is never parsed as a weekday.
- A replan request includes the baseline run, both revision tokens, selected scenario, `as_of`, typed changes with effective times and optional non-negative scenario-score tolerance. The default tolerance is zero. Completed/occurred, in-progress and locked accesses are immutable; amendments constrain only the remaining horizon.
- Replan results report the selected scenario score before/after and a separate churn object: changed/unaffected/new counts, week/date moves, absolute day displacement, ECLO flips and material sharing changes. Label-only changes cost zero.
- Manual preflight never writes. Each conflict includes `severity`, stable `rule_code`, `activity_ids`, `service_dates`, `location_ids`, `capacity_delta`, `message` and optional alternatives. Save and repair require the same current revision and repeat complete validation.
- Explanation responses include a deterministic fact pack and fallback summary even when no language-model provider is configured. Chat responses include cited run/activity/location IDs, tool/provenance metadata and an uncertainty field. Chat tools are read-only and caller-scoped.
- Operational infeasibility returns no newly published plan. The last validated publication remains current.

---

# Part 2: Legacy Transition API Contract (`/api`)

The legacy `/api/...` endpoints are retained to support existing prototype UI components and historical integration tests during transition. They model a synthetic, single-night formulation (`constraints_lp_setup.md`).

## Legacy Routes

| Method and route | Role | Legacy Purpose |
|---|---|---|
| `GET /health` | Public | Basic server readiness |
| `GET /config` | Public | Auth mode, engine name and intentionally public Auth configuration |
| `GET /me` | Signed in | Backend-assigned identity and role |
| `GET /planning-snapshot` | Signed in | Legacy single-night snapshot data (`backend/app/models.py`) |
| `POST /requests` | Requester | Create synthetic single-night request |
| `POST /requests/{id}/cancel` | Owning requester | Withdraw an unbooked synthetic request |
| `PATCH /requests/approval` | Officer | Mass approve or return unscheduled requests |
| `PATCH /allocations/locks` | Officer | Persistently lock or unlock published schedule allocations |
| `POST /conflicts/check` | Officer | Check synthetic single-night conflict rules |
| `POST /schedule/check` | Officer | Validate positions from the manual scheduling board |
| `POST /schedule/proposals` | Officer | Run legacy CP-SAT single-night solver (`backend/app/services/cp_sat.py`) |
| `POST /schedule/manual-proposals` | Officer | Independently check and stage manual plan |
| `GET /proposals` | Officer | Last ten stored feasible proposals |
| `POST /proposals/{id}/commit` | Officer | Atomically approve and publish versioned proposal |
| `PATCH /resources` | Officer | Add an unavailable interval or change equipment serviceability |
| `GET /audit` | Officer | Recent local audit events |
| `POST /demo/reset` | Demo officer only | Destructively reload synthetic seed data |

---

## Grounded Chat & Explanations Contracts

### Explanation Fact Pack (`GET /api/ps1/runs/{run_id}/explanations/{activity_id}`)

Query parameters: `baseline_run_id` (optional). Returns deterministic fact pack and fallback summary:

```json
{
  "fact_pack": {
    "fact_pack_id": "efp-1234abcd",
    "generated_at": "2026-09-19T05:50:00Z",
    "scope": {
      "instance_id": "inst-...",
      "instance_revision_id": "rev-...",
      "run_id": "run-...",
      "baseline_run_id": "run-base...",
      "scenario": "A",
      "data_source": "solver"
    },
    "activity": {
      "activity_id": "A017",
      "contract_number": "C003",
      "activity_type": "C",
      "priority": 1,
      "planned_start_date": "2027-04-26",
      "predecessor_activity_id": null,
      "required_accesses": 2
    },
    "baseline": { "available": true, "placements": [] },
    "current": { "available": true, "placements": [] },
    "diff": { "changed": true, "week_displacement": 2, "date_displacement_days": null, "eclo_changed": false },
    "frozen_state": { "is_frozen": false, "reason": null },
    "score": { "available": true, "baseline": {}, "current": {}, "delta": {} },
    "binding_constraints": [],
    "conflicts": [],
    "counterfactuals": [],
    "availability": {
      "official_validator": false,
      "counterfactuals": true,
      "replan_diff": true,
      "baseline_available": true,
      "cause_recorded": true,
      "mock_data": false
    },
    "evidence": [],
    "fallback_summary": "..."
  },
  "fallback_summary": "...",
  "provenance": {
    "provider": "nebula-x-deterministic",
    "model": "efb-v1.0",
    "prompt_template_version": "schedule-explainer-v1",
    "instance_revision_id": "rev-...",
    "run_id": "run-...",
    "baseline_run_id": "run-base..."
  }
}
```

### Schedule Chat Turn (`POST /api/ps1/chat`)

Request body:

```json
{
  "session_id": "chat-1234abcd",
  "instance_id": "inst-...",
  "run_id": "run-...",
  "baseline_run_id": "run-base...",
  "question": "Why was A017 moved?",
  "selected_activity_id": "A017",
  "selected_location_id": "SEC:BET:S15_S16",
  "selected_week": 19
}
```

Response body:

```json
{
  "session_id": "chat-1234abcd",
  "answer": "A017 was displaced from week 17 to week 19...",
  "response_mode": "gemini",
  "fact_pack_id": "efp-1234abcd",
  "citations": [
    {
      "evidence_id": "activity:A017",
      "classification": "stored_fact",
      "entity_type": "activity",
      "entity_id": "A017",
      "description": "Activity A017 belongs to contract C003."
    }
  ],
  "uncertainty": [],
  "provenance": {
    "provider": "google",
    "model": "gemini-3.6-flash",
    "prompt_template_version": "schedule-explainer-v1",
    "instance_revision_id": "rev-...",
    "run_id": "run-...",
    "baseline_run_id": "run-base..."
  },
  "tools_used": ["get_activity_diff", "get_run_conflicts"]
}
```

---

## Error Handling

Standard HTTP status codes are used:
- `400`: Invalid request payload or missing parameters.
- `401`: Missing or invalid authentication token.
- `403`: Role not authorised to perform this operation.
- `404`: Requested resource, instance, run, or export not found.
- `409`: Stale revision or concurrency conflict.
- `422`: Schema or parameter domain validation failure.
- `503`: Database or solver engine unavailable.
