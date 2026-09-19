# ForRail Optimisation Solver Specification

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> This document specifies the optimisation engine architecture for ForRail.
> Per [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md), the **Problem Statement 1 (PS1) Official Adoption Plan** acts as the single authoritative source of truth.
>
> The legacy single-night solver (`backend/app/services/cp_sat.py`) and validator (`full_validator.py`) based on `constraints_lp_setup.md` are **retired from the official PS1 path** and retained solely as historical learning and demonstration artifacts.

---

## 1. Official PS1 Optimisation Problem

The official PS1 challenge replaces the synthetic, single-night minute-level scheduling with **multi-week access allocation**, **location possession packing**, and **complete activity workloads** across a 30-week planning horizon (`W = 1..30`).

### Target & Priorities
1. **Schedule every activity's full workload** (100% complete; dropping/truncating work is strictly forbidden).
2. **Satisfy every official hard rule**.
3. **Minimise the official penalty on hidden instances**.
4. **Handle Scenarios A, B and C correctly**.
5. **Solve reliably within a bounded runtime**.
6. **Deliver exact global nights, recurring maintenance, low-churn replanning, safe manual edits and grounded explanations**.

---

## 2. Official Mathematical Formulation

### Sets and Dimensions
- **Activities $I$:** Every activity in `08_ACTIVITY_DETAILS.csv` (54 in the public instance).
- **Contracts / Budget Groups $C$:** Every contract/type group in `07_PROJECT_DETAILS.csv` (14 public contracts).
- **Weeks $W$:** Input planning horizon `1..H` (`1..30`, 2027-01-04 through 2027-08-01 publicly).
- **Locations $L$:** Bound-specific tunnel and platform locations from `04_LOCATION_SUPPLY.csv` (76 publicly).
- **Lines $R$:** Input line codes (`ALP`, `BET` publicly).
- **Local Nights $N_c$:** Local night indices `1..K_c` per contract/type/week, where $K_c$ is the CSV weekly cap.
- **Possession Groups:** Candidate shared possession slots scoped to each location and week (`co_share_group`).

Three dimensions remain strictly separated:
- `week`: calendar week placement (`1..30`) and completion accounting.
- `access_night`: index into the contract/type's granted weekly nights (`1..K_c`).
- `co_share_group`: identifier for a shared possession slot at a specific location and week.

### Decision Variables
- $x_{iw} \in \{0, 1\}$: activity $i$ receives an access in week $w$.
- $e_{iw} \in \{0, 1\}$: that access uses Early Closure / Late Opening (ECLO); $e_{iw} \le x_{iw}$.
- $z_{iwn} \in \{0, 1\}$: assignment of activity $i$ in week $w$ to contract local night $n \in \{1..K_c\}$.
- $y_{iwlg} \in \{0, 1\}$: assignment of activity $i$ in week $w$ to possession group $g$ at location $l$.
- $u_{lwg} \in \{0, 1\}$: indicator that possession group $g$ is occupied at location $l$ in week $w$.
- Contract completion week, activity lateness, location-week excess, and Scenario C line ECLO window variables.

### Hard Constraints
1. **Mandatory Full Workload Yield:** Every activity $i$ with workload $d_i$ must receive full access yield:
   $$\sum_{w \in W} (2 x_{iw} + e_{iw}) \ge 2 d_i$$
   A standard access yields 1 unit; an ECLO access yields 1.5 units (doubled units avoid floating point issues).
2. **At Most One Access per Activity per Week:** $x_{iw} \le 1$ for all $i, w$.
3. **Planned Start Week:** $x_{iw} = 0$ for all $w < r_i$ (where $r_i$ is the activity's planned start week).
4. **Precedence Constraints:** For every supplied dependency $(p, i)$, all access workload of predecessor $p$ must complete before work on successor $i$ begins.
5. **Core Footprint Booking:** An access must book every traversed tunnel and all endpoint/intermediate platforms in its core footprint:
   $$\sum_g y_{iwlg} = x_{iw}, \quad \forall l \in F_i$$
6. **Legal Possession Group Mixes:** Within any location-week possession group:
   - Exactly 1 PM alone; OR
   - Exactly 1 PC with at most 3 C (at most 4 activities); OR
   - At most 4 C activities.
   - Two PCs cannot share a group.
7. **Capacity & Co-Sharing:** One occupied possession group consumes 1 possession slot at that location and week.
8. **Protection Footprints & Buffers:**
   - **Live work:** 2 buffer sectors each side, opposite-bound closure mirroring, and cross-line interchange tunnel/platform protection.
   - **Consist work:** 1 buffer sector each side; no mirroring.
   - **Others:** 0 buffer sectors; no mirroring.
9. **Contract Weekly Night Caps:** For each contract/type $c$ in week $w$, distinct local night indices cannot exceed the CSV weekly maximum $K_c$.
10. **Contract Workfront Limits:** At most $f_c$ concurrent activities per contract/type on any single local night:
    $$\sum_{i \in c} z_{iwn} \le f_c, \quad \forall n \in \{1..K_c\}$$

---

## 3. Scenario Rules (A, B, C)

| Rule / Dimension | Scenario A (Strict Supply) | Scenario B (Strict Schedule) | Scenario C (Balanced) |
|---|---|---|---|
| **Planned Deadline Overrun** | Allowed, penalised | **Hard-forbidden** (no lateness allowed) | Allowed, penalised |
| **Location Supply Excess** | **Hard-forbidden** | Allowed, penalised (no hard excess limit) | At most **1 excess slot** per location-week, penalised |
| **ECLO Allowed** | **Hard-forbidden** ($e_{iw} = 0$) | Allowed anywhere in horizon | Allowed within **one span of $\le 2$ calendar weeks** per affected line |
| **Core Constraints** | Hard (Workload, Mixes, Budgets, Workfronts) | Hard (Workload, Mixes, Budgets, Workfronts) | Hard (Workload, Mixes, Budgets, Workfronts) |

### Scenario C Line ECLO Window:
In Scenario C, the solver independently chooses an ECLO start week $W^{start}_r$ for each line $r \in \{\text{ALP}, \text{BET}\}$. Any ECLO access affecting line $r$ must fall within $[W^{start}_r, W^{start}_r + 1]$. Cross-line Live work must fit the ECLO window of both lines.

---

## 4. Official Scoring Objectives

Let:
- $P = \sum_{i \in I} \text{contract\_weight}_i \times (1 + \text{activity\_nudge}_i) \times \text{activity\_overrun\_days}_i$
  - Contract weights: Priority 1 = 100, Priority 2 = 10, Priority 3 = 1.
  - Activity nudges: Priority 1 = 0.3, Priority 2 = 0.2, Priority 3 = 0.
  - Activity overrun compares its completion week ending Sunday ($7w - 1$ days from horizon start) against its contract's **planned** completion date.
- $V = \sum_{l \in L, w \in W} \max(0, \text{distinct\_possession\_groups}_{lw} - \text{nominal\_supply}_l)$
- $E = \text{total number of ECLO access rows scheduled}$

### Objective Function to Minimise:
- **Scenario A:** $\min P$
- **Scenario B:** $\min (7 V + 5 E)$
- **Scenario C:** $\min (P + 7 V + 5 E)$

*Model implementation:* Multiply the objective by 10 for exact integer coefficients in CP-SAT.

---

## 5. Solver Search Strategy

1. **Staged CP-SAT Solving:**
   - **Stage 1: Complete Feasibility:** Solve for a 100% complete workload feasible incumbent satisfying all hard rules.
   - **Stage 2: Exact Objective Improvement:** Optimise the exact scenario objective penalty under the remaining run budget.
2. **Greedy Seed & Hints:** Generate a deadline/slack-aware initial placement to warm-start CP-SAT.
3. **Incumbent Retention:** If the time limit expires during improvement, preserve and return the best valid incumbent. Distinguish `UNKNOWN` from proven `INFEASIBLE`.
4. **Symmetry Breaking:** Canonicalise interchangeable possession group labels within their location/week scope.
5. **LNS (Large Neighborhood Search):** Reoptimise congested location/weeks and coupled dependency chains.

---

## 6. Operational Enrichment Formulation

These are required ForRail workflow layers, not official score terms. `competition` runs remain eight-file-only and official-export eligible; `operational` runs may add versioned calendars, recurrence policies and emergency jobs.

### Calendarisation

After weekly solving, introduce a binary choice for each access and eligible Singapore `service_date` in its week. Choose exactly one date, align all footprint rows and co-share-group members on that global night, and enforce explicit date-level capacity, protection, ECLO, workfront and predecessor rules. `access_night` remains a local contract/type/week index and is never converted directly to a weekday.

If no date assignment exists, return the conflicting weekly pattern to the main solve as a cut or neighbourhood to repair. Do not publish partially dated schedules. The selected scenario objective remains primary; date balancing and movement are secondary operational objectives.

### Recurrence

For each explicit station/sector policy, generate stable mandatory occurrences from `last_completed_date`, `max_interval_days`, effective horizon and a complete job template. Exact service dates must satisfy:

\[
date_{k}-date_{k-1}\le interval\_days
\]

including the carry-in completion and horizon-end due boundary. Early completion cannot create a later oversized gap. Generated work uses the same workload, footprint, possession and safety constraints but is excluded from official CSV submissions. Never infer recurrence from nominal supply or subtract the same maintenance twice.

### Dynamic replanning and churn

Freeze completed/occurred, in-progress and manually locked accesses at an explicit `as_of` instant. Credit their delivered yield and solve all remaining mandatory work, including new emergency/ad-hoc and recurring jobs. Amendments apply from their effective time, not retroactively. Apply one selected A, B or C policy per run; optimise movable future variables while reporting full-plan and remaining-horizon metrics.

Optimise lexicographically: hard feasibility and recurrence; then the selected scenario objective `O_s`; then churn with `O_s=O_s*` by default. `O_s` is official only for an eligible competition run; over generated/ad-hoc work it is a PS1-derived `operational_scenario_cost`. A separately approved degradation tolerance may relax equality and must be reported. Churn matches persistent internal access IDs and measures material future week/date, day-distance, ECLO and sharing changes; pure label renaming and sequence renumbering cost zero.

### Manual edits and explanations

A dragged placement is a pinned draft, not a published mutation. The independent validator returns structured hard conflicts and warnings; a repair solve keeps the pin and replans movable work. Save repeats validation against current revisions. Explanation fact packs contain stored placements, diffs, binding rules, score/churn deltas and measured counterfactuals. A chatbot may verbalise those facts through scoped read-only tools but cannot solve, validate or publish.

---

## 7. Official Module Architecture

| Module | Responsibility |
|---|---|
| `backend/app/domain_models.py` | Canonical official problem and CSV row types. |
| `backend/app/io.py` | Ingestion/normalisation of the 8 official CSVs and exact 3-CSV writing. |
| `backend/app/topology.py` | Network graph, core spans, buffers, mirrored closure and interchange crossover. |
| `backend/app/ps1/models.py` | Typed solver options, statuses, result and validation summaries. |
| `backend/app/ps1/solver.py` | Official CP-SAT solver implementing the multi-week, possession, and scenario model. |
| `backend/app/ps1/scoring.py` | Independent official-score reconstruction. |
| `backend/app/ps1/validation.py` | Independent post-solve verification of exported schedules against official rules. |
| `backend/app/ps1/artifacts.py` | Strict artifact re-read and round-trip checks. |
| Planned `backend/app/ps1/` workflow modules | Calendarisation, recurrence, replan/churn, manual preflight and explanation facts. |

---

## 8. Legacy Synthetic Solver (Historical Reference)

The legacy single-night CP-SAT solver (`backend/app/services/cp_sat.py`) and validator (`backend/app/services/full_validator.py`):
- Designed around single-night minute grids, synthetic engineer qualifications, named equipment, and partial recovery (deferring work).
- **Retired from official PS1 scoring:** Deferring requests in recovery violates PS1's mandatory complete-workload rule.
- Retained only as a historical teaching scaffold. It may not import while the deleted legacy domain module is absent and must not be presented as the active execution path.

## 9. Application routing

The application exposes two planning modes without merging engines:

- **PS1 Requirements → A/B/C → `backend/app/ps1/solver.py`**. A queued run
  records an exact instance revision and persists only a complete locally
  validated incumbent.
- **Operations Mode → A/B/C → `backend/app/schedule_insertion/solver.py`**.
  An exact baseline revision is solved into a review candidate and is promoted
  only by Accept Schedule.

Both schedule and map projections require the same explicit identity. Newest
run timestamps are discovery metadata, never an authoritative selection rule.
