# NebulaX railway engineering-work scheduler

**A runnable synthetic maintenance-scheduling prototype with a requester portal, an officer workspace and a canonical Google OR-Tools CP-SAT solver.** This is not a live railway product.

![Officer workspace](docs/screenshots/02-officer.png)

## Start here

**One website. One login system. Two roles.**

- A **requester** submits work and sees their own requests/bookings.
- An **officer** sees all requests, checks conflicts, generates a proposal, and approves/publishes it.

The API enforces these permissions; hiding a button is not the permission check. In local demo mode the identities are deliberately simulated, so anyone with local access can select the officer. Do not expose demo mode publicly.

### A deliberate simplification from the earlier blueprint

The earlier proposal used React/Vite. This starter instead uses **plain HTML, CSS and native JavaScript modules**, served by FastAPI. There is **no Node installation, npm install, frontend build step or second server required**. The frontend is still separated from the backend by HTTP APIs. Your frontend teammate can replace it with React later without replacing the solver or database.

The canonical solver is the **OR-Tools CP-SAT implementation**. The original small enumerative demo search remains as a scaffold and learning artifact. There is no silent fallback and no hard-coded schedule answer.

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

The database is created and seeded automatically on first startup. You do not need Supabase, an API key, a separate database server, or an LLM account for this local demo. Package installation does require an internet connection.

Leave the terminal running while you use the app. Press `Ctrl+C` to stop it. After the first setup, run `sh scripts/dev.sh` on macOS/Linux or `./scripts/dev.ps1` in PowerShell.

**Do not run `npm run dev`: this version has no frontend build server.** The small `frontend/package.json` only supports optional JavaScript syntax checking.

## 2. Try the whole workflow

1. Choose **Planning officer**. A fresh canonical database contains the 12 comprehensive synthetic requests.
2. Click **Generate proposal**. The full solver first attempts a complete strict schedule, then runs recovery only if strict infeasibility is proved. Nothing is booked yet.
3. Review the returned status, scheduled work and clearly separated deferred requests. The canonical 14 September night currently proves strict infeasibility and returns an independently validated seven-request recovery plan.
4. Click **Approve & publish**, then accept the confirmation. The server rechecks the current revision and writes all bookings in a transaction.
5. Sign out. Choose **Track team**. The requester sees only that team's requests and its newly scheduled work. Other teams' track occupation is shown only as `Reserved`.
6. Choose **New request**, submit a work package, and refresh. The request persists, but it does not become a track reservation until published by the officer.

For a second demonstration, generate a proposal and then change a resource's availability. The old proposal becomes stale and cannot be committed. If a required locked resource becomes invalid, the solver reports infeasibility or an input problem instead of silently changing the frozen booking.

The canonical fixture covers **14-15 September 2026**, not today's live railway calendar. Choose a seeded date in the UI.

## 3. Where your teammates work

| Workstream | Main files | What that person owns |
|---|---|---|
| Data / domain model | `backend/app/models.py`, `scripts/generate_synthetic_dataset.py`, `data/comprehensive_synthetic_data.json` | Typed Pydantic v2 domain models and generated canonical synthetic data |
| Requester frontend | `frontend/src/pages/requester.js` | Form, request list, status and validation presentation |
| Officer frontend | `frontend/src/pages/officer.js`, `frontend/src/components/` | Timeline, conflict panel, proposal review, resource UI |
| Backend / rules | `backend/app/api/routes.py`, `database.py`, `services/checker.py` | APIs, persistence, permissions at routes, conflict rules, atomic publication |
| Optimisation | `backend/app/services/cp_sat.py`, `candidates.py`, `scheduler.py` | CP-SAT decisions, constraints, objective, result checking and scalability |
| Identity / integration / QA | `backend/app/auth/`, `frontend/src/auth/`, `backend/tests/` | Optional Supabase, server-owned roles, integration tests and CI |

With four people, combine the two frontend streams. With three people, combine auth/integration with backend. Agree a named owner for shared contracts before parallel changes.

**Read [docs/TEAM_WORK.md](docs/TEAM_WORK.md) before splitting work.** It includes suggested first tasks, acceptance criteria and a Git workflow.

## 4. What runs where?

```text
Browser: frontend/
  login -> requester OR officer pages
       |
       | HTTP requests to /api/...
       v
FastAPI: backend/app/api/routes.py
  identity + role check -> input validation
       |
       +--> database.py: SQLite records and revision numbers
       |
       +--> checker.py: why a requested plan conflicts
       |
       +--> scheduler.py
               |
               +--> demo_search.py   starter learning solver
               OR
               +--> cp_sat.py        canonical OR-Tools implementation
                         |
                         v
                  full_validator.py: independent nine-rule validation
                         |
                         v
              proposal -> officer approval -> database commit
```

The frontend **does not** calculate authoritative scheduling rules or write the database. Supabase, when enabled, provides identity only; it does not run the optimisation or store this starter's planning tables.

## 5. Folder map

```text
nebulaX/
  README.md
  .env.example                 configuration template; not actual secrets
  requirements.txt             core application dependencies
  requirements-cpsat.txt       core dependencies plus OR-Tools
  requirements-dev.txt         backend tests including CP-SAT tests
  frontend/
    index.html
    styles.css
    src/
      app.js                   page orchestration and event bindings
      auth/session.js          demo identities / Supabase sign-in
      lib/api.js               all frontend HTTP calls
      lib/format.js            date formatting and HTML escaping
      pages/login.js
      pages/requester.js
      pages/officer.js
      components/timeline.js
      components/conflicts.js
      components/proposal.js
  backend/
    app/
      main.py                  FastAPI app and static website serving
      config.py                configuration and demo identities
      schemas.py               validated request shapes
      models.py                typed domain data classes (CP-SAT formulation, vehicles, blackouts, rules)
      database.py              SQLite repository
      auth/dependencies.py     verified identity and server-owned role
      api/routes.py            API endpoints
      services/
        common.py              simple shared time/record helpers
        checker.py             rule evaluation without solver/DB imports
        candidates.py          small finite candidate domains
        demo_search.py         explicit six-pending-job teaching solver
        cp_sat.py              canonical strict/recovery CP-SAT model
        full_validator.py      independent nine-constraint result validator
        scheduler.py           stable solver interface + output recheck
    tests/                     automated tests
  data/
    comprehensive_synthetic_data.json generated canonical mock inputs
    demo_data.json             outdated scaffold fixture retained for its tests
    solver_v0.py               basic time/window learning model
    solver_v1.py               V0 plus dependency and power learning model
    reference_expected_results.json   executed regression reference, never solver input
  docs/                        handoff, API, auth, solver and testing guides
  scripts/                     launch and optional browser-check utilities
  .github/workflows/tests.yml  CI configuration for your eventual GitHub repo
```

## 6. Run the canonical solver directly

From your activated environment:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8
```

For structured JSON output:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8 --json
```

The command requires an explicit planning night. The solver reports strict and recovery statuses separately, each lexicographic objective stage, independent validation, scheduled requests, deferred requests and prototype limitations.

Read [docs/SOLVER.md](docs/SOLVER.md) for the exact model and extension points.

## 7. Should we add Supabase now?

**Not necessary to split work or demonstrate locally.** Each teammate can use the demo profiles and their own database while building modules.

When you need actual shared accounts, enable the supplied Supabase adapter. You still have **one login page**, with two roles assigned by the backend. Users cannot promote themselves using a role dropdown or profile metadata.

Read [docs/SUPABASE.md](docs/SUPABASE.md). It covers project configuration, officer UUIDs and what is/is not protected. No Supabase database migration is required for the current Auth-only integration.

**Sharing the Git repository shares code, not live data.** Each laptop has its own SQLite file. For a single shared data view, everyone must talk to the same appropriately secured backend. Do not put a SQLite file in Git or claim Supabase Auth synchronises local planning databases.

## 8. Current scope: working vs not implemented

**Working in the tested demo:** separate role views; ownership filtering; request submission/withdrawal; officer mass approval; persistent records; seven-night utilization overview; full-screen manual scheduling with five-minute drag placement; immediate visual conflict rechecking; bulk persistent job locks; unlocked-booking reshuffling; a real small-demo search; manual and generated proposal preview; single-officer publication; revision-based stale-plan rejection; atomic writes; resource updates; demo reset; audit records.

**Domain model and data classes (implemented in `backend/app/models.py`):** Typed Pydantic v2 data classes covering all mathematical entities from `constraints_lp_setup.md`: the 9 hard constraints (engineering window with handback margin $B$, sector unavailabilities $\mathcal{B}_s$ and exclusive safety footprints, work/power compatibility with $P_j \in \{\text{ON}, \text{OFF}, \text{NONE}\}$, specialist engineer competencies and pooled resource capacities $C_r$, transfer travel times $\tau^E$, dependencies with handover buffers $\Delta_{pj}$, booking commitment and freeze horizon $H^{freeze}$, timing flexibility modes with deferral flags $D_j^{allow}$, and service-critical mandatory work $M_j$), engineering vehicles ($\mathcal{V}$), transit corridors ($I_{v,s}$, $\tau_{v,s}$), conflicts, and unified planning snapshots.

**Implemented and executed locally:** strict and recovery CP-SAT modes, all nine documented constraints, sequential objectives, deterministic settings, comprehensive-data loading, an independent nine-rule validator, API proposal generation and repeat validation before commit.

**Not implemented in the solver engine:** choosing new vehicle routes or assignments when a request contains no vehicle-demand field; multiple alternative proposals in one solve; phase-specific resource/power states; external railway system integrations; production deployment hardening.

All jobs are complete, unsplittable work packages. One lead engineer and the specified equipment are reserved for the entire package. The technician pool is interchangeable capacity, not individually routed people. The first resource arrival is assumed possible. A flat 15-minute inter-site transfer and 10-minute opposed-power guard are fictional examples, not operating instructions.

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
