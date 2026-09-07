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

The full integer formulation chooses $\{y_j, s_j, e_j, x_{jeq}, m_j, \delta_j\}$:

- $y_j \in \{0, 1\}$: Binary task acceptance variable ($1 = \text{scheduled tonight}, 0 = \text{deferred}$).
- $s_j, e_j \in [0, T^{use}]$: Start and completion minute ($e_j = s_j + d_j$).
- $I_j$: Optional interval variable defined over $[s_j, d_j, e_j]$ guarded by $y_j = 1$.
- $x_{jeq} \in \{0, 1\}$: Assignment of specialist engineer $e$ to competency role $q$ on job $j$.
- $m_j \in \{0, 1\}$: Movement indicator for approved jobs outside freeze horizon ($1 = \text{moved from } \bar{s}_j$).
- $\delta_j \ge |s_j - p_j|$: Absolute deviation from preferred start minute.
- $C_{\max} \ge e_j$: Latest completion minute across scheduled work orders.
- $I_{v,s}$: Optional transit corridor interval for engineering vehicle $v \in \mathcal{V}$ across sector $s$ with duration $\tau_{v,s}$.

All domain entities are typed and validated via `backend/app/models.py`.

### The 9 Hard Constraints

1. **Engineering Window & Handback:** $s_j \ge 0$, $e_j \le T^{use} = T - B$ (where $B$ is the handback buffer, e.g. 20 min).
2. **Sector Availability & Safety Footprint:**
   - Fixed sector unavailabilities ($\mathcal{B}_s$): $y_j = 1 \implies (e_j \le \alpha_{sb}) \lor (s_j \ge \beta_{sb})$.
   - Mutually exclusive protected footprints ($C^{sector}_{jk} = 1$): $(e_j \le s_k) \lor (e_k \le s_j)$.
3. **Work & Traction-Power Compatibility:** Opposing traction power (`ON` vs `OFF`) in common feeding zones ($C^{power}_{jk}=1$) or work incompatibilities ($C^{work}_{jk}=1$) require transition separation $g_{jk}$: $(e_j + g_{jk} \le s_k) \lor (e_k + g_{kj} \le s_j)$. Tasks requiring `NONE` are electrically neutral.
4. **Resource Requirements, Qualification & Capacity:**
   - Specialist engineers: $\sum_e x_{jeq} = n_{jq} y_j$, $x_{jeq} \le Q_{eq}$, $\text{NoOverlap}(\{I_{je}\})$, and no overlap with engineer absence windows $\mathcal{B}_e$.
   - Pooled manpower & equipment: $\text{Cumulative}(\{I_j\}, \{c_{jr}\}, C_r)$ ensures demand at minute $t$ never exceeds capacity $C_r$.
5. **Resource Transfer / Travel Time:** Assigned engineers/equipment moving between consecutive jobs must observe inter-site travel times: $(e_j + \tau^E_{jk} \le s_k) \lor (e_k + \tau^E_{kj} \le s_j)$.
6. **Dependencies & Required Sequence:** Prerequisite enforcement $y_j \le y_p$ and handover clearance margin $s_j \ge e_p + \Delta_{pj}$ for all $p \in Pred(j)$.
7. **Booking Commitment & Freeze Horizon:** Approved jobs remain scheduled ($A_j = 1 \implies y_j = 1$); frozen jobs within $H^{freeze}$ cannot move ($L_j = 1 \implies s_j = \bar{s}_j$); approved non-frozen jobs may move only if necessary ($m_j = 1$).
8. **Request Timing Flexibility & Deferral Eligibility:** Accommodates `EXACT`, `RANGE`, and `ANY_TIME` modes. Non-deferrable work enforces $D_j^{allow} = 0 \implies y_j = 1$.
9. **Service-Critical / Mandatory Work:** Hard rule $M_j = 1 \implies y_j = 1$. Solver may never drop safety-critical repairs to resolve conflicts.

### Lexicographic Objective Architecture

The formulation recommends solving in **strict lexicographic priority stages**:

1. **Stage 0:** Satisfy all 9 hard constraints.
2. **Stage 1 (Schedule Stability):** $\min \sum_{j: A_j=1, L_j=0} m_j$ (minimize disturbance to approved bookings).
3. **Stage 2 (Optional Urgency):** $\max \sum_j U_j y_j$ (maximize completed non-mandatory work weighted by urgency $U_j \in [1, 5]$).
4. **Stage 3 (Requester Preferences):** $\min \sum_j F_j \delta_j$ (minimize total absolute deviation from preferred times).
5. **Stage 4 (Handback Margin):** $\min C_{\max}$ (maximize spare margin $\text{Slack} = T^{use} - C_{\max}$).

The starter implementation aggregates priority terms into a weighted single-solve objective:

```text
(number_of_active_jobs + 1) * total_absolute_start_deviation_minutes
  + count_of_nonpreferred_engineer_assignments
```

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
