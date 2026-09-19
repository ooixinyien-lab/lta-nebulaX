# PS1 Solver Formulation Review

**Official weekly formulation accepted 18 September 2026; operational enrichment addendum accepted 19 September 2026.**

The user accepted this mathematical formulation as the implementation basis. The unresolved official-rule details remain explicit below. This document does not change the authoritative [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md). The source handout is [PS1_README.md](../NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md), especially sections 2.4–2.7. The active implementation now lives in `backend/app/ps1/`; this review records the intended formulation and later workflow extensions.

Build one binary/integer scheduling model with three scenario policies. An ordinary continuous LP could assign fractions of an access or possession; those are not valid output decisions. The established accounting rules below have an integer linear formulation. OR-Tools CP-SAT is the intended implementation technology and also supports logical and maximum constraints directly.

The shared entry point is `solve_ps1(problem, scenario, options) -> PS1SolveResult`. A request for all scenarios invokes the same implementation three times with scenario A, B and C. Each invocation creates its own model, decision variables, search state and result; scenario constraints must not leak between runs. Reuse the common model-building code and add the selected policy and objective. Do not maintain three copied solver implementations. The outcome is three separately optimised schedules, each with its own three-CSV answer bundle.

The objectives and accounting below follow the adoption plan's reconciliation of the handout. A fully verified official model still needs the absent official checker: exact closure/co-sharing compatibility, interchange protection boundaries, and the predecessor week comparator remain unresolved. Keep those policies explicit; do not claim that the equations below alone establish official safety compliance.

The handout's displayed A/C equations omit the activity multiplier, whereas its worked examples and detailed per-activity score definition include it. This document follows the latter, as the adoption plan directs. The notation is consistent with AGENTS.md: V means excess possession slots and E means ECLO accesses. There is no separate additive contract-overrun penalty.

The score comes from three quantities:

\[
P=\sum_i a_{c(i)}m_i L_i,\qquad
V=\sum_{\ell,w}\max(0,U_{\ell w}-s_{\ell w}),\qquad
E=\sum_{i,w}e_{iw}.
\]

Here L_i is an activity's nonnegative lateness in calendar days, measured against its contract's planned completion date; U is occupied possession groups and s is nominal supply. The contract weight a is 100, 10 or 1 for contract priorities 1, 2 or 3. The activity multiplier m is 1.3, 1.2 or 1.0 for activity priorities 1, 2 or 3.

| Contract priority | Activity priority 1 | Activity priority 2 | Activity priority 3 |
|---|---:|---:|---:|
| 1 | 130 points/day | 120 points/day | 100 points/day |
| 2 | 13 points/day | 12 points/day | 10 points/day |
| 3 | 1.3 points/day | 1.2 points/day | 1 point/day |

For example, a priority-3 contract's priority-1 activity finishing seven days late costs 9.1. Two such activities each finishing seven days late cost 18.2, even though their contract has only seven days of reported overrun. The contract's finish is useful for RESULTS.csv; the objective sums activity penalties.

One occupied group consumes one slot at one location/week, whether it contains one activity or four legal co-sharers. If an access causes one excess slot at each of three locations, V increases by three and its excess cost is 21. An ECLO access contributes one to E, irrespective of its number of occupancy rows or affected lines. Its ECLO cost is five. These coefficients are prescribed by the handout, not tuning parameters or monetary prices.

The three objectives are:

\[
\min S_A=P,\qquad
\min S_B=7V+5E,\qquad
\min S_C=P+7V+5E.
\]

| Policy | A: strict supply | B: strict schedule | C: balanced |
|---|---|---|---|
| Planned-date lateness | Allowed and scored | Forbidden | Allowed and scored |
| Excess per location/week | Zero | No separate published hard excess cap | At most one |
| ECLO | Forbidden | Any eligible horizon week | One selected span of at most two weeks per affected line |
| Workload, safety, releases, dependencies, contract caps, workfronts | Hard | Hard | Hard |

The mathematical definitions and common constraints follow. Indices refer to the input instance, rather than hardcoded public IDs:

| Symbol | Meaning |
|---|---|
| I, W | Activities and weeks 1,...,H; H=30 in the public instance |
| c(i), I_c | Activity's contract/type budget group and activities in that group |
| L, R | Locations and railway lines |
| d_i, r_i | Required workload and earliest permitted week |
| F_i | Core working locations: traversed tunnels plus endpoint/intermediate platforms |
| A_i | Lines affected by an activity, including applicable Live interchange protection |
| K_c, f_c | Granted weekly local nights and workfronts per local night |
| s_lw | Nominal possession supply, read from the instance; flat across weeks in the supplied schema |
| t_0, D_c | Horizon start date and contract planned completion date |
| delta_c | Integer calendar days from t_0 to D_c |
| I_l | Activities whose core footprint contains location l |
| G_lw | Candidate possession labels local to location l and week w |

Read H and t_0 from the parameters CSV. Do not extend the horizon silently. Map planned starts to their containing planning week, consistent with the weekly rule. Keep exact days for deadlines: converting a Wednesday deadline to its containing week would incorrectly permit completion on the following Sunday in B.

For a finite, safe group-index bound, at most |I_l| occupied groups are needed at any location/week: each activity has at most one access that week. A may reduce the bound to min(|I_l|,s_lw), and C to min(|I_l|,s_lw+1). B's lack of a policy excess cap does not require infinitely many decision variables. Supply counts core occupancy groups; protection is derived separately according to the safety policy.

Use the following binary decision variables:

| Variable | Equals one when... |
|---|---|
| x_iw | Activity i receives an access in week w |
| e_iw | That access uses ECLO |
| z_iwn | That access uses local contract/type night n, where n=1,...,K_c(i) |
| y_iwlg | That access occupies group g at core location l |
| u_lwg | The local possession group is occupied |
| h_iw | Week w is the activity's final access week |

First, require full workload, a valid ECLO flag, and release compliance:

\[
e_{iw}\le x_{iw},\qquad
\sum_{w\in W}(2x_{iw}+e_{iw})\ge 2d_i,\qquad
x_{iw}=0\quad(w<r_i).
\]

The binary x permits at most one access per activity/week. A standard access contributes two doubled units; an ECLO access contributes three. ECLO yields 1.5 units total, not 1+1.5. Keep the workload inequality: equality can exclude valid rounding. For example, three ECLO accesses deliver 4.5 units toward a four-unit requirement.

Next, assign each scheduled access to exactly one local night and limit concurrent teams:

\[
\sum_{n=1}^{K_{c(i)}}z_{iwn}=x_{iw},\qquad
\sum_{i\in I_c}z_{iwn}\le f_c\quad\forall c,w,n.
\]

A contract with three allowed nights and two workfronts can therefore schedule up to six distinct activities in a week, but any one activity still gets at most one access. Do not replace this with an at-most-three-activities rule. Retain explicit local-night variables for the first implementation; the adoption plan treats aggregation to K_c*f_c as a possible later reduction requiring semantic confirmation.

For every core location l in F_i, assign exactly one local possession group whenever the activity runs:

\[
\sum_{g\in G_{\ell w}}y_{iw\ell g}=x_{iw}.
\]

At each location/week/group, let M, Q and C be the sums of assigned y variables belonging to PM, PC and C roles respectively. Enforce:

\[
M+Q\le u,\qquad 4M+Q+C\le4u,\qquad u\le M+Q+C.
\]

These inequalities allow exactly one PM alone, one PC with at most three C, or one to four C. They forbid two PCs and ensure u is one exactly when the group has members. Define:

\[
U_{\ell w}=\sum_g u_{\ell wg},\qquad
v_{\ell w}=\max(0,U_{\ell w}-s_{\ell w}),\qquad
V=\sum_{\ell,w}v_{\ell w}.
\]

For CP-SAT, use an exact max relation. For a purely integer linear representation, introduce binary b_lw and constant B_lw=max(s_lw,|G_lw|), with nonnegative integer v_lw:

\[
v_{\ell w}\ge U_{\ell w}-s_{\ell w},\quad
v_{\ell w}\le U_{\ell w}-s_{\ell w}+B_{\ell w}(1-b_{\ell w}),\quad
v_{\ell w}\le B_{\ell w}b_{\ell w}.
\]

When b=0 these force v=0 and U<=s; when b=1 they force v=U-s>=0. The result is exact even during feasibility-only search, when there is no objective pressure to tighten excess variables.

Possession labels and local night indices are independent. Do not require one group label throughout an activity's route, equate a group label with an access_night, or synchronize local labels across contracts or locations. The official sample contains both changing group labels along a route and co-sharing activities with different local night indices.

To compute exact completion using only linear equations, select the actual final access week:

\[
\sum_w h_{iw}=1,\qquad h_{iw}\le x_{iw},\qquad
x_{iw}\le\sum_{t=w}^{H}h_{it}\quad\forall i,w.
\]

The selected final week must contain an access, and no access may occur after it. Thus:

\[
T_i=\sum_w w h_{iw},\qquad
\operatorname{finish}_i=t_0+(7T_i-1)\text{ days}.
\]

Week 1 ends on 2027-01-10 in the public instance. A contract finishes at the maximum of its activity finishes. Its RESULTS.csv overrun is the positive difference from planned_completion_date, not contract_completion_date.

Precompute the constant lateness if activity i finishes in week w:

\[
\lambda_{iw}=\max(0,7w-1-\delta_{c(i)}).
\]

Then the exact lateness and objective are linear expressions:

\[
L_i=\sum_w\lambda_{iw}h_{iw},\qquad
P=\sum_{i,w}a_{c(i)}m_i\lambda_{iw}h_{iw}.
\]

Alternatively CP-SAT can use exact maximum constraints to derive last access and lateness directly. Do not use loose lower bounds alone for reported completion in feasibility search or Scenario B, where a lateness objective will not correct inflated auxiliary values. The one-final-week formulation above avoids that issue.

For each predecessor edge p->i, the adoption plan's provisional strictly-later-week rule becomes:

\[
x_{iw}\le\sum_{t=1}^{w-1}h_{pt}\quad\forall w.
\]

The empty sum at week 1 is zero. In words, a successor can run only once its predecessor's final access is in an earlier week. Keep this comparator in a named policy: the sample supports it, but the absent checker is needed to establish whether any same-week succession is legal.

Safety must additionally enforce the documented protection rules: Live has up to two buffer sectors on each side, opposite-bound mirroring, and applicable interchange protection on the other line; Consist has one sector each side without mirroring; Others has none. Clamp buffers at termini and identify interchange stations by (line_code,station_id).

Core occupancy and protection are different objects. The sample exports core locations only, including for Live activities. Do not automatically add buffer/mirrored/cross-line protection as core occupancy rows, extra workload, or extra scored possession groups. Maintenance is already reflected in nominal supply; do not subtract it again.

The missing piece is the precise compatibility relation between protection footprints and local possessions, including how co-sharing exemptions propagate. Denote that required relation abstractly by Safety(x,y;policy). This is a specification boundary, not a constraint that may be omitted from a production solver. A blanket x_iw+x_jw<=1 whenever two protection footprints intersect rejects the supplied sample and is not justified. Inventing globally synchronized nights would also contradict the observed accounting semantics. Implement understood topology and a clearly identified policy boundary; resolve and test the remaining relation against the checker or organiser clarification before claiming full official validation.

With all common rules above, the three scenario formulations are compact.

Scenario A minimizes P subject to the common rules and:

\[
U_{\ell w}\le s_{\ell w}\quad\forall\ell,w,\qquad
e_{iw}=0\quad\forall i,w.
\]

There are no supply or ECLO purchases. The optimiser chooses which activities must finish late while preserving full delivery and all hard rules. V and E are necessarily zero.

Scenario B minimizes 7V+5E subject to the common rules and:

\[
7T_i-1\le\delta_{c(i)}\quad\forall i.
\]

Equivalently, forbid final weeks whose Sunday exceeds the planned deadline. There is no additional policy cap on v, and ECLO is not restricted to a two-week window. Every activity finishes by its contract's deadline, so P is zero. Flexible location supply does not relax releases, dependencies, workfronts, K_c, or one access/activity/week. B can still be infeasible.

Scenario C minimizes P+7V+5E subject to the common rules and:

\[
U_{\ell w}\le s_{\ell w}+1\quad\forall\ell,w.
\]

For ECLO windows introduce binary q_rt: line r selects a window starting in week t. Allow t in 1,...,H; a start in H represents a one-week window at the horizon boundary. Then:

\[
\sum_{t=1}^{H}q_{rt}\le1\quad\forall r,\qquad
e_{iw}\le q_{r,w-1}+q_{rw}\quad\forall i,w,r\in A_i,
\]

where q_r0=0. Every ECLO access affecting a line must lie in that line's selected start week or the following week. No ECLO means no window is required. Cross-line Live must satisfy both line constraints. These windows permit many activities to use ECLO in the same two weeks; they do not impose a two-access total per line. Read any amended C supply from the input, then apply the one-slot allowance.

For exact integer scoring, let n_i be 3, 2 or 0 for activity priorities 1, 2 or 3. Define:

\[
P_{10}=\sum_{i,w}a_{c(i)}(10+n_i)\lambda_{iw}h_{iw}.
\]

Minimize P_10 in A; 70V+50E in B; P_10+70V+50E in C. Divide the solver objective and comparable bounds by ten when reporting the published score. This scales every term equally and preserves all tradeoffs. Use integer priority lookups rather than converting the existing float-valued score_nudge property through floating-point arithmetic.

Do not substitute rigid priority stages or the handout's informal cost ordering for this weighted sum. The finite weights permit aggregate tradeoffs. Do not add rewards for early completion, utilisation or stability to the primary score; the handout lists diagnostics and possible extra features, but does not give these extra score terms.

An actual input example explains why this matters. A036 requires seven units from week 22, has a week-26 deadline, and costs 1.3 per late day. In A, seven standard weeks finish in week 28, costing 14*1.3=18.2 before any competition. In C, two ECLO accesses plus four standard accesses finish in week 27, costing 7*1.3+2*5=19.1. Acceleration is 0.9 worse in isolation. Network effects could change the overall comparison. In B, finishing within weeks 22–26 requires at least four ECLO accesses because 5+0.5E>=7. A059 independently requires at least two ECLOs in B, establishing a public-instance lower bound of 30 before excess supply. These are bounds and isolated comparisons, not proofs of an achievable full-network optimum.

The eventual coding handoff should proceed in these bounded steps, using this reviewed formulation together with the authoritative adoption plan:

1. **Inspect and reuse the current data layer.** Read AGENTS.md, the root adoption plan, the official PS1 README, domain_models.py, io.py, topology.py and test_data_layer.py. Reuse the existing ProblemInstance, typed output rows, ingestion/export functions and footprint APIs. Add new solver/scoring/validation modules under backend/app/ps1/; do not create a competing set of existing domain or I/O models merely because an older architecture table proposed those names. New domain/request/result schemas inherit PS1Base. Keep the legacy single-night solvers and unrelated API/frontend work out of scope.

2. **Implement independent scoring and artifact checks first.** From access and occupancy rows, reconstruct final weeks, exact dates, weighted activity lateness, excess occupied groups and ECLO rows. Test priority multipliers, weekday deadlines, co-sharing counts and a multi-location excess example. The supplied A sample reconstructs P=48.3, V=0, E=0; its separate contract-overrun total is 28 days. Label these reconstructed results, not official-validator output.

3. **Implement the shared accounting model on small fixtures.** Add workload/release constraints, exact final-week selection, explicit local nights and workfronts, local group packing, exact excess counting, and the named predecessor policy. Test ECLO rounding, one access/activity/week, two-workfront throughput, PM isolation, two-PC rejection, C/PC+C sharing, complete footprints, and exact completion during feasibility search. Keep unresolved safety semantics explicit; an accounting-only prototype must not be advertised as a complete feasible PS1 schedule.

4. **Integrate and verify protection compatibility.** Reuse core/protection calculations, audit their assumptions, and obtain authoritative answers for the open compatibility, cross-line and precedence details. Add fixtures for the sample's A074/A025 week-21 case, changing group labels along A004's footprint, and co-sharing A040/A042 with different local nights. Confirm core-only occupancy export and exact affected-line membership for C windows. Local tests alone do not establish parity with the absent official checker.

5. **Add all three policies to one model builder.** Implement A's no-ECLO/no-excess rules; B's exact hard dates and flexible supply; C's one-slot allowance and jointly chosen line windows. Test that B rejects late schedules even if its displayed supply cost is low; that C rejects two excess slots at any one location/week; and that C allows many ECLO activities within its two-week window but rejects ECLO outside it. Test cross-line Live against both windows and the horizon endpoints.

6. **Add bounded solving, exports and incumbent retention.** Establish a complete, validated feasible incumbent, then optimize the exact scaled score within one total time budget. Retain the best validated incumbent if improvement times out. Distinguish FEASIBLE, OPTIMAL, proven INFEASIBLE and UNKNOWN; neither greedy failure nor timeout proves infeasibility. Record validation provenance separately from solver status. Never relax hard rules or return partial workload as a successful solution. Return the typed result and derived ECLO summary specified below. Emit a separate three-CSV bundle for each scenario, using existing typed exports; derive RESULTS from the actual access rows. Re-read the exports and independently validate them.

7. **Optimize only after correctness evidence.** Measure first-feasible time and score/bound progress on the public data and perturbed fixtures. Then evaluate hints, local group-label symmetry breaking and targeted neighbourhood search. Keep all contracts/lines in the coupled model unless a decomposition is proved valid. Any secondary preference must preserve the primary official score. Run the targeted new suites plus backend/tests/test_data_layer.py; avoid bare pytest while legacy collection imports remain broken. Broaden testing when changes or failures justify it.

The three exact output schemas are unchanged:

```text
SCHEDULE_ACCESS.csv
activity_id,access_seq,week,eclo,access_night

SCHEDULE_OCCUPANCY.csv
activity_id,week,location_id,co_share_group

RESULTS.csv
scenario,contract_number,simulated_completion_date,overrun_days
```

Emit eclo as 0 or 1 and assign access_seq in chronological order. Group labels are arbitrary within their location/week scope. Completion claims require full workload, all adopted hard checks, export round-trip checks, and an explicit statement of whether the actual official validator was available. The current pack does not contain that validator.

The files serve different readers: SCHEDULE_ACCESS says which activity runs in which week, whether it uses ECLO, and which local contract/type night it uses; SCHEDULE_OCCUPANCY says where that access works and how it shares each location's possession; RESULTS gives each contract's finish date and overrun. RESULTS does not contain the complete score breakdown or ECLO totals.

Use a separate directory or downloadable bundle per scenario. For example, a run can have `A/`, `B/` and `C/` directories, each containing exactly the three files above. Solving all three scenarios therefore produces nine official CSVs. Do not add columns to the official schemas or insert an application summary as a fourth file in an official scenario bundle.

For the backend/application, return a typed `PS1SolveResult` inheriting PS1Base, with nested typed models for summaries. It should serialize to JSON when exposed by the API; the CSV bundles remain the official submission format. The proposed result fields are:

| Field | Required content |
|---|---|
| `scenario` | A, B or C |
| `status` | Solver result: OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN or MODEL_INVALID |
| `has_incumbent` | Whether a complete candidate schedule is available; its check results are separately reported in `validation` |
| `access_rows` | Existing AccessScheduleRow objects, mapped directly to SCHEDULE_ACCESS.csv |
| `occupancy_rows` | Existing OccupancyScheduleRow objects, mapped directly to SCHEDULE_OCCUPANCY.csv |
| `contract_results` | Existing ScenarioResultRow objects, mapped directly to RESULTS.csv |
| `score` | Weighted activity lateness P, excess slot count V, ECLO access count E, their applicable penalty contributions and scenario objective; include exact scaled integer score |
| `eclo_summary` | Counts and timing derived from actual ECLO access rows, as described below |
| `validation` | Local check results/violations, adopted policy assumptions, and official-checker status: unavailable, not_run, passed or failed |
| `solve_metrics` | Runtime and, where meaningful, objective bound/gap in consistent score units |

If no incumbent exists, return empty schedule lists with null score and null ECLO summary. An unavailable schedule must not appear to be a valid zero-ECLO, zero-cost result. If an earlier incumbent survives an improvement-stage timeout, report the retained solution's status as FEASIBLE unless optimality was proved; keep the improvement-stage termination detail in metrics. A solver's FEASIBLE status concerns the encoded model and does not imply that an unavailable official validator has passed it.

Build `eclo_summary` from the returned schedule, with these fields:

| Field | Meaning |
|---|---|
| `eclo_accesses_total` | Number of SCHEDULE_ACCESS rows with eclo=1; exactly E used in the score |
| `eclo_penalty` | 5 times that count in B/C; zero for a valid A result |
| `accesses` | One record per ECLO access: activity ID, access sequence, contract number, activity type, week, week start/end dates, local access_night and affected line codes |
| `by_week` | ECLO access counts and date ranges for the weeks actually used |
| `by_line` | Actual ECLO usage weeks and affected-access counts for each line |
| `selected_windows` | Scenario C's chosen window per line, including week numbers and date bounds; null for A/B or a line with no ECLO use |

Report the chosen C window separately from the weeks actually used: a two-week permitted window may contain ECLO work in only one week. For an ECLO access affecting both lines, count the row once in `eclo_accesses_total` and `by_week`, but include it under both lines in `by_line`. Never sum the affected-line counts to obtain E.

Official timing precision is weekly. Derive week start as `horizon_start + 7*(week-1)` days and week end as `horizon_start + (7*week-1)` days. The official `access_night` is local to contract/type/week; `access_night=2` does not mean Tuesday. Neither local night indices nor local group labels establish a shared real-world calendar night. The official output alone cannot establish distinct calendar days or exact ECLO weekdays. Exact calendar-night dispatch is supplied by the separate operational stage below and must never be reverse-engineered from the official labels.

For example, the following illustrates an ECLO row's format only; it is not a complete schedule:

```csv
activity_id,access_seq,week,eclo,access_night
A036,1,22,1,2
```

This is one ECLO access for A036 in week 22 on its contract/type's local night 2. Its weekday remains unspecified until a validated operational calendarisation result supplies `service_date` separately.

## Operational Enrichment Addendum

The following formulation is required for ForRail workflow runs but is not part of official PS1 scoring or the three CSV schemas.

### Date assignment

Let `D(w)` be the explicitly eligible Singapore service dates in week `w`, and let `a` identify a persistent access occurrence. Introduce binary `g_ad`, equal to one when access `a` is assigned to date `d`:

\[
\sum_{d\in D(w(a))}g_{ad}=1.
\]

All footprint rows for `a` use that date. If accesses share one location/week/group, their chosen dates are equal. Date-level capacity, protection, ECLO, workfront, precedence and explicit calendar restrictions remain hard. Frozen/manual pins set the relevant `g_ad=1`. If this subproblem is infeasible, return a conflict/no-good to weekly solving; do not publish a partial date map.

### Recurrence

Generate stable occurrences only from an explicit composite asset policy. For scheduled occurrence dates `r_k`, last verified completion `r_0` and maximum interval `q`:

\[
r_k-r_{k-1}\le q
\]

and enforce the horizon-end due boundary. Every generated occurrence carries a complete workload/footprint/contract template and is mandatory in operational mode. Early work cannot permit the next gap to exceed `q`. Generated IDs never enter an official submission.

### Replanning and churn

At `as_of`, freeze completed/occurred, in-progress and locked accesses, and credit their delivered yield. Add typed emergency/ad-hoc changes, then solve one selected scenario. First minimise its primary objective `O_s`; with `O_s=O_s*` by default, minimise churn `C`. `O_s` is official for an eligible competition run and PS1-derived/operational when it includes generated work. An approved non-negative score tolerance is explicit and reported, never hidden in a blended coefficient.

`C` is computed over persistent future access IDs and decomposes changed week/date, absolute day displacement, ECLO flips and material sharing changes. New jobs have no baseline movement cost. Pure group-label symmetry and `access_seq` renumbering have zero churn.

### Manual and explanation boundaries

A drag/move is a pinned draft checked by the same independent validator. Publication repeats complete validation against current revisions; an infeasible repair preserves the prior plan. Explanations are deterministic fact packs derived from stored placements, diffs, binding rules and measured counterfactuals. A chatbot can verbalise and query those facts through role-scoped read-only tools, but cannot modify, validate or publish a schedule.
