# Canonical scheduler verification report

Verification date: **13 September 2026**.

## Executed results

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
