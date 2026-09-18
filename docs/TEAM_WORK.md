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
> 6. Deliver exact global nights, recurring maintenance, low-churn dynamic replanning, safe manual edits and grounded explanations.

---

## 1. Workstream Ownership & Deliverables

Per the official adoption plan, team responsibilities are divided as follows:

| Workstream | Main files / area | Key responsibilities | Definition of Done |
|---|---|---|---|
| **Data / Domain** | `backend/app/domain_models.py`, `io.py`, `topology.py`, official CSVs | Ingest and normalise all 8 official CSVs; own typed enrichment schemas and composite asset keys; calculate core/protection footprints | Official round trip passes; recurrence/calendar inputs are versioned and cannot contaminate official schemas |
| **Optimisation** | `backend/app/ps1/solver.py`, `validation.py` | Implement CP-SAT multi-week access, local night indexing, and possession group packing; enforce mandatory complete workload and Scenario A/B/C policies; optimise exact penalty | 100% complete workload feasible incumbent found; exact objective optimised; zero official hard violations |
| **Operational Solver** | Planned modules under `backend/app/ps1/` | Calendarise global nights; generate recurring jobs; freeze history; add emergencies; optimise scenario score then churn; repair pinned edits | Exact dates and cadence validate; no occurred work moves; churn/score are decomposed and reproducible |
| **Backend / API** | `backend/app/ps1/models.py`, `artifacts.py`, `api/ps1_routes.py`, `backend/app/db/` | Persist immutable official/enrichment revisions, runs, exact dates, drafts, diffs and explanation facts; enforce export and transaction boundaries | Official exports stay exact; stale drafts fail; failed replan cannot replace published plan |
| **Frontend** | `nebula-ui/src/` | Build upload/scenario/date views, recurrence editor, drag/move preflight/repair and grounded chat; never implement hard rules client-side | UI renders API facts, distinguishes local night/global date and preserves conflict/provenance states |
| **Explanation / Security** | PS1 API fact packs, chatbot tools and audit | Deterministic simple explanations, scoped read-only tools, prompt/tool provenance, tenant/role isolation and fallback | Displaced-activity and general schedule answers cite facts; model outage and injection tests pass |
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
4. **Milestone 4: Operational Scheduling (Data, Optimiser, Backend, Frontend)**
   - Add explicit Singapore operating calendars and exact-date assignment.
   - Generate mandatory station/sector jobs from versioned recurrence policies.
   - Add emergency/dynamic revisions, factual freeze boundaries and lexicographic minimum churn for each selected scenario.
   - *Exit evidence:* Date/cadence validators pass and replans preserve occurred work while reporting scenario score and churn separately.
5. **Milestone 5: Decision Support (Backend, Frontend, Optimiser, Security)**
   - Add drag/move draft preflight, transactional revalidation and pinned repair.
   - Add explanation fact packs and a role-scoped, read-only schedule chatbot with deterministic fallback.
   - *Exit evidence:* Conflict families and stale drafts are tested; explanations trace to stored evidence and cannot mutate plans.

---

## 3. Shared Files & Coordination Rules

- **Authoritative Source:** Treat [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md) as the single authoritative source of truth. Historical files (`constraints_lp_setup.md`, `scripts/generate_synthetic_dataset.py`, `comprehensive_synthetic_data.json`) are retired from PS1 authority.
- **Legacy Code Isolation:** `backend/app/api/routes.py` and `backend/app/services/cp_sat.py` are legacy transition components. Official solver-specific code belongs in `backend/app/ps1/` and PS1 HTTP routes in `backend/app/api/ps1_routes.py`; canonical shared models/I/O/topology remain at `backend/app/` root.
- **Official/Operational Isolation:** Official models/I/O remain in `backend/app/domain_models.py`, `io.py` and `topology.py`. Enrichment models reference an immutable official revision and cannot add fields/IDs to official exports.
- **Objective Order:** For replans, apply one selected A/B/C policy, freeze factual history, minimise scenario score, then churn. Label an enriched score operational rather than official; any tolerance requires explicit approval and reporting.
- **Git Branches:** Feature branches should be focused on one module or milestone task:
  ```sh
  git switch -c feat/ps1-io-parser
  # work on backend/app/io.py
  python -m pytest backend/tests/test_data_layer.py
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
6. **Global Nights:** Every operational access maps to one eligible `service_date`; shared groups align and `access_night` is never interpreted as weekday.
7. **Recurrence:** Generated station/sector occurrences have deterministic IDs and no cadence gap beyond `max_interval_days`.
8. **Frozen/Low Churn:** Occurred/in-progress/locked work remains unchanged and churn ignores label-only symmetry.
9. **Manual Safety:** Drag preflight covers all hard-rule families; save rechecks current revisions; failed repair preserves publication.
10. **Grounded Explanation:** Fact packs and chatbot answers cite run/activity evidence, enforce access control and work without the model provider.
