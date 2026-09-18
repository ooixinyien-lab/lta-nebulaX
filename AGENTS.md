# AGENTS.md — AI Agent Operating Guide for NebulaX

Welcome to **NebulaX**, the rail maintenance scheduling engine built for the Land Transport Authority (LTA) challenge.

This document serves as the operational handbook and single entry point for AI coding agents interacting with this repository. It establishes project context, authoritative constraints, architectural standards, development workflows, and strict behavioral guardrails.

---

## 1. Project Overview & Mission

NebulaX is an enterprise-grade railway possession and maintenance scheduling system targeting **first place in Problem Statement 1 (PS1)**.

### Core Order of Priorities
1. **100% Workload Satisfaction:** Every activity's full workload must be scheduled ($\sum_w (2 x_{iw} + e_{iw}) \ge 2 d_i$). Dropping, deferring, or truncating activities is strictly prohibited.
2. **Official Hard Constraint Compliance:** Zero violations of physical, safety, operational, and scenario constraints.
3. **Official Score Minimisation:** Minimise penalties on hidden test instances across:
   - Weighted activity lateness ($P$), summed per activity against its contract's `planned_completion_date`.
   - Excess possession slot count ($V$), summed across location-weeks and charged at 7 points per slot in Scenarios B/C.
   - ECLO access count ($E$), counting `eclo=1` access rows and charged at 5 points per access in Scenarios B/C.
4. **Scenario Handling:** Correctly solve Scenarios **A** (strict supply), **B** (strict completion dates), and **C** (balanced with ECLO windows).
5. **Bounded Runtime & Robustness:** Reliable incumbent retention under tight solver timeouts; graceful handling of infeasibility.
6. **Operational Value:** Verifiable disruption replanning and explainable scheduling decisions.

Contract-level overrun is reported in `RESULTS.csv` and hard-forbidden in Scenario B; it is not an additional penalty on top of $P$. Follow the adoption plan's reconciled scoring definition and the scenario objectives below.

---

## 2. Authoritative Single Source of Truth

> [!IMPORTANT]
> **CRITICAL RULE:** **[PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md)** is the **single authoritative source of truth** for all optimisation models, data contracts, and scoring logic.
> 
> - If any legacy document (e.g. `constraints_lp_setup.md`, historical issues, or legacy comments) contradicts `PS1_OFFICIAL_ADOPTION_PLAN.md`, **the adoption plan strictly supersedes them**.
> - The codebase is actively transitioning from a legacy synthetic single-night prototype to the official PS1 multi-week model. Do not resurrect legacy single-night abstractions.

---

## 3. Codebase State & Migration Map

Be acutely aware of what is active vs. retired:

| Component | Status | Location | Notes |
|---|---|---|---|
| **PS1 Domain Models** | **ACTIVE (Authoritative)** | [`backend/app/domain_models.py`](file:///backend/app/domain_models.py) | Pydantic v2 domain schemas, enums, problem containers, output rows. |
| **PS1 Data Ingestion & I/O** | **ACTIVE (Authoritative)** | [`backend/app/io.py`](file:///backend/app/io.py) | Ingests 8 official CSVs, checks relational integrity/DAG cycles, exports 3 CSV bundles. |
| **PS1 Network Topology** | **ACTIVE (Authoritative)** | [`backend/app/topology.py`](file:///backend/app/topology.py) | $2k+1$ graph invariants, core footprints, buffers, Live mirroring, interchange effects. |
| **PS1 Data Tests** | **ACTIVE (Passing)** | [`backend/tests/test_data_layer.py`](file:///backend/tests/test_data_layer.py) | 21 comprehensive tests for ingestion, topology, buffers, and exports. |
| **Application Infra** | **ACTIVE (Keep)** | [`backend/app/database.py`](file:///backend/app/database.py), [`backend/app/config.py`](file:///backend/app/config.py), [`backend/app/auth/`](file:///backend/app/auth/) | FastAPI app, SQLite persistence, revision tokens, transaction audits, role identity. |
| **Legacy Solver & Validator** | **RETIRED from PS1** | `backend/app/services/cp_sat.py`, `full_validator.py` | Single-night minute-level solver and validator. Kept for historical reference only. |
| **Legacy `models.py`** | **DELETED** | (Formerly `backend/app/models.py`) | Removed in favor of `domain_models.py`. Note: Legacy test files importing `backend.app.models` are obsolete/pending update. |

---

## 4. Tech Stack & Execution Environment

- **Language:** Python 3.12+ (standard local interpreter at `.venv/bin/python`).
- **Optimisation Solver:** Google OR-Tools CP-SAT (`ortools.sat.python.cp_model`).
- **Web Framework:** FastAPI, Starlette, Uvicorn, Pydantic v2 (`ConfigDict(extra="forbid")`).
- **Persistence:** SQLite with WAL mode, revision tokens, and audit logging.
- **Frontend:** Vanilla JavaScript (native ES modules), HTML5, CSS3.
  - **NO frontend build step.** No Webpack, no Vite, no Next.js.
  - **DO NOT RUN `npm run dev`.** The frontend is statically served by FastAPI.

### Essential Development Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements-cpsat.txt   # Core app + OR-Tools
python -m pip install -r requirements-dev.txt     # Test suite + dev tools

# Run local FastAPI development server (Mac/Linux)
sh scripts/dev.sh
# Or directly:
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Run PS1 Data Layer tests (all 21 passing)
pytest backend/tests/test_data_layer.py -v

# Run standalone prototype solver tests
pytest backend/tests/test_solver_v0.py backend/tests/test_solver_v1.py -v

# Run optional JS syntax validation (requires Node)
node scripts/check-js.mjs
```

> [!WARNING]
> Running bare `pytest` across all test files currently triggers collection errors in legacy test files (`test_api.py`, `test_full_solver.py`, etc.) because they still reference the deleted `backend.app.models`. When testing, execute target test suites like `pytest backend/tests/test_data_layer.py`.

---

## 5. Domain Rules & Mathematical Invariants

When implementing or modifying optimisation models and business logic, agents must enforce these exact invariants:

### 1. Planning Horizon & Units
- Horizon: **30 weeks** ($W = \{1, \dots, 30\}$), starting Monday 2027-01-04 to Sunday 2027-08-01.
- Date mapping: Week $w$ finishes on ending Sunday: $\text{date}(w) = \text{start} + (7w - 1) \text{ days}$.
- **Doubled Integer Units:** Use doubled units to avoid floating-point errors:
  - Standard access yield = 1.0 (doubled: **2**)
  - Early Closure / Late Opening (ECLO) yield = 1.5 (doubled: **3**)
  - Activity workload demand = $d_i$ (doubled: **$2 d_i$**)
  - Yield condition: $\sum_{w \in W} (2 x_{iw} + e_{iw}) \ge 2 d_i$

### 2. Three Distinct Scheduling Dimensions
Never confuse or collapse these dimensions:
1. **`week` ($1 \dots 30$):** Global calendar placement and completion accounting.
2. **`access_night` ($1 \dots K_c$):** Local night index within the contract/type's granted weekly cap.
3. **`co_share_group`:** Location-and-week-scoped possession group identifier. **Possession group labels are local to each location and week, NOT global across an entire route.**

### 3. Possession Co-Sharing & Legal Mix
Within any location-week possession group:
- Exactly **1 PM alone**; OR
- Exactly **1 PC with at most 3 C** (at most 4 activities total); OR
- At most **4 C** activities.
- **Two PCs can NEVER share a possession group.**
- One occupied possession group consumes **1 possession slot** at that location and week.

### 4. Network Topology & Protection Buffers
- **Composite Station Keys:** Station IDs like `H01` and `H02` are interchanges shared by both `ALP` and `BET`. Always identify stations by `(line_code, station_id)`.
- **$2k+1$ Invariant:** A line with $k$ stations has $k-1$ sectors connecting them sequentially.
- **Buffers:**
  - **Live Work:** 2 buffer sectors on each side + opposite-bound closure mirroring + cross-line interchange tunnel/platform protection.
  - **Non-live (Consist):** 1 buffer sector on each side; no opposite-bound mirroring.
  - **Non-live (Others):** 0 buffer sectors.
- Buffers are clamped at line termini.

### 5. Scenario Policies
Let $v_{lw}$ be the excess occupied possession slots above nominal supply at location $l$ in week $w$, so $V = \sum_{l,w} v_{lw}$. This is separate from the ECLO access indicator $e_{iw}$ used in workload accounting.

- **Scenario A (Strict Supply):** Supply is hard-capped by `04_LOCATION_SUPPLY.csv` ($V = 0$), and ECLO is hard-forbidden ($E = 0$). Planned-date lateness is permitted. Minimise $P$.
- **Scenario B (Strict Schedule):** Every activity must complete on or before its contract's planned completion date, so contract overrun is hard-forbidden and $P = 0$. Supply can exceed nominal capacity with no additional published hard excess cap; ECLO is permitted anywhere in the horizon. Minimise $7V + 5E$.
- **Scenario C (Balanced):** Planned-date lateness is permitted. At most 1 excess slot per location-week is allowed ($v_{lw} \le 1$). ECLO is permitted only within one selected span of at most 2 consecutive calendar weeks per affected line; cross-line Live accesses must fit both lines' windows. Minimise $P + 7V + 5E$.

### 6. Official 3-CSV Output Format
All scenario runs must produce exactly these three CSVs matching official schemas:
1. **`SCHEDULE_ACCESS.csv`:** `activity_id,access_seq,week,eclo,access_night` (`eclo` is integer `0` or `1`).
2. **`SCHEDULE_OCCUPANCY.csv`:** `activity_id,week,location_id,co_share_group`.
3. **`RESULTS.csv`:** `scenario,contract_number,simulated_completion_date,overrun_days`.

---

## 6. Directory Structure & Key Files

```text
lta-nebulaX/
├── AGENTS.md                      <-- You are here (AI agent operating guide)
├── PS1_OFFICIAL_ADOPTION_PLAN.md  <-- Single authoritative specification for PS1
├── README.md                      <-- System architecture & developer instructions
├── requirements.txt               <-- Base production dependencies
├── requirements-cpsat.txt         <-- Core dependencies including OR-Tools
├── requirements-dev.txt           <-- Development & test dependencies
├── backend/
│   ├── app/
│   │   ├── main.py                <-- FastAPI entrypoint & static route mounting
│   │   ├── config.py              <-- Pydantic settings & environment configuration
│   │   ├── database.py            <-- SQLite connection, revision tokens & transactions
│   │   ├── domain_models.py       <-- Official PS1 Pydantic v2 models & enums
│   │   ├── io.py                  <-- Official 8-CSV ingestion & 3-CSV export
│   │   ├── topology.py            <-- Rail network graph, core & protection footprints
│   │   ├── auth/                  <-- Role verification (Requester vs Officer)
│   │   ├── api/                   <-- HTTP route handlers (routes.py)
│   │   └── services/              <-- Legacy solver & validator (retired from PS1 path)
│   └── tests/
│       ├── test_data_layer.py     <-- Active test suite for PS1 data & topology
│       ├── test_solver_v0.py      <-- Solver prototype tests
│       └── test_solver_v1.py      <-- Solver prototype tests
├── data/                          <-- 8 official CSVs (01_LINES.csv ... 08_ACTIVITY_DETAILS.csv)
├── docs/                          <-- Supplementary architectural specs & contracts
│   ├── TEAM_WORK.md               <-- Workstream boundaries & deliverables
│   ├── SOLVER.md                  <-- Optimisation solver formulations
│   ├── API_CONTRACT.md            <-- REST API schemas
│   └── TEST_REPORT.md             <-- Test execution reports
├── frontend/                      <-- Vanilla JS frontend (served statically)
│   ├── index.html                 <-- Single page app shell
│   ├── styles.css                 <-- Application styles
│   └── src/                       <-- ES modules (app.js, components/, pages/)
└── scripts/                       <-- Utility scripts (dev.sh, check-js.mjs)
```

---

## 7. AI Agent Guardrails & Operating Principles

Agents working on this codebase must adhere to the following rules:

### Rule 1: Respect the Source of Truth
- When implementing optimisation features, route endpoints, or validators, always verify your logic against [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md).
- Do not make arbitrary assumptions about rules, penalty weights, or constraints. Check the plan or ask.

### Rule 2: Strict Pydantic v2 Standards
- Always inherit from `PS1Base` in [`backend/app/domain_models.py`](file:///backend/app/domain_models.py) with `extra="forbid"`.
- Use explicit type annotations and field validators.
- Never write ad-hoc dictionary passing where typed domain models are available.

### Rule 3: Maintain Frontend Architecture
- The frontend is pure native ES modules without build tooling.
- **Never** add npm build frameworks (Webpack, Vite, React, Tailwind CLI, etc.) unless explicitly instructed by the user.
- All styling belongs in [`frontend/styles.css`](file:///frontend/styles.css) and script logic in [`frontend/src/`](file:///frontend/src/).

### Rule 4: Data Safety & Git Hygiene
- **Never commit:** `.env`, `.venv`, `*.sqlite3`, `.DS_Store`, or `__pycache__`.
- All data in `data/` is synthetic. This repository does not connect to live railway control or signaling networks.
- Before committing changes, run relevant tests to ensure no regressions:
  ```bash
  pytest backend/tests/test_data_layer.py
  ```

### Rule 5: Keep Changes Scoped
- Respect workstream boundaries from [`docs/TEAM_WORK.md`](file:///docs/TEAM_WORK.md).
- Do not refactor unrelated modules when fixing a specific bug or implementing a single milestone feature.
