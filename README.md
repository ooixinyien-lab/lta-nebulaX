# ForRail — PS1 Official Rail Maintenance Scheduling & Operations Engine

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Google OR-Tools CP-SAT](https://img.shields.io/badge/solver-OR--Tools%20CP--SAT-red.svg)](https://developers.google.com/optimization/cp/cp_solver)
[![React 19](https://img.shields.io/badge/frontend-React%2019%20%2B%20Vite-cyan.svg)](https://vitejs.dev/)
[![FastAPI](https://img.shields.io/badge/backend-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/persistence-SQLite%20WAL-lightgrey.svg)](https://www.sqlite.org/wal.html)

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> **ForRail** is the official rail maintenance possession scheduling and operations engine built for the Land Transport Authority (LTA) challenge.
>
> [PS1_OFFICIAL_ADOPTION_PLAN.md](PS1_OFFICIAL_ADOPTION_PLAN.md) acts as the **single authoritative source of truth** for all mathematical models, data contracts, and scoring logic.

---

## 1. Executive Summary & Mission

**Target:** First place in Problem Statement 1 (PS1).

### Core Order of Priorities
1. **100% Workload Satisfaction:** Every single activity's full demand is scheduled ($\sum_w (2 x_{iw} + e_{iw}) \ge 2 d_i$). Dropping, deferring, or truncating activities is strictly forbidden.
2. **Zero Official Hard Violations:** Strict mathematical enforcement of physical track capacity, legal possession mixing, directional line topology, and protection buffer footprints.
3. **Official Score Minimisation:** Minimise exact penalties on test instances across:
   - Weighted activity lateness ($P$), summed per activity against its contract's `planned_completion_date`.
   - Excess possession slot count ($V$), charged at 7 points per slot in Scenarios B and C.
   - Early Closure / Late Opening (ECLO) access count ($E$), charged at 5 points per access in Scenarios B and C.
4. **Scenario Policies:** Exact compliance across:
   - **Scenario A (Strict Supply):** Supply is hard-capped ($V = 0$), ECLO forbidden ($E = 0$); minimise lateness $P$.
   - **Scenario B (Strict Schedule):** Zero contract overrun permitted ($P = 0$); minimise supply excess and ECLO ($7V + 5E$).
   - **Scenario C (Balanced Trade-Off):** Max 1 excess slot per location-week ($v_{lw} \le 1$), line ECLO windows capped at $\le 2$ consecutive weeks; minimise $P + 7V + 5E$.
5. **Operational Enterprise Excellence:** Exact Singapore calendar dispatch, ad-hoc/emergency injection, low-churn dynamic replanning, preflight conflict detection, and grounded AI decision support.

---

## 2. System Architecture & Capabilities

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             FORRAIL APPLICATION SHELL                            │
└──────────────────────────────────────────────────────────────────────────────────┘
            │                                                      │
            ▼                                                      ▼
┌───────────────────────────────┐              ┌───────────────────────────────────┐
│     PS1 REQUIREMENTS VIEW     │              │       OPERATIONS MODE VIEW        │
│          (For Judges)         │              │      (Real-World Operations)      │
├───────────────────────────────┤              ├───────────────────────────────────┤
│ • Official 8-CSV Ingestion    │              │ • Immutable Baseline Revisions    │
│ • CP-SAT Math Optimisation    │              │ • Ad-hoc / Emergency Additions    │
│ • Scenarios A, B, and C       │              │ • Real-time Conflict Preflight    │
│ • Interactive SVG Network Map │              │ • Dynamic Low-Churn Auto-Solve    │
│ • Possession Dispatch Board   │              │ • Schedule Diff & Displacement    │
│ • Exact 3-CSV Output Export   │              │ • Grounded Gemini AI Explainer    │
└───────────────────────────────┘              └───────────────────────────────────┘
            │                                                      │
            └──────────────────────┬───────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              FASTAPI BACKEND ENGINE                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│ • app/domain_models.py : Pydantic v2 strict schemas with extra="forbid"          │
│ • app/topology.py      : 2k+1 graph invariants, Live mirroring & buffer clamping │
│ • app/ps1/solver.py    : Google OR-Tools CP-SAT multi-criteria solver            │
│ • app/ps1/scoring.py   : Independent penalty reconstruction and score auditing   │
│ • app/ps1/validation.py: Independent validator for physical & scenario rules     │
│ • app/database.py      : SQLite WAL with atomic transactions & revision counters │
│ • app/integrations/    : Gemini API schedule explainer with read-only fact packs │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Key Highlights
- **Mathematical Soundness:** Built directly with Google OR-Tools CP-SAT. Schedules 192 workload units with 100% completeness.
- **Topological Invariants:** Enforces the $2k+1$ graph invariant across $k$ stations and $k-1$ sequential sectors, Live opposite-bound closure mirroring, and cross-line interchange protection (ALP & BET lines).
- **Possession Group Co-sharing:** Enforces legal co-sharing rules (1 PM alone, 1 PC + $\le 3$ C, or $\le 4$ C; never 2 PCs) within location-week scopes.
- **Dual-Bound Interactive Map:** High-performance SVG interactive canvas showing stations, sector links, buffer expansions, and active workfronts with pan/zoom controls.

---

## 3. Quickstart & Installation

### Prerequisites
- **Python 3.12+** (recommended)
- **Node.js 18+** (for frontend development/build)

### 1. Setup Backend Environment

```bash
# Clone and enter directory
cd lta-nebulaX

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
python -m pip install -r requirements-cpsat.txt
python -m pip install -r requirements-dev.txt

# Copy environment configuration
cp .env.example .env
```

### 2. Start the Application

You can launch the backend and frontend in two easy ways:

#### Option A: Quick Dev Script (Recommended)
```bash
sh scripts/dev.sh
```

#### Option B: Separate Backend & Frontend Processes

**Terminal 1 (Backend - FastAPI):**
```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 (Frontend - Vite / React 19):**
```bash
cd nebula-ui
npm install
npm run dev
```

- **Modern Interactive App:** Open [http://127.0.0.1:5173](http://127.0.0.1:5173) (Vite proxies `/api` calls directly to port 8000).
- **Backend API & Swagger Docs:** Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
- **Production Bundle (FastAPI-served):** Running `npm run build` inside `nebula-ui/` compiles the app to `nebula-ui/dist/`, which FastAPI automatically serves at [http://127.0.0.1:8000/network-map](http://127.0.0.1:8000/network-map) or [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

---

## 4. Step-by-Step Guide for Judges: PS1 Requirements View

This walkthrough guides judges through testing any custom 8-file PS1 dataset, running the CP-SAT optimisation engine, visually verifying constraints on the interactive map, and exporting the exact official 3-CSV bundle.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PS1 JUDGE VERIFICATION FLOW                           │
│                                                                                 │
│  [1. Ingestion]       [2. Select Mode]     [3. Solve Engine]    [4. Verification]     [5. Export]      │
│  Upload 8 CSVs   ───►  PS1 Requirements ───► Solve All      ───► Interactive Map ───► Download 3 CSVs  │
│  & Validate DB         Scenario A/B/C       CP-SAT 100%          & Dispatch Board     Official Bundle  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Step 1: Open the Application & Navigate to Data Ingestion
1. Open [http://localhost:5173](http://localhost:5173) (or [http://localhost:8000](http://localhost:8000)) in your browser.
2. Click **Data Ingestion** in the top navigation bar.

### Step 2: Upload Your Custom 8-File PS1 Bundle
1. In the **Data Ingestion** panel, click **Browse CSV Files** (or drag and drop your files).
2. Select your 8 official PS1 input CSVs:
   - `01_LINES.csv`
   - `02_STATIONS.csv`
   - `03_SECTORS.csv`
   - `04_LOCATION_SUPPLY.csv`
   - `05_BUFFER_LOCATION.csv`
   - `06_PARAMETERS.csv`
   - `07_PROJECT_DETAILS.csv`
   - `08_ACTIVITY_DETAILS.csv`
3. The real-time file checklist will turn green for all 8 files.
4. Click **Populate Database**.
   - *What happens:* ForRail checks relational foreign keys, validates acyclicity (DAG) of predecessor dependencies, enforces $2k+1$ topology invariants, and stores the raw bytes with a cryptographic SHA-256 fingerprint.

*(Note: To reset and test another dataset at any time, click **Clear Database** in the Danger Zone).*

### Step 3: Switch to PS1 Requirements Mode & Choose Scenario
1. Navigate back to **Dashboard** using the top navigation bar.
2. In the top header controls, ensure **PS1 Requirements** is selected (this is the default evaluation view for judges).
3. Select your scenario policy by clicking **A**, **B**, or **C**:
   - **Scenario A (Strict Supply):** Supply is hard-capped by `04_LOCATION_SUPPLY.csv` ($V = 0$) and ECLO is strictly forbidden ($E = 0$). Objective: minimise planned lateness penalty $P$.
   - **Scenario B (Strict Schedule):** Every activity must complete on or before its contract's planned completion date ($P = 0$, zero overrun). Flexible supply and ECLO accesses permitted. Objective: minimise $7V + 5E$.
   - **Scenario C (Balanced Trade-Off):** Lateness permitted, at most 1 excess slot per location-week ($v_{lw} \le 1$), ECLO allowed within a maximum 2-week window per line. Objective: minimise $P + 7V + 5E$.

### Step 4: Run the CP-SAT Optimisation Engine
1. Click **Solve All Scenarios** (or solve the active scenario).
2. The solver button will show **Solving…** while Google OR-Tools CP-SAT executes in the background.
3. The solver:
   - Guarantees **100% full workload completion** across all activities.
   - Enforces legal possession co-sharing groups.
   - Computes protection buffers (Live 2, Consist 1, Others 0), Live opposite-bound mirroring, and interchange platform protection.
   - Optimises the scenario penalty objective directly.
4. Upon completion, the interactive schedule dashboard immediately renders.

### Step 5: Visual Verification on the Interactive Network Map
1. **Interactive SVG Network Map:**
   - Explore the topological rail projection of Singapore's fictional corridor (**ALP** and **BET** lines).
   - Use the **Week Slider** (Weeks 1 to 30) or the timeline dots to jump between weeks.
   - Hover over stations and sectors to see active possessions, track directions, and spatial allocations.
   - Use **Layer Controls** to toggle:
     - **Workfronts:** Highlights sectors with active engineering work.
     - **Buffer Zones:** Displays the protective buffer expansions around active worksites.
     - **Crossover Links:** Shows dual-line interchange connections (H01, H02) where Live work triggers cross-line platform protection.
     - **Station Labels & Grid Lines:** Adjusts visual clarity.
2. **Interactive Possession Dispatch Board:**
   - Scroll down to inspect the possession dispatch matrix organized by location and week.
   - Inspect co-sharing group composition and verify that no two PC activities ever share a group.
   - Click any activity card to open the **Activity Inspector Drawer**, displaying contract IDs, access sequences, workload yield progress, predecessor dependencies, and nature of work.

### Step 6: Export the Official 3-CSV Submission Bundle
1. Click the **Export Schedule (CSV)** button in the network toolbar or dispatch board header.
2. ForRail instantly generates and downloads the three required competition CSV files:
   - **`SCHEDULE_ACCESS.csv`**: Contains `activity_id,access_seq,week,eclo,access_night`.
   - **`SCHEDULE_OCCUPANCY.csv`**: Contains `activity_id,week,location_id,co_share_group`.
   - **`RESULTS.csv`**: Contains `scenario,contract_number,simulated_completion_date,overrun_days`.
3. The exported files conform exactly to the official PS1 challenge format, with zero extraneous columns or invalid values.

---

## 5. Step-by-Step Guide for Operators: Operations Mode View (Bonus Features)

In real-world railway networks, maintenance plans cannot remain static. Track defects, emergency repairs, and operational disruptions require rapid, low-churn replanning without violating safety rules or tearing up already-committed engineering schedules.

Switching to **Operations Mode** unlocks ForRail's enterprise operations suite:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           OPERATIONS MODE BONUS SUITE                           │
│                                                                                 │
│  [1. Mode Toggle]    [2. Add Job]         [3. Preflight Check]  [4. Auto-Solve]    [5. AI Chatbot]   │
│  Operations Mode ──► Emergency / Ad-Hoc ──► Real-Time Violations ──► Min-Churn  ──► Grounded Gemini │
│  Baseline Rev 1      Job Insertion        & Safety Alerts       Disruption Replen   Fact Explainer    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Feature 1: Versioned Operational Baselines
- Toggle the header switch from **PS1 Requirements** to **Operations Mode**.
- ForRail automatically creates an operational baseline derived from the official schedule.
- Baselines are immutable and tracked with revision numbers (e.g. `Baseline base-xxx Revision 1`). All subsequent changes are recorded in an audit trail.

### Feature 2: Ad-Hoc & Emergency Job Request Injection
1. Click **+ Add Job Request** in the top header.
2. The modal allows rail operators to specify emergency or unscheduled maintenance:
   - **Job ID & Contract Number:** Enter unique operational identifiers (e.g., `EMERGENCY-01`, `C001`).
   - **Release Date & Deadlines:** Set planned start date, planned completion date, and hard completion date.
   - **Workload Demands:** Required access count, maximum accesses per week, and concurrent workfronts.
   - **Access Type & Nature:** Choose `PM`, `PC`, or `C`, and nature (`Live`, `Non-live (Consist)`, or `Non-live (Others)`).
   - **Source:** Choose `addition` (planned routine addition) or `emergency` (urgent track defect).
   - **Location Span:** Select start and end location on the line.
3. Click **Add without solving** to inject the job into the active draft.

### Feature 3: Real-Time Preflight Conflict Detection
1. As soon as new demands or conflicting moves are introduced, ForRail's server-side validator runs preflight checks.
2. The banner immediately alerts the operator:
   `⚠️ X scheduling conflicts require resolution`
3. Click **View conflicts** to review the exact rule breaches:
   - Location capacity exceedance
   - Illegal co-sharing mix (e.g. PC co-sharing with another PC)
   - Predecessor dependency violations
   - Buffer clashing with live track operations

### Feature 4: Dynamic Re-Planning & Churn Minimization ("Auto Solve")
1. In the header, click **Auto Solve**.
2. ForRail executes a lexicographic multi-objective CP-SAT solver:
   - **Historical Freeze:** All occurred, in-progress, and locked work is strictly frozen and cannot move.
   - **Primary Objective:** Satisfy all hard safety rules and minimise the active scenario objective ($P$, $V$, or $E$).
   - **Secondary Objective (Minimum Churn):** Minimise operational disruption by penalising service date displacement days and reassigned jobs.
3. The solver generates a **Candidate Plan** without overwriting the published baseline.

### Feature 5: Reviewing the Disruption Diff
1. Once solved, the header banner turns green and reports the exact disruption metrics:
   `Operational schedule is valid · Candidate diff: X jobs changed · Y days displaced · cost Z`
2. Operators can inspect both the Network Map and Dispatch Board to verify how the emergency work was slotted in with minimal disturbance to other contractors.

### Feature 6: Promoting Candidate to Baseline ("Accept Schedule")
1. When satisfied with the candidate plan, click **Accept Schedule** in the header.
2. ForRail transactionally commits the changes, increments the baseline revision (e.g., Revision 1 $\rightarrow$ Revision 2), and clears transient draft states.

### Feature 7: Grounded AI Schedule Explainer (Gemini Chatbot)
1. In the bottom-right corner of the screen, click the **Schedule Explainer** launcher button.
2. The AI assistant opens a docked chat panel powered by Google Gemini.
3. **Strict Grounding & Security:**
   - The chatbot is **strictly read-only**: it cannot mutate, solve, or corrupt schedule state.
   - It is grounded entirely in structured server-side **Fact Packs** and allowlisted read tools.
   - It cannot hallucinate: if a reason is not backed by mathematical solver evidence, it explicitly reports that no constraint evidence exists.
4. **Try asking the assistant:**
   - *"Why did Activity A036 get scheduled in Week 22?"*
   - *"Which contracts are driving lateness penalties in Scenario A?"*
   - *"What are the main bottleneck locations in Week 14?"*
   - *"Explain why the emergency job displaced Contract C004."*
5. The explainer responds with verifiable facts, citing contract numbers, location IDs, buffer requirements, and objective score impacts.

---

## 6. Automated Testing & Verification

ForRail includes an exhaustive test suite covering data ingestion, graph topology invariants, buffer expansions, scoring reconciliation, CP-SAT solving, and the React frontend.

### Running Backend Tests

```bash
# Run all active PS1 solver, data, and scoring tests (39 tests)
source .venv/bin/activate
pytest backend/tests/test_data_layer.py backend/tests/test_ps1_scoring_validation.py backend/tests/test_ps1_solver.py -v
```

### Running Frontend Vitest Suite

```bash
cd nebula-ui
npm test -- --run
```
*(44 unit and integration tests covering the Network Map, Dispatch Board, Chatbot, and Planning State).*

### Running Full Build

```bash
cd nebula-ui
npm run build
```

---

## 7. Project Directory Layout

```text
lta-nebulaX/
├── PS1_OFFICIAL_ADOPTION_PLAN.md  <-- Single authoritative specification for PS1
├── README.md                      <-- System architecture & complete user guide
├── AGENTS.md                      <-- AI agent operational handbook
├── requirements-cpsat.txt         <-- Core application & OR-Tools dependencies
├── requirements-dev.txt           <-- Testing and development tools
├── data/                          <-- 8 official CSVs (01_LINES.csv ... 08_ACTIVITY_DETAILS.csv)
├── backend/
│   ├── app/
│   │   ├── main.py                <-- FastAPI entrypoint, router mounting, static dist serving
│   │   ├── config.py              <-- Pydantic settings & environment configuration
│   │   ├── database.py            <-- SQLite WAL persistence, revision counters, audit log
│   │   ├── domain_models.py       <-- Authoritative Pydantic v2 domain schemas (extra="forbid")
│   │   ├── io.py                  <-- 8-CSV ingestion & official 3-CSV export bundle
│   │   ├── topology.py            <-- 2k+1 graph invariants, Live mirroring & protection buffers
│   │   ├── ps1/
│   │   │   ├── solver.py          <-- CP-SAT multi-criteria solver (Scenarios A, B, C)
│   │   │   ├── scoring.py         <-- Penalty calculation (P, V, E)
│   │   │   ├── validation.py      <-- Independent rule validator
│   │   │   ├── artifacts.py       <-- 3-CSV bundle serialization & round-trip verification
│   │   │   └── prompts/           <-- Schedule Explainer system prompts
│   │   ├── api/
│   │   │   ├── ps1_routes.py      <-- Official PS1 upload/solve/export REST API
│   │   │   ├── planning_routes.py <-- Unified planning & operations REST API
│   │   │   └── ps1_calendar_routes.py
│   │   └── integrations/
│   │       └── gemini.py          <-- Grounded Gemini Schedule Explainer service
│   └── tests/
│       ├── test_data_layer.py     <-- Ingestion, foreign keys, DAG acyclicity & topology tests
│       ├── test_ps1_scoring_validation.py
│       └── test_ps1_solver.py     <-- CP-SAT feasibility and scenario policy tests
├── nebula-ui/                     <-- Modern React 19 + Vite + Tailwind CSS frontend
│   ├── src/
│   │   ├── App.jsx                <-- Main application shell & tab router
│   │   ├── ScheduleDashboard.jsx  <-- Interactive Possession Dispatch Board
│   │   ├── components/
│   │   │   ├── AppHeader.jsx      <-- Top navigation & mode toggles
│   │   │   ├── network-map/       <-- Interactive SVG Network Map components
│   │   │   └── chatbot/           <-- Grounded Schedule Explainer chat interface
│   │   ├── planning/              <-- Planning state machine & API client
│   │   └── services/              <-- REST API clients
│   └── dist/                      <-- Production build served at /network-map
└── docs/                          <-- Comprehensive architectural specifications
    ├── SOLVER.md                  <-- Mathematical solver formulation details
    ├── API_CONTRACT.md            <-- REST API schemas
    ├── DATABASE.md                <-- SQLite schema ledger and persistence architecture
    ├── REFERENCES.md              <-- Technical references and challenge sources
    └── TEST_REPORT.md             <-- Test verification logs
```

---

## 8. Data Safety & Fictional Network Notice

- All rail networks, station names, sector codes, and maintenance contracts in `data/` are purely synthetic and provided for the Land Transport Authority (LTA) challenge.
- **ForRail** does not connect to live signaling, power grid, or train control systems.
- No confidential or proprietary operational data is stored or transmitted.
