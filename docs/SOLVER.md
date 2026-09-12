# NebulaX solver handover

## Authoritative inputs

The canonical implementation is `backend/app/services/cp_sat.py`. It uses:

- `constraints_lp_setup.md` for the nine approved constraint families;
- `data/comprehensive_synthetic_data.json` for the canonical mock data;
- `scripts/generate_synthetic_dataset.py` as the source that generates that JSON;
- `backend/app/services/full_validator.py` for independent post-solve checking.

All inputs are synthetic. A solver result is a prototype planning aid and is
not approval for live railway operations.

## Educational version progression

| Version | Purpose | Difference from the preceding version |
|---|---|---|
| V0 | Basic integer start/end variables, full job duration, engineering-window containment and frozen starts | Starting model |
| V1 | Dependency/handover ordering and opposed traction-power separation | Adds sequencing and power state to V0; it does not implement all nine rules |
| Full | Canonical strict/recovery scheduler and independent validation | Adds every approved constraint, named and pooled resources, lexicographic objectives, controlled statuses and backend integration |

V0 and V1 remain separate learning artifacts in `data/solver_v0.py` and
`data/solver_v1.py`. They should not be expanded until they become duplicate
copies of the full solver.

## CP-SAT syntax used in the full solver

CP-SAT means Constraint Programming – Satisfiability. It searches integer and
Boolean decisions while enforcing declared rules.

- `model.new_bool_var(...)` creates a variable whose value is `0` or `1`.
  NebulaX uses it for choices such as whether a recovery-mode job is present.
- `model.new_int_var_from_domain(...)` creates an integer variable restricted
  to an allowed set. Start variables use the configured five-minute grid.
- `model.new_optional_interval_var(start, duration, end, present, ...)` creates
  a time interval that exists only when `present == 1`.
- `constraint.only_enforce_if(condition)` makes a constraint conditional. For
  example, a deferred job does not consume an engineer.
- `model.add_no_overlap(intervals)` prevents one named person or item of
  equipment from being used by overlapping work.
- `model.add_cumulative(intervals, demands, capacity)` limits pooled demand at
  every moment, such as five technicians shared across concurrent jobs.
- `model.add_abs_equality(distance, start - baseline)` calculates absolute
  movement or preference deviation without allowing a negative distance.

The solver measures time as integer minutes from the selected engineering
window's start. This keeps the model small while the exported result retains
timezone-aware ISO timestamps.

## Two solving modes

`solve(...)` always attempts strict mode first. Strict mode sets every selected
request's presence Boolean to `1`; therefore every request must be scheduled.

Recovery runs only after CP-SAT proves strict mode `INFEASIBLE`. It changes
eligible deferrable requests to optional intervals. Mandatory, non-deferrable,
approved and locked/frozen work remains required. No safety or operational
constraint becomes soft.

Status meanings are precise:

- `OPTIMAL`: a valid schedule was found and every objective stage was proved
  best under the documented hierarchy.
- `FEASIBLE`: a valid schedule was found, but at least one objective stage was
  not proved best before the limit.
- `INFEASIBLE`: CP-SAT proved that no schedule satisfies the hard constraints.
- `UNKNOWN`: the limit ended without a solution or an infeasibility proof.
- `MODEL_INVALID`: OR-Tools rejected the constructed model.

Variable values are read only after `OPTIMAL` or `FEASIBLE`. `UNKNOWN` never
triggers recovery because it is not proof of infeasibility.

## Nine hard constraints

| # | Rule | Main full-solver implementation | Independent check |
|---|---|---|---|
| 1 | Engineering Window & Handback | Start domains, complete phase duration and usable horizon in `build_model` | Duration, grid, window and 20-minute clearance |
| 2 | Sector Availability & Safety Footprint | Fixed-interval avoidance and pairwise footprint separation | Blackouts, fixed unavailability, transit and overlaps |
| 3 | Work & Traction-Power Compatibility | Power/work lookup plus conditional transition separation | Common-zone compatibility and transition guards |
| 4 | Resource Requirements, Qualification & Capacity | Role assignment Booleans, availability, `NoOverlap` and `Cumulative` | Qualifications, exact equipment, availability and pool load |
| 5 | Resource Transfer / Travel Time | Directional pairwise separation for shared named resources | Consecutive assignment and directional matrix lookup |
| 6 | Dependencies & Required Sequence | Presence implication and buffered predecessor completion | Predecessor presence and handover time |
| 7 | Booking Commitment & Freeze Horizon | Fixed allocations and movement variables | Approved presence and unchanged frozen/locked fields |
| 8 | Request Timing Flexibility & Deferral Eligibility | `EXACT`, `RANGE`, `ANY_TIME`, dates and recovery presence | Date/range/exact semantics and permitted omission |
| 9 | Service-Critical / Mandatory Work | Mandatory presence fixed to `1` in both modes | Mandatory request presence |

Each numbered check produces a separate pass/fail record. A CP-SAT result is
described as constraint-valid only when all nine independent checks pass.

## Lexicographic objectives

Lexicographic means completing one objective, fixing its proved optimum, then
optimising the next. It avoids an unsafe weighted sum in which many minor gains
could outweigh one important scheduling decision.

Strict mode minimises, in order:

1. count of moved existing unlocked allocations;
2. total movement minutes;
3. deviation from non-null preferred starts;
4. latest completion minute as a deterministic tie-breaker.

Recovery mode optimises, in order:

1. maximum scheduled `urgency_score` total, after mandatory presence has
   already been enforced as a hard rule;
2. maximum request count;
3. minimum moved existing-allocation count;
4. minimum movement minutes;
5. minimum deviation from non-null preferred starts;
6. minimum latest completion minute.

A null `preferred_start` creates no deviation variable or artificial penalty.
Each stage reports its incumbent value, best bound and relative optimality gap.

## Determinism and time limits

The prototype uses one CP-SAT worker and random seed `17`. One worker provides
stable demonstrations at the cost of not using parallel search. Each strict or
recovery mode has an eight-second default limit; sequential objective stages
share that mode limit.

## Run the canonical solver

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8
```

For JSON output:

```sh
python -m backend.app.services.cp_sat --planning-date 2026-09-14 --time-limit 8 --json
```

The planning night is a required command-line argument. Library and backend
calls may use the explicitly configured `metadata.planning_date`.

## Backend integration

`backend/app/services/scheduler.py` is the API seam. `cp_sat` results are
already independently checked by the full validator. The older `demo_search`
engine remains paired with the older lightweight checker and demo dataset.

The application seeds fresh databases from `DATASET_PATH`, which defaults to
the comprehensive dataset. A new database filename is used so an existing
starter database is preserved. Proposal commit repeats full validation before
writing allocations.

## Prototype assumptions and limitations

- A missing different-sector travel pair uses
  `planning_rules.different_site_transfer_minutes`. This is a declared
  synthetic fallback, not invented operational route data.
- Required named equipment IDs cannot be substituted.
- Existing vehicle assignments are preserved. Requests do not currently have
  a field that authorises the solver to allocate a new vehicle.
- Vehicle transit is fixed input; the solver does not choose routes.
- One solve covers one engineering night and jobs are unsplittable.
- Deferred global-conflict explanations are intentionally cautious when no
  single cause has been proved.
