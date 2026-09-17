# NebulaX API Contract

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This document specifies the HTTP API contracts for NebulaX.
> Per [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), the **Problem Statement 1 (PS1) Official Adoption Plan** acts as the single authoritative source of truth.
>
> NebulaX provides two API layers:
> 1. **Official PS1 API (`/api/ps1/...`):** Authoritative contract for Problem Statement 1 (instance upload, scenario solve, status progress, exports, and disruption replanning).
> 2. **Legacy Transition API (`/api/...`):** Preserved during transition to support existing synthetic prototype frontend components and historical integration tests.

---

# Part 1: Official PS1 API Contract (`/api/ps1`)

Base path: `/api/ps1`. Supports the official PS1 workflow for unseen eight-file instance evaluation, multi-week solving, official metric reporting, and export generation.

## Official PS1 Endpoints

| Method and Route | Purpose | Payload / Parameters | Response |
|---|---|---|---|
| `POST /api/ps1/instances/upload` | Upload 8 official CSV files for an instance | `multipart/form-data` with files `01_LINES.csv` through `08_ACTIVITY_DETAILS.csv` | `{ instance_id, fingerprint, filename_status, entity_counts, validation_summary }` |
| `GET /api/ps1/instances/{id}` | Inspect uploaded instance topology, contracts, and workload | Query parameters | Instance metadata, 54 activities, 14 contracts, 76 locations, 30 weeks |
| `POST /api/ps1/solve` | Trigger CP-SAT solver for a scenario | `{ instance_id, scenario: "A"|"B"|"C", time_limit_seconds, baseline_run_id?, disruption? }` | `{ run_id, instance_id, scenario, status: "QUEUED"|"RUNNING", created_at }` |
| `GET /api/ps1/runs/{id}/progress` | Real-time solver phase & progress | None | `{ run_id, phase: "FEASIBILITY"|"OPTIMISATION", elapsed_seconds, solver_status, workload_complete: boolean, incumbent_score: float }` |
| `GET /api/ps1/runs/{id}/results` | Complete scenario results and score breakdown | None | Full result payload (see schema below) |
| `GET /api/ps1/runs/{id}/export/{filename}` | Download exact official CSV artifact | `filename`: `SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, or `RESULTS.csv` | CSV text file with exact official columns |
| `POST /api/ps1/replan/diff` | Compare baseline vs disrupted replan | `{ baseline_run_id, replan_run_id }` | Changed accesses, weeks, ECLO, affected locations, score before/after, binding causes |

---

### Official Result Payload Schema (`GET /api/ps1/runs/{id}/results`)

```json
{
  "run_id": "run-ps1-20260918-01",
  "instance_id": "inst-public-01",
  "scenario": "A",
  "solver_status": "OPTIMAL",
  "elapsed_seconds": 12.4,
  "workload_complete": true,
  "workload_summary": {
    "total_activities": 54,
    "fully_scheduled": 54,
    "total_workload_required": 192,
    "total_yield_delivered": 192
  },
  "score": {
    "official_penalty": 25.2,
    "components": {
      "P_activity_overrun_penalty": 25.2,
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
      "buffers_and_live_mirroring": "PASS",
      "contract_weekly_caps": "PASS",
      "contract_workfronts": "PASS",
      "scenario_policy": "PASS"
    }
  },
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

## Error Handling

Standard HTTP status codes are used:
- `400`: Invalid request payload or missing parameters.
- `401`: Missing or invalid authentication token.
- `403`: Role not authorised to perform this operation.
- `404`: Requested resource, instance, run, or export not found.
- `409`: Stale revision or concurrency conflict.
- `422`: Schema or parameter domain validation failure.
- `503`: Database or solver engine unavailable.

