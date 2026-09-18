# PS1 solver

This package implements the accepted weekly PS1 accounting formulation with one
shared CP-SAT model builder and scenario-specific policies for A, B, and C.

From Python:

```python
from backend.app.io import load_problem_from_directory
from backend.app.ps1 import PS1SolveOptions, export_solve_result, solve_ps1

problem = load_problem_from_directory("data")
result = solve_ps1(
    problem,
    "A",
    PS1SolveOptions(time_limit_seconds=60, feasibility_time_limit_seconds=10),
)
if result.has_incumbent:
    export_solve_result(result, "outputs/A")
```

From the repository root:

```bash
python -m backend.app.ps1 \
  --data-dir data \
  --scenario all \
  --output-dir outputs \
  --time-limit 60
```

Each scenario directory contains exactly `SCHEDULE_ACCESS.csv`,
`SCHEDULE_OCCUPANCY.csv`, and `RESULTS.csv`. The JSON result also contains the
score components, ECLO access count and weekly timing, solver metrics, and local
validation provenance.

The row-based validator independently rechecks the understood workload,
release, predecessor, local-night, workfront, core occupancy, legal mix,
capacity, deadline, and ECLO-window rules. Results and scoring are reconstructed
from access/occupancy rows, and written bundles are re-read using strict schemas.
The supplied pack does not include the organiser's checker, and the accepted
specification leaves the group-dependent buffer/closure compatibility predicate
unresolved. The result therefore reports `safety_status="unverified"` and
`official_checker_status="unavailable"`; it does not claim official validation
parity.
