# Optimisation teammate: your starting point

## Stable interface

```python
result = solve(snapshot, time_limit=8)
```

Your result must include `status`, `engine`, `allocations`, `message` and `elapsed_seconds`. Successful results can also include `objective`. Each allocation has `request_id`, `start`, `end`, `engineer_id`, `equipment_ids` and `locked`.

The API chooses the configured implementation through `services/scheduler.py`. It rechecks the output before making it publishable. Do not put HTTP calls, SQL writes, login code or frontend formatting inside the optimisation module.

## The two implementations are not equivalent in scale

`demo_search.py` is a small reference search. It explicitly enumerates start-time/engineer candidates, prunes using the rule checker, and minimises preference deviation. It is capped at six pending requests. It can return a feasible incumbent when its time limit expires, or `UNKNOWN` if it has not found one. It is intentionally labelled as NOT CP-SAT.

`cp_sat.py` is the OR-Tools implementation for your team to validate and extend. It currently has a 40-active-request guard; that is a development guard, not a benchmarked capacity claim. OR-Tools was unavailable in the build environment, so its seven tests were not executed here.

Both solve a finite five-minute start-time model. `OPTIMAL` means optimal under that model/objective, not globally best under real railway operating rules.

## Current CP-SAT model

### Variables

For each active request $j \in \mathcal{J}$:

- integer start and end minutes ($start_j, end_j$) measured from the first seeded engineering window;
- a lead-engineer index;
- a fixed-duration interval ($I_j$) equal to setup + work + test + handback ($D_j$).

For engineering vehicles $v \in \mathcal{V}$:
- transit intervals $I_{v,s} = \text{IntervalVar}(start_{v,s}, \tau_{v,s}, end_{v,s})$ representing dynamic sector occupancy along predefined depot corridors.

For a new request, `candidates.py` enumerates start/engineer pairs satisfying individual window, blackout, skill, equipment serviceability and resource-availability checks. These form an allowed-assignment table. Already committed requests get one fixed candidate. All entities are typed and validated via `backend/app/models.py`.

### Constraints

- All active requests are assigned exactly once; there is no optional/urgency logic yet.
- Existing commitments are fixed ($y_{\text{fixed}} = 1$).
- Exclusive protected footprints cannot overlap: $\text{NoOverlap}(\{I_j \mid s \in \Omega_j\})$.
- Traction power sector compatibility: opposed power states (`ON` vs `OFF`) in any shared affected zone ($z \in \mathcal{Z}$) require the synthetic transition guard; tasks with `NONE` require no isolation.
- Blackout & track closure exclusions: no task or vehicle transit may intersect an active blackout period ($b \in \mathcal{B}$) in its sectors.
- Vehicle transit corridor interlocking: transit intervals and stationary worksites in sector $s$ are mutually exclusive: $\text{NoOverlap}(\{I_{v,s}\} \cup \{I_j\})$.
- Morning sweep revenue protection: tasks must finish before window close minus $T_{\text{buffer}}$ (e.g. 20 minutes).
- Assignments sharing a lead engineer or equipment must be separated, including the flat inter-site transfer gap when their work sectors differ.
- Predecessors must end before dependent jobs start, plus required handover buffer: $start_j \ge end_p + \Delta_{p,j}$.
- A cumulative constraint limits simultaneous general-technician demand to pool capacity ($C_{\text{TECH}}$).
- All job phases share the package's resources and power requirement in this starter.

Resource transfer is a simple pairwise separation assumption, not a route model. The first arrival is assumed reachable. Technician travel is not represented. Equipment IDs are required physical units, not a flexible choice among equipment types.

### Objective

For pending requests, minimise:

```text
(number_of_active_jobs + 1) * total_absolute_start_deviation_minutes
  + count_of_nonpreferred_engineer_assignments
```

The coefficient ensures that one minute of total time deviation dominates every possible engineer-preference penalty in this small model. This is deliberate priority ordering, not an estimate of money or safety risk.

The initial fixture produces a total weighted objective of 475 with R03 at 02:30 and R04 at 02:35 using E01. The reference JSON is not imported by either solver.

## First tasks

1. Install `requirements-cpsat.txt`, set `SOLVER_ENGINE=cp_sat`, restart and run `python -m pytest -q`.
2. Verify the reference result and engineer-absence case through both solver tests and the website.
3. Add tests before extending constraints. A rule must be added to both the CP-SAT model and the checker.
4. Generate two or three meaningfully distinct alternatives; do not repeatedly return the same assignment with a different ID.
5. Add explicit optional/priority handling only after agreeing the policy with the team. Infeasible mandatory work must not disappear silently.

Later extensions include solver-side transit corridor scheduling, movable approved allocations with disruption penalties, richer resource assignments, operator-supplied compatibility rules and route reservations. Do not add a shortest-path route and claim it is authorised railway access.

## Status discipline

- `OPTIMAL`: objective proven optimal for the encoded model/domain.
- `FEASIBLE`: valid incumbent; optimality not proved.
- `INFEASIBLE`: infeasibility proved for the encoded model/domain (or an empty required domain/dependency contradiction).
- `UNKNOWN`: search did not establish a solution or impossibility in the allowed time.
- `MODEL_INVALID`: model formulation error; do not publish.
- `UNAVAILABLE`: OR-Tools is not installed.
- `REVIEW_REQUIRED`: invalid locked baseline or a missing required rule.
- `VALIDATION_FAILED`: the checker rejected a candidate; do not publish it.
- `LIMIT`: starter size guard reached; not a mathematical infeasibility result.

The demo search reuses the checker as its feasibility evaluator; it is not an independent implementation of every rule. The CP-SAT model has separate global constraint code, but shares simple helpers and candidate screening. Shared code can contain shared mistakes. Domain validation and additional tests remain necessary.

## References

- [OR-Tools scheduling example](https://developers.google.com/optimization/scheduling/job_shop)
- [CP-SAT modelling/status guide](https://developers.google.com/optimization/cp/cp_solver)
- [Python model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html)
