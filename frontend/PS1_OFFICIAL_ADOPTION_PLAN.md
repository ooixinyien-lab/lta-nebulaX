# PS1 Official Adoption Plan

**Audience:** backend, optimisation, data, frontend and presentation teammates.  
**Scope:** Problem Statement 1 only. This document proposes adoption work; it does not implement it.  
**Audit baseline:** the official materials and repository inspected on 18 September 2026.

## Executive summary

Our target is first place in PS1. Keep NebulaX's application infrastructure and replace its synthetic, single-night optimisation model with a model of weekly accesses, location possessions and complete activity workloads.

The order of priorities is:

1. Schedule every activity's full workload.
2. Satisfy every official hard rule.
3. Minimise the official penalty on hidden instances.
4. Handle Scenarios A, B and C correctly.
5. Solve reliably within a bounded runtime.
6. Demonstrate useful explanations and disruption replanning.

The authoritative specification is [the official PS1 README](../NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md), supported by its eight input CSVs, sample submission and references. PS2 and PS3 are outside scope.

**Critical limitation:** the supplied pack does not contain the official validator or the referenced `trackaccess` tooling. Our existing synthetic validator is not the official checker. Exact executable conformance and official scores therefore remain unverified.

This document separates three kinds of statement:

| Label | Meaning |
|---|---|
| **Official requirement** | Stated in the PS1 README or published input/output schema. Where the materials conflict, the uncertainty is identified. |
| **Audit finding** | Observed in the supplied data, sample outputs, references or existing code. Reconstructed scores are not official validator results. |
| **Proposed design** | A team implementation recommendation, subject to confirmation against the official executable. |

Frontend implementation remains owned by the frontend team. This plan specifies the data/API support they need, without prescribing or generating UI code.

## Top 5 findings

1. **The optimisation problem has changed.** The old solver assigns unsplittable jobs to minutes within one engineering night. PS1 assigns repeated activity accesses across weeks and packs compatible work into location possessions. Mapping CSV rows into the old `MaintenanceRequest` would retain unsupported assumptions.
2. **The official validator is absent.** PS1 contains eight inputs, three sample outputs, a README, an SVG and a drawio file. Neither source/executable tooling nor an installed `trackaccess` module was found. An exhaustive executable-rule audit and README/validator comparison cannot yet be completed.
3. **Minute-level scheduling is unnecessary.** Official decisions use week, local `access_night`, ECLO and location-specific `co_share_group`. The two labels are independent accounting concepts, not a global calendar-night identifier. In 169 of 192 sample accesses, the group label changes across the activity's footprint.
4. **The public data provides useful lower bounds.** It contains 54 activities, 14 contracts, 192 workload units, 76 locations and a 30-week horizon. Under the detailed README score, A has a lower bound of 25.2 before competition, versus the sample's reconstructed 48.3. B requires at least six ECLO accesses, costing at least 30 before excess supply. C cannot eliminate A036's delay.
5. **Official score comes before additional features.** Full workload and feasibility are mandatory gates. The rubric covers problem fit, technical performance on hidden instances relative to the reference solver, and usability; it publishes no numerical dimension weights. Stability, utilisation and explanations have no documented direct score term.

## What changed from our old model

| Old concept | Classification | Official adoption decision |
|---|---|---|
| OR-Tools CP-SAT | KEEP | Reuse the optimisation technology with a new domain model. |
| Bounded solving, incumbent retention, truthful statuses | KEEP | Preserve a valid solution when improvement times out; distinguish `UNKNOWN` from proven infeasibility. |
| Independent validation before publication | KEEP | Recheck exported artifacts using the official validator when available. |
| Exact minutes, five-minute grid, setup/test/handback phases | REMOVE from PS1 | No official duration or clock-time inputs require these variables. |
| `IntervalVar` / `OptionalIntervalVar` | REMOVE from PS1 core | Repeated accesses can be separated by idle weeks. Use placement choices, not one continuous job interval. |
| Engineer assignment and qualifications | BONUS ONLY | No official engineer inputs; exclude these constraints from scored solving. |
| Equipment, vehicles and travel | BONUS ONLY | No corresponding official demand/supply tables; do not invent resource bottlenecks. |
| Manpower capacity | ADAPT the concept | Use contract/type workfront limits, not a global technician pool. |
| Dependencies | ADAPT | Preserve the six supplied predecessor edges. Remove synthetic minute handover buffers and single-night filtering. Confirm the exact week comparator. |
| Power compatibility | ADAPT | Replace ON/OFF timing and transition guards with nature-of-work protection footprints, Live mirroring and interchange effects. |
| Blanket sector exclusivity | ADAPT | Permit legal PC/C and C/C co-sharing within location possession groups. |
| Optional/deferrable jobs and partial recovery | REMOVE | Every activity and its full workload must be represented. |
| Stability and replanning | BONUS ONLY for scoring | Reuse baseline, revision and change-report concepts. Optimise official score before churn. |

**Audit finding:** the current integration test accepts publishing seven of twelve synthetic requests after recovery. That behaviour violates PS1's complete-workload baseline. See [the current integration test](../backend/tests/test_full_api_integration.py).

## Official PS1 scheduling model

### What the solver decides

**Official requirements:** choose which weeks each activity receives access, whether an access uses ECLO where permitted, its contract/type's local night index, and its possession group at every location in its working span. Derive completion dates and scenario results from those placements.

Three dimensions must remain distinct:

| Dimension | Scope | Meaning |
|---|---|---|
| `week` | Planning horizon | Calendar placement and completion accounting. |
| `access_night` | Contract + activity type + week | Index into that contract/type's granted weekly nights; used for allocation and workfront checks. |
| `co_share_group` | Location + week | Identifies a shared possession slot at that location. |

**Audit finding:** the sample gives different group labels to different locations on one route. It also puts A040 and A042 in shared location groups in week 25 despite different local night indices and a one-workfront contract. A globally synchronised interpretation would reject the sample.

### Sets and parameters

**Proposed design:** use these mathematical objects, with source-dependent semantics isolated for later validator confirmation.

| Object | Definition |
|---|---|
| Activities `I` | Every row in `08_ACTIVITY_DETAILS.csv`. |
| Contract/type groups `C` | Budget groups identified by contract number and activity type. |
| Lines `R`, locations `L` | Line-specific, bound-specific network locations. |
| Weeks `W` | Declared planning horizon, provisionally `1..H`. Horizon overflow needs executable confirmation. |
| Predecessor edges | Supplied activity-to-activity dependencies. |
| Local nights `N_c` | Indices `1..K_c`, where `K_c` is the CSV weekly cap. |
| Possession groups | Candidate group labels scoped to each location/week. |
| Activity parameters | Workload `d_i`, release week `r_i`, core footprint `F_i`, protection footprint, affected lines, possession role and priority. |
| Contract parameters | Weekly cap `K_c`, workfront count `f_c`, planned deadline `D_c`, contract priority and nature of works. |
| Supply `s_lw` | Nominal possession slots at a location/week, repeated from the supplied flat capacity table. |

### Decision variables

- `x_iw`: activity `i` receives an access in week `w`.
- `e_iw`: that access uses ECLO; `e_iw <= x_iw`.
- `z_iwn`: assignment to a contract/type's local night index.
- `y_iwlg`: assignment to a possession group at a core footprint location.
- `u_lwg`: whether that possession group is occupied.
- First/last access weeks, activity lateness, contract completion, location-week excess and Scenario C's ECLO window start per line.

**Granularity decision:** do not introduce minute or weekday variables into the scored model. Do not force an activity to occupy one continuous multiweek interval or to use one group label along its entire route.

### Completion and output

**Audit finding:** the sample maps week `w` to its ending Sunday:

`completion_date(w) = horizon_start + (7w - 1) days`

An activity finishes in its last access week; a contract finishes when its last activity finishes. Report contract overrun against `planned_completion_date`. The contractual completion date is a separate field, not the stated scoring deadline.

**Official requirement:** provide a separate three-file answer bundle for each scenario.

| File | Exact columns |
|---|---|
| `SCHEDULE_ACCESS.csv` | `activity_id,access_seq,week,eclo,access_night` |
| `SCHEDULE_OCCUPANCY.csv` | `activity_id,week,location_id,co_share_group` |
| `RESULTS.csv` | `scenario,contract_number,simulated_completion_date,overrun_days` |

Do not mix scenarios within a `RESULTS.csv`. The supplied sample covers A only; our deliverable must cover A, B and C.

## Hard constraints

The following catalogue comes from the README and schema. It is **not an exhaustive list extracted from the absent executable validator**.

| Rule | Required or proposed treatment | Evidence status |
|---|---|---|
| Full workload | Every activity receives total yield at least `total_accesses`; none dropped or truncated. | Official requirement |
| Access yield | Standard access yields 1; ECLO yields 1.5 total. | Official requirement |
| Planned start | No access before the activity's planned start week. | Official requirement |
| One access/activity/week | At most one access for an activity in a week. This differs from the contract's multiple local nights. | Explicit README statement in the ECLO-window rule |
| Precedence | Predecessor workload completes before successor work begins. Use strictly later weeks provisionally; confirm comparator. | Input field and sample support; precise enforcement unspecified |
| Core occupancy | Book every traversed tunnel and all endpoint/intermediate platforms. | Official requirement; sample confirmed |
| Legal mix | One PM alone; or one PC with at most three C; or at most four C. Two PCs cannot share. | Official requirement |
| Co-sharing | One location/week/group consumes one possession slot. Apply the stated intra-possession closure/buffer exemptions. | Official requirement; exact exemption propagation unresolved |
| Buffers | Live: two sectors each side; Consist: one; Others: zero. Protect against buffer/work and buffer/buffer conflicts under the official possession semantics. | Official requirement; boundary and timing details unresolved |
| Opposite-bound Live mirroring | Derive the opposite-bound closure for Live work. | Official requirement |
| Interchange Live effect | Live couples the other line's interchange tunnel/platform protection; non-Live work keeps independent capacity. | Official requirement; exact cross-line footprint unresolved |
| Weekly allocation | Distinct local night indices per contract/type/week cannot exceed the CSV cap. | Official requirement |
| Workfronts | Distinct activities per contract/type/local night cannot exceed the CSV workfront count. | Official requirement |
| Scenario policy | Apply A/B/C capacity, date and ECLO restrictions below. | Official requirement |
| Artifact integrity | Correct IDs, complete references, access ordering, occupancy coverage and consistent results. | Published schema; exact duplicate/parser checks unavailable |

Source: [PS1 operating rules, sections 2.4–2.6](../NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md).

### Workload and local accounting formulation

**Proposed design:** use doubled workload units to avoid floating-point arithmetic:

`sum_w(2*x_iw + e_iw) >= 2*d_i`, for every activity.

The official rule is an inequality. Exact equality could exclude legitimate ECLO rounding. Binary `x_iw` enforces one access/activity/week.

For local night assignment:

- `sum_n z_iwn = x_iw`.
- `sum_(i in contract/type c) z_iwn <= f_c`.
- Night indices are restricted to `1..K_c`.

If the checker confirms no additional coupling to these local labels, the assignment is equivalent to a weekly count limit `sum_i x_iw <= K_c*f_c`, followed by deterministic label assignment. This is a potential model reduction, not an assumption to apply before confirmation.

### Occupancy and protection formulation

For each scheduled activity and each core location, assign exactly one group: `sum_g y_iwlg = x_iw`. Link group usage to its members and enforce the legal mixes. Count distinct occupied groups, not activity rows, for location supply.

**Audit finding:** the sample's 928 occupancy rows contain core working footprints only. Even the Live activities have no extra buffer, mirrored-bound or cross-line rows. Derive protection separately; do not count it as extra workload or automatically export it as core occupancy.

**Proposed design:** isolate core expansion, protection expansion and closure/co-sharing compatibility into explicit policies. A blanket prohibition on overlapping protection footprints anywhere in the same week rejects the supplied sample. The exact conflict predicate must come from the official checker or organiser clarification.

Maintenance has already reduced the available supply. There is no separate maintenance event calendar in the eight CSVs; do not invent reservations or subtract maintenance a second time.

## Scenario A/B/C differences

### Hard policy

| Policy | A: strict supply | B: strict schedule | C: balanced |
|---|---|---|---|
| Planned-date overrun | Allowed and penalised | Hard-forbidden | Allowed and penalised |
| Location supply excess | Hard-forbidden | Allowed and penalised; no documented hard excess limit | At most one excess slot per location/week, penalised |
| ECLO | Hard-forbidden | Allowed anywhere in horizon | Allowed within one span of at most two calendar weeks per affected line |
| Workload, safety, allocation and workfront limits | Hard | Hard | Hard |

Scenario C may also receive amended input supply. That input elasticity and the additional one-slot allowance are separate: read the actual instance and then apply the scenario rule.

In C, independently choose a window start for each line. Every ECLO access affecting a line must fall in that start week or the next. Cross-line Live must fit both windows. This limits each activity to at most two ECLO accesses; it does **not** limit an entire line to two ECLO accesses.

B's flexible supply does not increase contract weekly caps, workfronts or the activity's maximum weekly frequency.

### Score

**Official documentation, provisionally reconciled:** use the detailed per-activity definition in README section 2.7. Its displayed A/C equations omit an activity multiplier that the worked examples and detailed score definition include. Confirm the executable formula and version before claiming parity.

Let:

- `P` = sum over activities of `contract_weight * (1 + activity_nudge) * activity_overrun_days`.
- Contract weights = 100, 10, 1 for contract priorities 1, 2, 3.
- Activity nudges = 0.3, 0.2, 0 for activity priorities 1, 2, 3.
- Activity overrun compares its completion with its contract's **planned** deadline.
- `V` = sum over location/weeks of `max(0, distinct_possession_groups - nominal_supply)`.
- `E` = number of ECLO access rows.

| Scenario | Penalty to minimise |
|---|---|
| A | `P` |
| B | `7*V + 5*E` |
| C | `P + 7*V + 5*E` |

**Proposed design:** multiply the objective by ten for exact integer coefficients. Optimise this weighted objective directly. Do not replace it with contract-level makespan lateness or rigid lexicographic priority tiers: the stated finite weights permit trade-offs.

The report also includes total overrun, contracts overrunning, earliness, raw overrun by contract priority, hotspots and access counts. These diagnostics are not additional documented penalties. Stability and utilisation are not direct score terms either.

### Public-instance bounds and economic implications

**Audit findings, assuming the stated weekly-frequency rule, detailed scoring formula and the sample's week-end completion convention:**

| Case | Derivation | Implication |
|---|---|---|
| A036 in A | Release week 22, workload 7, planned deadline week 26. Earliest completion is week 28: 14 days late at weight 1.3. | At least 18.2 penalty. |
| A059 in A | Release week 14, workload 7, planned deadline week 19. Earliest completion is week 20: 7 days late at weight 1. | At least 7 penalty; together A has lower bound 25.2 before competition. |
| A036 and A059 in B | Five available weeks require at least four ECLO accesses for A036; six weeks require at least two for A059. | At least six ECLO accesses and penalty 30 before excess supply. |
| A036 in C | At most two ECLO accesses add only one workload unit. At least six weeks are needed. | At least seven days late, even with extra location supply. |

For A036 in C, two ECLO accesses reduce isolated lateness cost from 18.2 to 9.1 but add 10 ECLO cost: total 19.1 is worse. ECLO can still help other activities or reduce excess supply, but “always accelerate before accepting delay” is not a valid policy.

The supplied A sample has 28 contract-overrun days but a reconstructed **per-activity weighted penalty of 48.3**. Those metrics are different. None of these numbers is an official validator result or proof that a lower bound is achievable.

## Official data mapping

Source: [the eight official input files](../NebulaX-Hackathon-ProblemStatement-main/PS1/01_data/).

| CSV | Data rows | Important columns and relationships | Scheduling meaning |
|---|---:|---|---|
| `01_LINES.csv` | 2 | `line_code` key; `line_name` | ALP/BET identities and display labels. |
| `02_STATIONS.csv` | 20 | Composite key `(line_code, station_id)`; `seq`; `is_interchange` | Line-local station order and interchange hubs. H01/H02 recur on both lines. |
| `03_SECTORS.csv` | 18 | `sector_id`; line; from/to station IDs; `seq`; `is_shared` | Tunnel adjacency. Endpoint joins must include line. All `is_shared` values are zero. |
| `04_LOCATION_SUPPLY.csv` | 76 | `location_id`; `location_kind`; line; bound; `supply_capacity` | 36 bound-specific tunnel locations and 40 platform locations. Flat weekly possession capacity; there is no week column. |
| `05_BUFFER_LOCATION.csv` | 3 | `nature_of_works`; `up_to_buffer_sectors`; `opposite_bound_required` | Join project `nature_of_activity`; Live 2/mirror, Consist 1/no mirror, Others 0/no mirror. |
| `06_PARAMETERS.csv` | 2 | `key,value`: `horizon_start`, `horizon_weeks` | Public horizon starts 2027-01-04 and spans 30 weeks through 2027-08-01. |
| `07_PROJECT_DETAILS.csv` | 14 | Contract number; description; award date; activity type; nature; contract priority; contractual/planned completion; workfronts; access type; weekly maximum | Contract/type budgets, possession role, protection class and score parameters. Description and award/contractual dates have no stated extra hard rule. |
| `08_ACTIVITY_DETAILS.csv` | 54 | Activity ID; contract/type; start/end locations; total accesses; planned start; predecessor; activity priority | Mandatory workload, inclusive spatial span, release, dependency and within-tier score multiplier. |

### Data audit conclusions

- `activity_type` is Renewal/Construction; `access_type` is PM/PC/C. They are different dimensions.
- Activity IDs have gaps. Preserve supplied IDs instead of generating an assumed sequence.
- No foreign-key inconsistencies, activity-type mismatches or predecessor cycles were found. There are six populated predecessor edges, all within contracts.
- Sector `seq` runs ALP 1–9 and BET 10–18. Derive adjacency within the line rather than assuming both restart at one.
- All public activities are same-line/same-bound sector-to-sector spans: 17 cover one tunnel, 23 cover two, and 14 cover three. A span of `k` tunnels includes `k+1` platforms, giving `2k+1` core locations. This is a public-data observation, not a hidden-instance schema restriction.
- Hub tunnels and hub platforms have nominal supply 1; adjacent tunnels 2; ordinary tunnels 4; ordinary platforms 2. A capacity-one location may still host a legal four-activity group.
- There are nine C contracts, four PC contracts and one PM contract. Two contracts are Live; their public activities A074/A075 each require only one access at the interchange.
- Three contracts have two workfronts; the rest have one. The supplied Live caps are two and others three. Read CSV values rather than hardcoding these relationships.
- There are no engineer lists, equipment lists, manpower demands, exact durations or clock-time windows.

### Sample and reference audit conclusions

- [Sample access output](../NebulaX-Hackathon-ProblemStatement-main/PS1/03_submission_sample/SCHEDULE_ACCESS.csv): 192 rows, all ECLO zero, one access/activity/week, exact workload coverage and no observed planned-start violations.
- [Sample occupancy output](../NebulaX-Hackathon-ProblemStatement-main/PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv): 928 core-footprint rows. Counting distinct groups satisfies nominal capacity and legal mixes. Local night ranges, weekly budgets and workfront counts also pass the reconstructed checks.
- [Sample results](../NebulaX-Hackathon-ProblemStatement-main/PS1/03_submission_sample/RESULTS.csv): 14 Scenario A rows. Contract overruns are C006: 14 days, C010: 7 days and C014: 7 days.
- All sample successors start strictly after their predecessors' last access week. This does not prove that the missing validator rejects all same-week alternatives.
- The [SVG](../NebulaX-Hackathon-ProblemStatement-main/PS1/02_references/network_diagram.svg) and CSVs establish independent line tunnels with Live-only crossover. The [drawio reference](../NebulaX-Hackathon-ProblemStatement-main/PS1/02_references/PS1.drawio) discusses cross-line buffers and says they do not extend beyond the interchange; precise expansion still needs confirmation.
- Structural/accounting checks do not establish complete sample safety. The exact closure/co-sharing rule is unresolved, despite the README describing the sample as feasible.

## Revised solver architecture

### Backend structure

**Proposed design:** retain the FastAPI application and add one compact `backend/app/ps1/` package. Use one official solver implementation with staged improvements, not a new sequence of competing solver versions.

| Proposed module | Responsibility |
|---|---|
| `models.py` | Official instance, scenario, access, occupancy and result types. |
| `io.py` | Eight-file import, schema/reference checks and normalisation. |
| `topology.py` | Core span, buffer, mirrored closure and interchange expansion. |
| `solver.py` | PS1 model, feasibility search, exact objective and incumbent improvement. |
| `validation.py` | Independent checks, official-validator adapter and explicit validation provenance. |
| `export.py` | Exact scenario CSV bundles and result reconstruction. |

Keep closure compatibility, group counting, local night accounting, completion conversion and scoring policies easy to inspect and replace when the official checker resolves ambiguity. Independent validation must recalculate from exported artifacts; it must not simply trust the solver's own variables.

Add instance/run/result storage. The existing allocation table is keyed by `request_id` and the old API rejects duplicate request IDs. Neither represents repeated accesses for one activity. Preserve short transactions, revision checks and audit records while changing the domain storage.

### Search strategy

**Recommendation:** one CP-SAT model, staged execution: first obtain a complete feasible incumbent, then improve the scenario's official objective under one bounded run budget.

| Technique | Adoption decision |
|---|---|
| Single CP-SAT run | Establish the simplest correct baseline; measure first-feasible latency and score improvement. |
| Staged CP-SAT | Use feasibility then exact-score improvement. Do not retain synthetic movement-first stages. |
| Greedy seed plus CP-SAT | Add a deadline/slack/bottleneck-aware constructor. Validate complete seeds and pass them as hints; greedy failure is not proof of infeasibility. |
| Warm starts | Reuse feasible incumbents across stages and replans. Hints guide search; they are not hard commitments. |
| Symmetry breaking | Canonicalise interchangeable group labels within their true scope. Remove local-night label search only after proving equivalent accounting. |
| Decomposition | Precompute topology and sparse conflicts. Do not solve lines or contracts independently by default: budgets, dependencies, Live effects and ECLO windows couple them. |
| Large Neighborhood Search | Reoptimise congested location/weeks with affected contracts, predecessors and ECLO windows. Start with built-in search; add custom neighbourhoods when measured gains justify them. |
| Parallel search | Benchmark worker counts on the hosted machine. Do not automatically preserve the old single-worker configuration or oversubscribe concurrent scenario runs. |

Retain the best validated incumbent if improvement times out. Report objective/bound/gap only when meaningful for the current model and stage. Benchmark across changed demand, capacities, priorities and release dates, not repeated runs of the public fixture alone.

OR-Tools provides [integer CP-SAT modelling and explicit statuses](https://developers.google.com/optimization/cp/cp_solver), plus [hint repair, parallel search and LNS parameters](https://raw.githubusercontent.com/google/or-tools/stable/ortools/sat/sat_parameters.proto). The strategy above is our design recommendation, not a promised runtime result.

### API needs for frontend teammates

Frontend implementation is out of scope. The backend should provide:

- **Instance upload:** eight named CSVs; instance ID/fingerprint, revision, parse errors, topology, weeks, contracts, activities and required workload.
- **Solve request:** instance, scenario and time budget; optional baseline run and explicit disruption/replan inputs.
- **Run progress:** phase, elapsed time, solver status, workload completeness and best validated incumbent. Keep official validation status separate.
- **Results:** exact access/occupancy rows, scheduled versus required workload per activity, contract completions, score components, ECLO windows, capacity/excess hotspots and validator report.
- **Downloads:** exactly three official CSV artifacts per scenario.
- **Replan differences:** changed activity/week/access/ECLO placements, affected locations, score before/after and evidenced reasons. Pure label renaming is not operational churn.
- **Validation provenance:** identify checker/formula version and report `validator_unavailable` until the actual official tool is supplied.

Do not fabricate clock-time allocations or named resource assignments to satisfy the old API. Expose local night/group meanings clearly so downstream views do not imply unsupported global chronology.

## Existing code: Keep / Modify / Retire / Do Not Touch

These are proposed implementation actions. **Retire** means remove from the official PS1 path while preserving historical code; it does not mean delete files now.

| Files or area | Action | Reason |
|---|---|---|
| `backend/app/auth/`, `backend/tests/test_auth.py` | KEEP | Identity and role enforcement are independent of the scheduling model. |
| Transaction, audit, stale-proposal and tamper-test patterns | KEEP | Preserve publication integrity and reproducibility. |
| `backend/app/main.py` | MODIFY narrowly | Keep FastAPI/static-hosting infrastructure; register a separate PS1 router. |
| `backend/app/services/scheduler.py` | MODIFY | Retain the API-to-solver seam and dispatch explicit PS1 instances/scenarios. |
| `backend/app/api/routes.py` | KEEP legacy contract during transition | Add `api/ps1_routes.py` for official-domain operations instead of changing teammates' payloads silently. |
| `backend/app/schemas.py` | ISOLATE legacy schemas | Define PS1 schemas separately; old timed allocation and engineer requirements do not apply. |
| `backend/app/database.py` | MODIFY | Add instance/run/result and repeated-access storage; preserve transaction/revision/audit mechanics. |
| `backend/app/config.py` | MODIFY | Configure PS1 input, official validator and solve budgets instead of requiring a synthetic-only snapshot. |
| `backend/app/services/cp_sat.py`, `full_validator.py` | RETIRE from official path | Current constraints, objectives and validation contract are synthetic. Reuse generic status/incumbent patterns only. |
| `backend/app/models.py` | RETIRE old scheduling types from official path | Do not manufacture phases, timestamps or resources to fit `PlanningSnapshot`/`MaintenanceRequest`. |
| `backend/app/services/{candidates,demo_search,checker,common}.py` | RETIRE from official path | These helpers assume the old timing/resource domain. |
| `backend/app/{job,schedule,checker,conflict,conflict_models,demo,main copy}.py` | RETIRE historical prototypes | Avoid combining competing model definitions into PS1. |
| `data/solver_v0.py`, `data/solver_v1.py`, synthetic JSON fixtures, `scripts/generate_synthetic_dataset.py`, `constraints_lp_setup.md` | RETIRE as PS1 authority | Historical learning/testing artifacts, not official rules or score evidence. |
| Existing synthetic solver/domain/validator tests | RETAIN historical coverage only | Their success does not certify PS1. Add separate official-domain regressions. |
| `docs/API_CONTRACT.md`, `docs/SOLVER.md`, root `README.md` | MODIFY during adoption | Document the official contract and stop presenting synthetic rules as PS1 authority. |
| `frontend/**` and frontend/browser testing assets | DO NOT TOUCH in this workstream | Frontend implementation belongs to teammates. |
| `NebulaX-Hackathon-ProblemStatement-main/PS1/**` | DO NOT TOUCH | Preserve authoritative inputs, references and samples verbatim. |
| Official PS2/PS3 materials | DO NOT TOUCH | Outside scope. |

Relevant current implementation evidence: [single-night solver](../backend/app/services/cp_sat.py), [synthetic validator](../backend/app/services/full_validator.py), [allocation storage](../backend/app/database.py), [API assumptions](../backend/app/api/routes.py) and [partial-recovery integration test](../backend/tests/test_full_api_integration.py).

## Implementation milestones

Use three milestones and one maintained PS1 solver.

| Milestone | Main work | Exit evidence | Main contributors |
|---|---|---|---|
| **1. Official correctness** | Import/normalise eight CSVs; resolve checker semantics; implement complete-workload A/B/C solving and exact exports. | Public bundles with complete workload and zero official hard violations; repeatable score reconciliation. If tooling is still missing, explicitly mark validation incomplete. | Data, optimiser, backend |
| **2. Competitive optimisation** | Exact penalty optimisation, seeds/hints, symmetry reduction and targeted neighbourhood improvement. | Better validated scores against baseline across public and perturbed instances; measured first-feasible time and improvement curves. | Optimiser, data, backend |
| **3. Hidden-instance hardening** | Bounded runtime, upload/run isolation, failure handling, validator regressions and disruption replanning. | Reliable hosted workflow, three scenario exports, measured replan demonstration and submission materials. | Backend, optimiser, data, frontend and presentation owners |

Frontend teammates consume the API contract and own any UI work independently. Do not postpone the upload/run/export contract until presentation week.

## Testing + validator loop

### Authority and validation status

**Audit finding:** there is no official executable to run in the supplied pack. The README's claim that the sample is feasible is useful reference evidence, not an independently reproduced validation result.

**Proposed design:** obtain the exact organiser checker and formula version, pin its provenance and preserve its report. Until then, distinguish local structural/rule checks from official validation. Never relabel `backend/app/services/full_validator.py` as the official checker.

### Validation loop

1. Parse the eight inputs and check IDs, relationships, topology and parameter domains.
2. Solve with complete workload mandatory and retain a candidate incumbent.
3. Export the exact three CSVs for that scenario.
4. Re-read the exports and independently recompute workload, footprints, accounting, dates and score components.
5. Run the official validator on those exported files when available.
6. Compare its feasibility and score with local expectations; turn every disagreement into a focused regression.
7. Publish the checked artifacts with instance, solver and checker provenance. Revalidate when publishing against a changed revision.

### High-value test coverage

| Area | Cases that matter |
|---|---|
| Import | Eight-file completeness, composite station IDs, gapped activity IDs, invalid references, mismatched types and predecessor cycles. |
| Workload | Missing/partial activities, duplicate accesses, standard/ECLO yield and legitimate ECLO rounding. |
| Geometry | Endpoint platforms, line boundaries, buffer/work and buffer/buffer cases, Live mirroring and interchange crossover. |
| Possession accounting | PM exclusivity, two-PC rejection, PC+3C, four C, excess members and local group renaming. |
| Local nights/workfronts | Separate contract/type budgets, per-night teams, and independence from location-group labels. |
| Scenarios | A rejects ECLO/excess; B rejects planned-date overrun; C permits one excess slot but rejects two and enforces both affected-line ECLO windows. |
| Completion/score | Week-end dates, per-activity versus per-contract totals, contract bands/activity nudges, location-week excess and ECLO row counts. |
| Runtime/publication | Timeout with and without an incumbent, truthful solver status, invalid export rejection, stale runs and isolated uploads. |

Use the supplied sample and reconstructed figures as regressions for understood semantics. Do not alter the sample to make a locally invented rule pass. Test the A036/A059 lower bounds and the ambiguous co-sharing/buffer examples against the actual checker when obtained.

Perturb demand, supply, priorities and release dates to exercise hidden-instance behaviour. The public sample contains no ECLO and only two short Live activities, so it is insufficient coverage by itself.

## Winning differentiators

### Direct effect on validator score

- Correct co-sharing at capacity-one interchange bottlenecks.
- Exact per-activity penalty optimisation and priority weighting.
- Early treatment of low-slack activities and dependency chains.
- Joint ECLO-window selection, including cross-line effects.
- Marginal-cost decisions that account for both congestion relief and completion effects.
- Counting extra possessions at every location/week they consume, rather than once per activity.
- Reliable retention of complete, validated incumbents on difficult hidden instances.

### Judging and demonstration quality

- Demonstrate a supply disruption, identify the possessions it invalidates, replan, and show the before/after score and operational changes.
- Explain moves using actual binding constraints and measured counterfactual solves, not unsupported narratives.
- Report bounds and unavoidable costs honestly. For example, the public A instance cannot achieve zero under the documented frequency rule.
- Preserve unaffected work where possible after protecting the official score. Ignore pure group-label renaming when measuring churn.
- Make the backend upload/run/validate/export workflow reliable for an unseen eight-file instance.

### Optional bonus

- Natural-language questions grounded in structured explanations.
- Capacity-negotiation suggestions and fragility analysis.
- Named engineers, equipment routing and minute-level logistics only after official solving is reliable and if the team has time; these have lower immediate return.

### Required submission support

The official deliverables are public CSV results, a hosted live app that accepts the eight hidden-instance files, a three-minute YouTube video and a GitLab repository URL. These are requirements, not optional polish. See [PS1 deliverables](../NebulaX-Hackathon-ProblemStatement-main/PS1/PS1_README.md).

The presentation team should use the same validated outputs, score decomposition and disruption evidence as the app. No first-place or optimality claim should exceed the measured evidence.

## Biggest risks

| Risk or discrepancy | Why it matters | Response |
|---|---|---|
| Missing official validator/tooling | Exact hard checks, score formula and compatibility cannot be verified. | Obtain the exact organiser executable/source and version. Keep validation provenance explicit. |
| Local labels mistaken for global nights | Rejects the sample and adds unsupported scheduling restrictions. | Keep contract/type night accounting separate from location-group packing. |
| Closure/co-sharing ambiguity | In week 21, naïve week-wide buffer overlap rejects A074/A025 although the sample is described as feasible. A004 bridges different local sharing groups. | Use these exact examples for checker/organiser clarification; isolate the conflict predicate. |
| Objective contradictions | A/C displayed equations omit the activity multiplier; verbal cost ordering conflicts with the stated 7/5 coefficients and suggests delay in B. | Provisionally follow the detailed per-activity definition and explicit coefficients, then reconcile with the checker. |
| Interchange footprint ambiguity | README/SVG establish separate tunnels; drawio wording leaves protection expansion details uncertain. | Confirm exactly which opposite-line tunnels/platforms close and how boundaries are handled. |
| Precedence and horizon details unspecified | Same-week successor handling and scheduling beyond the declared horizon can change feasibility. | Keep conservative provisional rules isolated; do not silently extend the horizon or discard dependencies. |
| Flexible supply mistaken for guaranteed feasibility | Release dates, workload frequency, workfronts and dependencies can make B impossible regardless of location slots. | Use lower bounds and truthful status reporting; never drop workload or relax safety to manufacture success. |
| Existing API/storage assumptions | One allocation per request cannot represent repeated official accesses. | Add PS1 instance/run/output storage and an explicit API contract. |
| Overfitting public data | No sample ECLO and only two one-access Live activities leave core policies untested. | Benchmark perturbed and targeted edge cases through the validator. |
| Stale top-level wording | Introductory material refers to a shared tunnel/other line names or input counts inconsistent with detailed PS1 data. | Prefer the detailed PS1 specification, schema and executable; preserve original materials. |

## First implementation step

**Build the official input/output and validation boundary before extending optimisation.**

- **Data owner:** parse all eight inputs, preserve IDs, establish composite-key topology and reproduce the core footprints and sample accounting.
- **Backend owner:** define PS1 instance/run/artifact storage and the upload/run/result/export API contract. Keep legacy payloads isolated during transition.
- **Optimiser owner:** implement the week/access/possession model only against that normalised contract; retain mandatory workload and the scenario-specific policies.
- **Team coordination:** obtain the official validator and resolve local-night/group semantics, closure expansion, precedence, horizon handling and score formula/version.
- **Frontend/presentation owners:** review the API information and evidence needed for hidden-instance upload, scenario comparison and the disruption demonstration; implementation remains in their workstream.

The first reviewable artifact is a reproducible eight-file import and sample CSV round trip, with local accounting results and an explicit official-validator status. Once semantics are confirmed, complete the first feasible A/B/C solver milestone before adding bonus features.
