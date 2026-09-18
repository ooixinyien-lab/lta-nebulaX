# NebulaX Testing and Verification Report

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This report documents testing verification for NebulaX.
> Per [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md):
> - **Synthetic test success does not certify PS1 correctness.** The 135 passing tests below verify only the historical single-night synthetic prototype.
> - The synthetic solver's recovery behavior (scheduling 7 of 12 requests) violates PS1's mandatory complete-workload requirement.
> - Official PS1 verification and the separate operational enrichment checks below must retain explicit provenance.

---

## 1. Official PS1 Validation Loop & Test Plan

Per [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), official PS1 verification requires:

1. **8-CSV Input Checks:** Validate schemas, composite keys `(line_code, station_id)`, gapped activity IDs, and acyclic dependencies across all 8 official input files.
2. **Mandatory Full Workload:** Validate that every activity receives full yield ($\ge d_i$) with no dropped activities.
3. **Topology & Protection Expansion:** Independent verification of core footprint traversal, buffer sectors (Live 2, Consist 1, Others 0), opposite-bound Live mirroring, and cross-line interchange crossover.
4. **Possession Accounting:** Verify co-sharing legality (1 PM alone, 1 PC + $\le 3$ C, or $\le 4$ C; never 2 PCs) and nominal capacity limits ($s_{lw}$).
5. **Local Night & Workfront Rules:** Validate that weekly local night indices do not exceed contract caps ($K_c$) and concurrent activities do not exceed workfronts ($f_c$).
6. **Scenario Constraints (A, B, C):** Verify that Scenario A forbids location excess; Scenario B forbids planned date overrun; Scenario C enforces line ECLO windows ($\le 2$ weeks) and $\le 1$ excess slot per location/week.
7. **Official Score Reconciliation:** Exact calculation of activity overrun penalty ($P$), excess slots ($V$), and ECLO count ($E$) matching the official scoring formula.
8. **Artifact Round-Trip:** Export and re-read the 3 official CSV files (`SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, `RESULTS.csv`).
9. **Calendarisation:** Every access receives one eligible Singapore service date in its week; shared groups align; date-level capacity/protection and frozen pins pass.
10. **Recurrence:** Deterministic generated jobs cover carry-in and horizon-end boundaries with no gap greater than `max_interval_days`.
11. **Replanning/Churn:** Occurred, completed, in-progress and locked work does not move; remaining workload stays complete; each selected A/B/C score is optimised before churn.
12. **Manual Edits:** Preflight detects every hard-rule family; stale/frozen edits fail; save revalidates; infeasible repair retains the published plan.
13. **Explanations/Chat:** Fact packs match stored diffs/counterfactuals; tools are read-only and role-scoped; unsupported claims and provider outage use the deterministic fallback.

*Validation Provenance:* The official validator tool is not present in the supplied pack; local validation reports `validator_unavailable` until the official checker is supplied by the organisers.

Operational checks do not turn an enriched run into an official submission. Any generated ID or operational-only field makes the run ineligible for the exact official bundle.

## 2. Active PS1 Local Verification

Verification date: **19 September 2026**.

```sh
python -m pytest backend/tests/test_data_layer.py backend/tests/test_ps1_scoring_validation.py backend/tests/test_ps1_solver.py backend/tests/test_ps1_database.py backend/tests/test_ps1_explanations.py backend/tests/test_ps1_chat_tools.py backend/tests/test_ps1_chat_api.py backend/tests/test_ps1_chat_security.py backend/tests/test_ps1_chat_fallback.py -q
```

Result: **78 passed** (21 data/topology/I/O tests, 18 scoring/validation/solver tests, 12 persistence tests, and 27 grounded chatbot & explanation tests). Additionally, `cd nebula-ui && npm test` passes 21/21 frontend tests and `npm run build` succeeds cleanly.


---

## 3. Operational Enrichment Acceptance Matrix (Planned)

| Area | Required cases |
|---|---|
| Global nights | Week boundary/timezone; local-night independence; shared group equality; ineligible/closed dates; date-level capacity/protection; infeasible date subproblem feeding weekly repair. |
| Recurrence | Composite interchange key; deterministic IDs; carry-in/out; early service; policy revision/suspension; missing template; impossible cadence with no dropped job. |
| Dynamic updates | Emergency insertion; capacity/calendar outage; remaining-yield credit; each A/B/C policy; zero/default score tolerance; explicit tolerance; persistent access matching; label symmetry. |
| Manual moves | Frozen past, release/deadline/precedence, possession mix/capacity/protection, ECLO window, workfront, recurrence gap, warnings, stale revision and transactional rollback. |
| Explanations/chat | Displaced and unchanged activities; measured alternative; missing data; prompt injection; cross-tenant/role denial; no arbitrary SQL/action; provider timeout and deterministic fallback. |

---

## 4. Legacy Synthetic Baseline Verification (Historical Scaffold)

Verification date: **13 September 2026**.  
*Scope:* Legacy single-night CP-SAT solver and synthetic 9-rule validator.

### Executed Results (Historical Prototype)

| Check | Result |
|---|---|
| Complete Python suite | **135 passed** |
| CP-SAT full-solver and validator tests | **Passed with OR-Tools installed** |
| Generator scenario validation and JSON round trips | **Passed** |
| Canonical JSON regeneration | **No diff** |
| Repository JSON parsing | **5 files parsed** |
| JavaScript module syntax | **11 modules passed** |
| Fresh canonical FastAPI proposal and commit | **Passed** |
| Tampered automatic/manual proposal revalidation | **Rejected as expected** |
| Browser Playwright smoke flow | **Not run: optional Playwright package is not installed** |

Pytest emits one third-party deprecation warning from Starlette's TestClient
type alias. It does not represent a solver or application test failure.

## Canonical solver execution

Command:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8
```

Observed result:

- strict status: `INFEASIBLE`;
- recovery status: `OPTIMAL`;
- independent validation: passed constraints 1 through 9;
- scheduled priority: 23;
- scheduled count: 7;
- moved existing allocations: 0;
- movement: 0 minutes;
- preferred-time deviation: 115 minutes;
- latest completion: minute 180, or 04:15 SGT.

Scheduled request IDs: `R09`, `R10`, `R01`, `R02`, `R12`, `R03`, `R06`.

Deferred request IDs: `R04`, `R05`, `R07`, `R08`, `R11`. R05 has the
individually proved cause that required equipment Q04 is unserviceable. The
other requests were excluded by the globally optimal hard-constraint
combination; no single cause was fabricated.

## Coverage highlights

- Explicit planning-night selection and allowed dates.
- Nullable preferred starts and cross-night preference deviations.
- Complete four-phase durations and the 20-minute handback buffer.
- Sector blackouts, protected footprints and fixed transit.
- Traction-power and work-type transitions.
- Specialist qualification, availability and double-booking.
- Named equipment and pooled capacities.
- Engineer, equipment and vehicle travel.
- Dependencies and handover buffers.
- Frozen/locked commitments and movement minimisation.
- Exact, range, any-time and deferral behavior.
- Mandatory work in strict and recovery modes.
- Priority and equal-priority recovery selection.
- `OPTIMAL`, `FEASIBLE`, `INFEASIBLE` and `UNKNOWN` orchestration behavior.
- Independent rejection of deliberately corrupted exports.
- Canonical API generation, manual staging and atomic publication recheck.
- V0 and V1 remain runnable within their documented teaching boundaries.

## Browser-test limitation

`python scripts/browser_smoke.py` was attempted and stopped immediately with
`ModuleNotFoundError: playwright`. No browser result is claimed. The script
remains optional and explicitly uses `data/demo_data.json` to test the legacy
scaffold flow; canonical solver/API behavior is covered by FastAPI integration
tests.

All datasets and results described here are synthetic. Passing these checks is
not approval for live railway operations.
