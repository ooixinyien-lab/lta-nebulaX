# NebulaX — PS1 Official Rail Maintenance Scheduling System

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This repository is adopting the official **Problem Statement 1 (PS1)** challenge requirements.
> [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) acts as the **single authoritative source of truth** for all optimisation, data, backend, and API specifications.
>
> **Core Strategy:** Keep NebulaX's robust application infrastructure (FastAPI, identity/role auth, transaction/audit controls) and replace the legacy synthetic, single-night scheduling model with the official PS1 model of multi-week accesses (30-week horizon), location possessions, and 100% complete activity workloads across Scenarios A, B, and C.
>
> The legacy single-night CP-SAT solver (`cp_sat.py`), synthetic validator (`full_validator.py`), and `constraints_lp_setup.md` are **retired from the official PS1 path** and retained solely as historical learning and scaffolding artifacts.

**Target:** First place in PS1.  
**Order of Priorities:**
1. Schedule every activity's full workload (100% complete, mandatory).
2. Satisfy every official hard rule.
3. Minimise the official penalty on hidden instances.
4. Handle Scenarios A, B, and C correctly.
5. Solve reliably within a bounded runtime.
6. Deliver exact global-night dispatch, recurring maintenance, low-churn dynamic replanning, safe manual edits, and grounded chatbot explanations.

---

## Overview: Transition from Legacy Prototype to Official PS1

NebulaX originally provided a runnable synthetic maintenance-scheduling prototype with a requester portal, an officer workspace, and a single-night CP-SAT solver. As detailed in [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md), the repository is transitioning to the official PS1 domain:

| Dimension | Legacy Synthetic Prototype (Retired from PS1 path) | Official PS1 Architecture (Authoritative) |
|---|---|---|
| **Horizon** | Single engineering night (minute-level grid) | 30-week planning horizon (`W = 1..30`) |
| **Decisions** | Minute timestamps, engineer assignments, equipment | Weekly accesses (`x_iw`), ECLO (`e_iw`), local night (`z_iwn`), possession groups (`y_iwlg`) |
| **Workload** | Dropping/deferring jobs permitted (e.g. 7 of 12 scheduled) | **100% complete workload mandatory** (`sum_w(2*x_iw + e_iw) >= 2*d_i`) |
| **Resources** | Synthetic technicians, named engineers, vehicles | Contract weekly caps ($K_c$), workfronts ($f_c$), location possession capacity ($s_lw$) |
| **Scenarios** | Single strict vs recovery mode | **Scenarios A (strict supply), B (strict dates), C (balanced)** |
| **Inputs** | `comprehensive_synthetic_data.json` | **8 Official CSVs** (`01_LINES.csv` ... `08_ACTIVITY_DETAILS.csv`) |
| **Exports** | SQLite database rows / JSON API | **3 Official CSVs** (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`) |
| **Solver Path** | `backend/app/services/cp_sat.py` (Historical) | Canonical data in `domain_models.py`/`io.py`/`topology.py`; solver, scoring, validation and artifacts in `backend/app/ps1/` |
| **Operational Detail** | Synthetic minute timestamps | Separate exact-date calendarisation, recurrence and replan layers; never infer weekdays from official `access_night` |

---

## Start here

The existing web UI demonstrates the application infrastructure:
**One website. One login system. Two roles.**

- A **requester** submits work and sees their own requests/bookings.
- An **officer** sees all requests, checks conflicts, generates a proposal, and approves/publishes it.

The API enforces these permissions; hiding a button is not the permission check. In local demo mode the identities are deliberately simulated, so anyone with local access can select the officer. Do not expose demo mode publicly.

New UI work belongs in **`nebula-ui/` (React + Vite)**. The legacy `frontend/` is still served at `/` during transition; do not add the new scheduling workflow there. FastAPI owns all scheduling, validation, conflict and explanation facts.

## 1. Run it on your laptop

Use **Python 3.12** for the most straightforward team setup. The build environment used Python 3.13.5; this repository has not been verified on every Python/OS combination.

Open the **NebulaX repository** in VS Code, then open its terminal. The terminal's current directory must contain this README and `requirements.txt`.

### macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-cpsat.txt
cp .env.example .env
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cpsat.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** in your browser. Interactive backend API documentation is at **http://127.0.0.1:8000/docs**.

Startup creates or safely upgrades one local SQLite database at `DATABASE_PATH` (default `backend/nebulax.sqlite3`) and validates/imports all eight official CSVs from `OFFICIAL_DATA_PATH` (default `data`). Matching bundles are reused; changed bundles create new snapshots without resetting runs or plans. Missing or invalid required CSVs stop startup with an error. Python's built-in `sqlite3` is the only database runtime; no database server or migration command is required. See [persistence and compatibility](docs/DATABASE.md).

Synthetic JSON is not loaded during PS1 startup. The legacy API currently cannot import the deleted `backend.app.models` module, a limitation already present at compatibility baseline `c156c5a`. Startup logs this limitation and serves the separate PS1 API. The legacy workflow below is historical, not a working fresh-start workflow.

Leave the terminal running while you use the app. Press `Ctrl+C` to stop it. After the first setup, run `sh scripts/dev.sh` on macOS/Linux or `./scripts/dev.ps1` in PowerShell.

For modern UI development, run Vite separately:

```sh
cd nebula-ui
npm install
npm run dev
```

Vite serves `http://127.0.0.1:5173` and proxies `/api` to FastAPI. For a production-style check, run `npm run build`; FastAPI serves the built app at `/network-map` when `nebula-ui/dist/` exists.

### Map fixed solver outputs to actual nights

The calendar layer reads an existing `SCHEDULE_ACCESS.csv`,
`SCHEDULE_OCCUPANCY.csv` and `RESULTS.csv` together with their matching official
instance revision. It stores the original bytes unchanged and writes exact
`service_date` values to separate operational records.

1. Start FastAPI and the Vite UI as above, then open
   `http://localhost:5173/calendar` or choose **Actual Night Preview**.
2. The page restores the latest imported solver output, its matching instance,
   the calendar used for its last attempt, and any previous valid date mapping.
   On a first visit without an imported output, select the three output CSVs;
   the instance revision is filled from the stored instance.
3. Choose **Show calendar**. The web app imports any selected files, creates the
   clearly labelled assumed demo calendar when needed, and starts date assignment
   automatically. No separate worker terminal is required.

**Advanced setup** contains source/revision overrides and optional calendar JSON
import using [`docs/examples/operating_calendar.json`](docs/examples/operating_calendar.json).
Refreshing the page restores stored results; it does not rerun the solver.
The read-only week view appears only when every fixed source access receives a
validated date. Otherwise the page displays the returned conflicts.

For standalone queue processing or recovery after an interrupted server process,
the optional worker remains available as
`python -m backend.app.ps1.calendar_worker --once`. A fixed weekly schedule can
be impossible under a selected operating calendar; the API then returns
conflicts and leaves all official rows and files unchanged. `access_night`
remains a local contract index and is displayed separately from the weekday.

## 2. Historical legacy synthetic workflow

This sequence documents the retired prototype and is not a runnable current-main walkthrough while `backend.app.models` is absent:

1. Choose **Planning officer**. A fresh canonical database contains the 12 comprehensive synthetic requests.
2. Click **Generate proposal**. The legacy full solver first attempts a complete strict schedule, then runs recovery only if strict infeasibility is proved.
3. Review the returned status, scheduled work and clearly separated deferred requests. The canonical 14 September night proves strict infeasibility and returns an independently validated seven-request recovery plan.
   *(Note: As established in [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md), deferring 5 of 12 requests violates the official PS1 complete-workload baseline, which mandates scheduling 100% of all activities across the multi-week horizon).*
4. Click **Approve & publish**, then accept the confirmation. The server rechecks the current revision and writes all bookings in a transaction.
5. Sign out. Choose **Track team**. The requester sees only that team's requests and its newly scheduled work.
6. Choose **New request**, submit a work package, and refresh.

The canonical fixture covers **14-15 September 2026** for the legacy synthetic demonstration.

## 3. Team ownership and milestones (per PS1 Adoption Plan)

Per [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md), implementation is organised around three sequential milestones and shared ownership:

| Workstream | Main files | Ownership and responsibilities |
|---|---|---|
| **Data / I/O** | `backend/app/domain_models.py`, `backend/app/io.py`, `backend/app/topology.py`, official CSV inputs | Parse all 8 official CSVs, preserve IDs, composite-key topology, core and buffer footprints, export CSV round-trips. |
| **Optimisation** | `backend/app/ps1/solver.py`, `validation.py` | CP-SAT multi-week/possession/workload model, mandatory 100% workload yield, Scenarios A/B/C constraints, exact penalty objectives. |
| **Backend / API** | `backend/app/ps1/models.py`, `artifacts.py`, `backend/app/api/ps1_routes.py`, `backend/app/db/` | Instance upload, run execution, scenario result storage, official 3-CSV export endpoints, transaction/audit integrity. |
| **Operational Workflow** | Planned modules under `backend/app/ps1/` | Exact-date calendarisation, recurrence generation, emergency input, lexicographic churn and manual-edit preflight. |
| **Frontend / Explanation** | `nebula-ui/`, presentation materials | Operational schedule UI, scenario comparison, drag/move drafts, structured conflicts, grounded chatbot and demo. |

### Adoption Milestones:
1. **Milestone 1: Official Correctness** — 8 CSV parsing, complete-workload A/B/C solving, exact 3 CSV exports (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`), zero official hard violations.
2. **Milestone 2: Competitive Optimisation** — Exact penalty optimisation, greedy seeds/hints, symmetry breaking, and targeted LNS reoptimisation.
3. **Milestone 3: Hidden-Instance Hardening** — Bounded runtimes, upload/run isolation, failure handling, disruption replanning demonstrations, and official submission packaging.
4. **Milestone 4: Operational Scheduling** — Exact global nights, recurring jobs, emergency updates, frozen history, and scenario-first/minimum-churn replanning.
5. **Milestone 5: Decision Support** — Transactional manual-move validation/repair and grounded schedule explanations/chat.

Read [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) and [docs/TEAM_WORK.md](docs/TEAM_WORK.md) for full task definitions.

## 4. Architecture and execution paths

```text
Browser: nebula-ui/ (canonical) or frontend/ (legacy transition)
       |
       | authenticated HTTP requests
       v
FastAPI: backend/app/api/ps1_routes.py
       |
       +--> domain_models.py + io.py + topology.py
       |      official 8-CSV model and geometry
       +--> ps1/solver.py + scoring.py + validation.py + artifacts.py
       |      shared weekly A/B/C solve and exact official exports
       +--> db/
       |      immutable instances, revisions, runs, results and audit
       +--> planned operational workflow
              recurrence generation -> weekly solve -> calendarisation
              -> date validation -> replan/manual repair -> explanation facts

Legacy api/routes.py and services/* remain isolated historical scaffolding.
```

## 5. Folder map

```text
nebulaX/
  PS1_OFFICIAL_ADOPTION_PLAN.md  Authoritative source of truth for PS1
  README.md                      Architecture and adoption guide
  constraints_lp_setup.md        Retired as PS1 authority; legacy synthetic reference
  requirements.txt               Core application dependencies
  requirements-cpsat.txt         Core dependencies plus OR-Tools
  requirements-dev.txt           Backend tests including CP-SAT tests
  backend/
    app/
      main.py                    FastAPI app, routes, static file serving
      config.py                  Application configuration
      database.py                SQLite persistence, transaction & audit logging
      auth/                      Identity and server-enforced role verification
      domain_models.py           Canonical official PS1 types
      io.py                      8-CSV loader and exact 3-CSV writer
      topology.py                Footprint, buffer, mirrored closure & interchange logic
      ps1/                       Official solver and planned workflow package
        models.py                Solver/result/status schemas
        solver.py                Official CP-SAT weekly access & possession solver
        scoring.py               Independent score reconstruction
        validation.py            Independent adopted-rule checks
        artifacts.py             Strict official artifact readers/round trips
      db/                        PS1 SQLite records and repositories
      api/
        routes.py                Legacy synthetic API routes (transition contract)
        ps1_routes.py            [NEW] Official PS1 instance, solve & export endpoints
      services/
        cp_sat.py                Legacy single-night CP-SAT solver (RETIRED from PS1 path)
        full_validator.py        Legacy single-night validator (RETIRED from PS1 path)
        scheduler.py             Solver dispatch interface
        checker.py               Legacy conflict evaluation
    tests/                       Automated tests (unit, integration, legacy regression)
  data/                          Historical synthetic datasets and learning scripts
  docs/                          Technical contracts, solver guides, and team notes
  nebula-ui/                     Canonical React/Vite frontend
  frontend/                      Legacy vanilla-JS transition workspace
```

## 6. Solver execution

### Official PS1 Solver
The official solver executes against the 8 official CSV files for Scenarios A, B, and C, requiring 100% activity workload satisfaction across the 30-week horizon:

```sh
python -m backend.app.ps1 --data-dir data --scenario all --output-dir outputs --time-limit 60
```

See [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) and [docs/SOLVER.md](docs/SOLVER.md) for execution details and validation limitations.

### Operational workflow roadmap

The official weekly result is the foundation, not a claim about a physical weekday. The required operational pipeline will:

1. generate mandatory jobs from explicit station/sector recurrence policies;
2. solve all official and operational work under one selected A/B/C policy;
3. map weekly accesses to exact Singapore service dates with a separate calendar solver;
4. freeze occurred work and replan dynamic/emergency changes with scenario score first and churn second;
5. validate drag/move drafts server-side and optionally repair the remaining schedule; and
6. explain displacement and answer schedule questions from structured read-only facts.

Operational fields and generated IDs never appear in an official three-CSV bundle. The legacy single-night solver remains historical and may not import while its deleted domain module is absent.

## 7. Identity and auth

NebulaX includes role-based identity supporting simulated local demo identities and optional real Supabase Auth. Identity enforcement is server-owned and independent of the scheduling domain model. See [docs/SUPABASE.md](docs/SUPABASE.md).

## 8. Current scope: Legacy prototype vs PS1 official adoption

**Legacy Synthetic Prototype (Implemented & Executed Locally):**
- FastAPI infrastructure, session-based role checks, atomic SQLite transactions with revision counters and audit logging.
- Interactive single-night scheduling UI with five-minute grid, drag-and-drop, and conflict preview.
- Single-night synthetic CP-SAT solver and 9-rule validator based on `constraints_lp_setup.md`.
- *Limitation:* Deferring requests in recovery violates PS1's mandatory full-workload requirement.

**PS1 Official Adoption (In Progress per PS1_OFFICIAL_ADOPTION_PLAN.md):**
- **Authoritative specification:** [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) and official PS1 README.
- **Problem formulation:** Multi-week planning horizon (30 weeks), weekly accesses, location possession groups (`co_share_group`), contract weekly caps ($K_c$), workfronts ($f_c$).
- **Workload:** 100% complete workload mandatory (`sum_w(2*x_iw + e_iw) >= 2*d_i`) for all 54 activities. No dropped or truncated activities.
- **Scenarios:** Strict supply (A), Strict schedule with flexible supply & ECLO (B), Balanced with ECLO windows and max 1 excess slot/loc-week (C).
- **Deliverables:** 3 official CSV bundles per scenario (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`), disruption replan demonstration, hosted application, and submission video.

**Required Operational Enrichments (Planned):**

- A calendarisation solver assigns `service_date`/`global_night_id`; `access_night` remains a local weekly index, not a weekday.
- Explicit recurrence policies generate mandatory station/sector jobs without double-counting supply reductions.
- Emergency/ad-hoc replans freeze occurred, in-progress and locked work, then optimise each selected scenario objective before minimum churn.
- Manual drag/move creates a draft and structured backend conflict preflight; publication revalidates transactionally.
- A grounded chatbot explains displaced work and supports general schedule questions through scoped read-only tools; it cannot validate or publish plans.

## 9. Test it

```sh
python -m pip install -r requirements-dev.txt
python -m pytest backend/tests/test_data_layer.py backend/tests/test_ps1_scoring_validation.py backend/tests/test_ps1_solver.py -q
```

`requirements-dev.txt` includes OR-Tools and pytest. Avoid bare `pytest` while obsolete legacy tests still import the deleted `backend.app.models` module.

Optional JavaScript syntax check (requires Node, not needed to run the app):

```sh
node scripts/check-js.mjs
```

See [docs/TEST_REPORT.md](docs/TEST_REPORT.md) for what was actually tested before delivery, and [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for a repeatable walkthrough.

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| `No module named backend` | Run commands from the repository root, not from inside `backend/`. |
| `No module named uvicorn` | Use the `.venv` interpreter and install `requirements-cpsat.txt`. |
| Browser cannot connect | FastAPI/legacy UI uses `http://127.0.0.1:8000`; Vite development uses `http://127.0.0.1:5173` with FastAPI also running. |
| Solver says `UNAVAILABLE` | Install `requirements-cpsat.txt`, or explicitly select `demo_search` for the tiny fixture. |
| Solver says `INPUT_ERROR` | Read the field/request identifier in the message; canonical data is validated before model construction. |
| Supabase requester sees no seed jobs | Seed jobs belong to fictional demo owners. A real requester starts by submitting their own job. Officers see all seed jobs. |
| Editing generated JSON is overwritten | Change `scripts/generate_synthetic_dataset.py`, then regenerate `data/comprehensive_synthetic_data.json`. |
| Existing app still shows starter data | Use the new `backend/nebulax.sqlite3` path or officer reset. Reset deletes local edits and proposals. |
| Old proposal cannot publish | A request, resource or booking changed. Generate a fresh proposal. |
| Resource outage makes planning impossible | A locked booking may now be invalid. The starter will not silently move it. |
| Sign-in disappears on refresh in Supabase mode | Tokens are intentionally memory-only in this basic adapter; sign in again. |

## 11. Safety and data boundaries

Everything in `data/` is synthetic. No actual LTA, SMRT or SBS Transit records are included. This app neither grants track access nor controls power. A model-feasible plan is not a verified safe operational plan.

The `.gitignore` excludes credentials, environments, local database files and caches. Do not add them to Git manually. The source has no service-role key, live credentials or installed dependency folders.

Supporting software references and the distinction from the earlier blueprint are in [docs/REFERENCES.md](docs/REFERENCES.md).
