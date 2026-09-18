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
6. Demonstrate useful explanations and disruption replanning.

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
| **Solver Path** | `backend/app/services/cp_sat.py` (Historical) | `backend/app/ps1/` (`models.py`, `io.py`, `solver.py`, `validation.py`, `export.py`) |

---

## Start here (Legacy Prototype UI)

The existing web UI demonstrates the application infrastructure:
**One website. One login system. Two roles.**

- A **requester** submits work and sees their own requests/bookings.
- An **officer** sees all requests, checks conflicts, generates a proposal, and approves/publishes it.

The API enforces these permissions; hiding a button is not the permission check. In local demo mode the identities are deliberately simulated, so anyone with local access can select the officer. Do not expose demo mode publicly.

The full-stack scaffolding uses **plain HTML, CSS and native JavaScript modules**, served by FastAPI without requiring Node or npm build servers. The official PS1 upload/solve/export contract will be integrated alongside this infrastructure.

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

**Do not run `npm run dev`: this version has no frontend build server.** The small `frontend/package.json` only supports optional JavaScript syntax checking.

## 2. Try the legacy synthetic workflow

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
| **Data / I/O** | `backend/app/ps1/io.py`, `topology.py`, official CSV inputs | Parse all 8 official CSVs, preserve IDs, composite-key topology, core and buffer footprints, export CSV round-trips. |
| **Optimisation** | `backend/app/ps1/solver.py`, `validation.py` | CP-SAT multi-week/possession/workload model, mandatory 100% workload yield, Scenarios A/B/C constraints, exact penalty objectives. |
| **Backend / API** | `backend/app/ps1/models.py`, `export.py`, `backend/app/api/ps1_routes.py`, `database.py` | Instance upload, run execution, scenario result storage, official 3-CSV export endpoints, transaction/audit integrity. |
| **Frontend / Presentation** | `frontend/`, presentation materials | Instance upload UI, scenario A/B/C comparison, disruption replan visualisation, 3-minute video and slide deck. |

### Adoption Milestones:
1. **Milestone 1: Official Correctness** — 8 CSV parsing, complete-workload A/B/C solving, exact 3 CSV exports (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`), zero official hard violations.
2. **Milestone 2: Competitive Optimisation** — Exact penalty optimisation, greedy seeds/hints, symmetry breaking, and targeted LNS reoptimisation.
3. **Milestone 3: Hidden-Instance Hardening** — Bounded runtimes, upload/run isolation, failure handling, disruption replanning demonstrations, and official submission packaging.

Read [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) and [docs/TEAM_WORK.md](docs/TEAM_WORK.md) for full task definitions.

## 4. Architecture and execution paths

```text
Browser: frontend/
  login -> requester OR officer pages
       |
       | HTTP requests to /api/...
       v
FastAPI: backend/app/
  +--> api/ps1_routes.py [OFFICIAL PS1 PATH - In Adoption]
  |      |
  |      +--> ps1/io.py: parses 8 official CSVs
  |      +--> ps1/topology.py: core, buffer, mirror & interchange footprints
  |      +--> ps1/solver.py: CP-SAT multi-week & possession packing solver
  |      +--> ps1/validation.py: independent PS1 verification
  |      +--> ps1/export.py: exports 3 scenario CSV bundles
  |
  +--> api/routes.py [LEGACY SYNTHETIC PATH - Scaffolding Only]
         |
         +--> database.py: SQLite records and revision numbers
         +--> services/checker.py: legacy synthetic conflict rules
         +--> services/cp_sat.py: legacy single-night solver (RETIRED from PS1 path)
         +--> services/full_validator.py: legacy 9-rule validator
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
      ps1/                       [NEW] Official PS1 implementation package
        models.py                Official PS1 domain entities & scenario schemas
        io.py                    8-CSV loader, schema validation & normalisation
        topology.py              Footprint, buffer, mirrored closure & interchange logic
        solver.py                Official CP-SAT weekly access & possession solver
        validation.py            Independent rule checking & official-validator adapter
        export.py                Official 3-file CSV exporter & results calculator
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
```

## 6. Solver execution

### Official PS1 Solver
The official solver executes against the 8 official CSV files for Scenarios A, B, and C, ensuring 100% activity workload satisfaction across the 30-week horizon. See [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) and [docs/SOLVER.md](docs/SOLVER.md) for execution details.

### Legacy Single-Night Synthetic Solver (Scaffolding Reference)
From your activated environment, you can run the historical synthetic solver:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8
```

For structured JSON output:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8 --json
```

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

## 9. Test it

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

For the complete suite, use `requirements-dev.txt`; it includes OR-Tools and pytest.

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
| Browser cannot connect | Keep the server terminal running and open `http://127.0.0.1:8000`, not port 5173. |
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
