# Team Handoff & Workstream Alignment (PS1 Official Adoption)

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> All work across backend, optimisation, data, frontend, and presentation must align with [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md).
>
> **Target:** First place in Problem Statement 1 (PS1).  
> **Order of Priorities:**
> 1. Schedule every activity's full workload (100% complete; dropping work is prohibited).
> 2. Satisfy every official hard rule.
> 3. Minimise the official penalty on hidden instances.
> 4. Handle Scenarios A, B and C correctly.
> 5. Solve reliably within a bounded runtime.
> 6. Demonstrate useful explanations and disruption replanning.

---

## 1. Workstream Ownership & Deliverables

Per the official adoption plan, team responsibilities are divided as follows:

| Workstream | Main files / area | Key responsibilities | Definition of Done |
|---|---|---|---|
| **Data / Domain** | `backend/app/ps1/io.py`, `topology.py`, official CSVs | Ingest and normalise all 8 official CSVs; enforce composite keys `(line_code, station_id)`; calculate core footprints, buffers, Live opposite-bound mirroring and interchange crossovers | 8-file parser passes schema checks; sample core footprints and accounting reproduced without errors |
| **Optimisation** | `backend/app/ps1/solver.py`, `validation.py` | Implement CP-SAT multi-week access, local night indexing, and possession group packing; enforce mandatory complete workload and Scenario A/B/C policies; optimise exact penalty | 100% complete workload feasible incumbent found; exact objective optimised; zero official hard violations |
| **Backend / API** | `backend/app/ps1/models.py`, `export.py`, `api/ps1_routes.py`, `database.py` | Add PS1 instance/run/result persistence; expose `/api/ps1/` endpoints for upload, solve, progress, results, and exports; enforce transaction/revision safety | Reproducible 8-CSV upload and 3-CSV export round trip; isolated multi-tenant instance runs |
| **Frontend** | `frontend/src/` | Build views for 8-file instance upload, scenario A/B/C comparison, timeline/occupancy visualization, and disruption replan | UI renders real PS1 multi-week data from `/api/ps1/` without embedding scheduling rules in browser |
| **Presentation** | Slides, video script | Prepare the 3-minute demonstration video and presentation deck based on measured solver evidence | Video and slides demonstrate Scenarios A/B/C, honest bounds, and measured disruption replan |

---

## 2. Implementation Milestones

1. **Milestone 1: Official Correctness (Data, Optimiser, Backend)**
   - Import and normalise 8 CSVs.
   - Implement complete-workload A/B/C solving and exact 3 CSV exports (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`).
   - *Exit evidence:* Public bundles with 100% complete workload and zero official hard violations; repeatable score reconciliation.
2. **Milestone 2: Competitive Optimisation (Optimiser, Data, Backend)**
   - Exact penalty objective optimisation ($P, V, E$).
   - Greedy seed constructor, CP-SAT hints, and symmetry breaking.
   - Targeted LNS on bottleneck location/weeks.
   - *Exit evidence:* Superior validated scores across public and perturbed instances; measured improvement curves.
3. **Milestone 3: Hidden-Instance Hardening (All Workstreams)**
   - Bounded runtime execution and incumbent retention.
   - Upload/run isolation and robust error handling.
   - Disruption replan demonstration and submission packaging (video, repo).
   - *Exit evidence:* Reliable hosted app accepting 8 unseen CSVs, exportable outputs, verified disruption demo.

---

## 3. Shared Files & Coordination Rules

- **Authoritative Source:** Treat [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md) as the single authoritative source of truth. Historical files (`constraints_lp_setup.md`, `scripts/generate_synthetic_dataset.py`, `comprehensive_synthetic_data.json`) are retired from PS1 authority.
- **Legacy Code Isolation:** `backend/app/api/routes.py` and `backend/app/services/cp_sat.py` are legacy transition components. All official PS1 code must reside in `backend/app/ps1/` and `backend/app/api/ps1_routes.py`.
- **Git Branches:** Feature branches should be focused on one module or milestone task:
  ```sh
  git switch -c feat/ps1-io-parser
  # work on backend/app/ps1/io.py
  python -m pytest backend/tests/test_ps1_io.py
  git commit -m "Implement and test 8-CSV parser"
  ```
- **Never Commit:** `.env`, `.venv`, local SQLite files (`*.sqlite3`), or cache directories.

---

## 4. Key Integration Checkpoints

1. **8-CSV Parse:** Uploading the 8 official CSVs produces verified entities and topology with zero foreign key or cycle errors.
2. **Mandatory Full Workload:** Every activity receives yield $\ge d_i$; no activities are dropped or truncated.
3. **Scenario Correctness:** Scenario A enforces strict supply (no excess); Scenario B forbids planned-date overrun; Scenario C respects line ECLO windows and max 1 excess slot/loc-wk.
4. **Export Integrity:** Generated CSV exports match official schemas exactly and round-trip through local validation.
5. **Disruption Replan:** A simulated capacity outage invalidates affected possessions, triggers a replan, and produces evidenced before/after score metrics.

