# NEBULA X — Rail Maintenance Scheduling Mathematical Formulation

> **Purpose.** This document converts the team's agreed real-world scheduling rules into a mathematical optimization model. It is the shared reference for the mock dataset, requester form, backend master data, conflict checker, and OR-Tools CP-SAT scheduler.
>
> **Important modelling note:** this is not a pure continuous linear program. The problem contains binary choices, integer time, logical either/or constraints, optional jobs, and resource assignment. The appropriate model is therefore an **integer constraint optimization / CP-SAT scheduling model**.

---

# 1. Real-World Constraint Table

| # | Constraint | Real-world logic | Example |
|---|---|---|---|
| **1** | **Engineering Window & Handback** | Every scheduled job must fit inside the engineering window and finish before the required morning handback/clearance period. | If the window is 01:15–04:45 with a 20-minute handback buffer, work must finish by 04:25. |
| **2** | **Sector Availability & Safety Footprint** | The work sector and its required protection/buffer footprint must be available for the full job duration. Jobs whose protected footprints cannot coexist may not overlap. | R01 works in S03 but protects S02–S04, so another conflicting job cannot occupy S04 simultaneously. |
| **3** | **Work & Traction-Power Compatibility** | Concurrent jobs must satisfy defined compatibility rules. Opposing traction-power requirements cannot overlap in an affected power zone, and any required transition time must be respected. | R01 requires Z01 OFF while R02 requires Z01 ON. |
| **4** | **Resource Requirements, Qualification & Capacity** | Every job must receive its required specialist engineers, pooled manpower and equipment. Specialists must be qualified and available; individuals cannot be double-booked; pooled demand cannot exceed capacity. | A signalling job requires 1 signalling-qualified engineer and 3 technicians. |
| **5** | **Resource Transfer / Travel Time** | A person or individually tracked movable resource assigned to consecutive jobs must have enough time to travel between locations. | E01 finishes at S01 at 02:00 and needs 15 minutes to reach S05. |
| **6** | **Dependencies & Required Sequence** | A dependent activity can start only after predecessor work has completed and any required handover/clearance period has elapsed. | Testing R03 depends on repair R01. |
| **7** | **Booking Commitment & Freeze Horizon** | Draft work is movable. Approved work outside the freeze horizon may move only if necessary. Work inside the freeze horizon is fixed unless a planning officer explicitly unlocks it. | With a synthetic 3-day freeze horizon, a job tomorrow is frozen while a job 5 days away may still move. |
| **8** | **Request Timing Flexibility & Deferral Eligibility** | A requester may request an exact slot, a permitted time range, or any time within the engineering window. Separately, the request states whether it may be deferred to another night. | “Any time tonight, but cannot defer.” |
| **9** | **Service-Critical / Mandatory Work** | Work confirmed as necessary before the next service period cannot be dropped or deferred. Non-mandatory work may be deferred according to optimization priorities. | A defect that would prevent safe next-day service must be scheduled tonight. |

The table above is the **real-life problem**. The remainder converts those rules into mathematical sets, parameters, decision variables, hard constraints and optimization objectives.

---

# 2. Planning Scope and Assumptions

For the MVP, one optimization run plans **one engineering night at a time**.

Let time be measured in integer minutes from the start of the engineering window:

$$
\mathcal T=\{0,1,\ldots,T\}
$$

where $T$ is the total length of the engineering window.

Let:

$$
B=\text{required handback buffer}
$$

and therefore:

$$
T^{use}=T-B
$$

is the latest time at which maintenance work may finish.

Example:

```text
Clock time:  01:15 ------------------------------ 04:45
Model time:    0  ------------------------------- 210
                                            |20 min|
                                             buffer
```

### MVP assumptions

1. Time is modelled in **1-minute integer steps**.
2. A job duration is its **total reserved occupation duration**, including any setup/testing/clearance time that blocks required resources or space.
3. Deferral means the job is not placed in tonight's schedule and is returned to the queue for a later planning instance.
4. Sector rules, work compatibility, power zones and standard resource requirements come from master/reference data.
5. The `mandatory` flag should be planner-confirmed or rules-based, not freely self-declared by requesters.
6. A synthetic freeze horizon may be used in the demo but remains configurable.

---

# 3. Sets

| Symbol | Meaning |
|---|---|
| $j,k\in\mathcal J$ | Maintenance requests / work orders |
| $s\in\mathcal S$ | Track sectors / blocks |
| $z\in\mathcal Z$ | Traction-power zones |
| $e\in\mathcal E$ | Individually tracked engineers |
| $q\in\mathcal K$ | Engineer competency / role types |
| $r\in\mathcal R$ | Pooled resources: technicians, equipment types, etc. |
| $p\in Pred(j)$ | Prerequisite jobs of job $j$ |
| $b\in\mathcal B_s$ | Fixed unavailable intervals for sector $s$ |
| $h\in\mathcal B_e$ | Fixed unavailable intervals for engineer $e$ |

Examples of pooled resources:

```text
GENERAL_TECHNICIAN
TRACK_PROTECTION_OFFICER_POOL
TAMPING_MACHINE
TEST_KIT
MAINTENANCE_TROLLEY
```

If a resource must be tracked by identity rather than quantity, it should use individual-assignment logic similar to engineers.

---

# 4. Parameters

Parameters are known **before** the solver runs.

## 4.1 Global parameters

$$
T = \text{engineering-window length}
$$

$$
B = \text{handback buffer}
$$

$$
T^{use}=T-B
$$

$$
H^{freeze}=\text{configurable booking freeze horizon}
$$

---

## 4.2 Job parameters

For each request $j$:

| Parameter | Meaning |
|---|---|
| $d_j$ | Total reserved duration |
| $\Omega_j\subseteq\mathcal S$ | Work sector(s) + required safety/protection footprint |
| $Z_j\subseteq\mathcal Z$ | Affected power zone(s) |
| $P_j$ | Power requirement: `ON`, `OFF`, or `NONE` |
| $a_j$ | Earliest allowed start |
| $b_j$ | Latest allowed finish |
| $p_j$ | Preferred start, if specified |
| $F_j\in\{0,1\}$ | 1 if a preferred start exists |
| $D_j^{allow}\in\{0,1\}$ | 1 if the job may be deferred |
| $M_j\in\{0,1\}$ | 1 if mandatory before next service |
| $A_j\in\{0,1\}$ | 1 if already approved |
| $L_j\in\{0,1\}$ | 1 if approved and frozen |
| $\bar s_j$ | Existing approved start time |
| $U_j$ | Urgency score for non-mandatory work, e.g. 1–5 |
| $n_{jq}$ | Number of specialist engineer role-slots of competency $q$ required |
| $c_{jr}$ | Quantity of pooled resource $r$ required |
| $\Delta_{pj}$ | Handover/clearance time after prerequisite $p$ |

### Timing modes

**Exact slot**

$$
a_j=p_j,\qquad b_j=p_j+d_j
$$

**Flexible range**

$$
a_j\le s_j,\qquad e_j\le b_j
$$

with $p_j$ representing the preferred start inside that range.

**Any time tonight**

$$
a_j=0,\qquad b_j=T^{use},\qquad F_j=0
$$

Thus all three user choices use the same mathematical model.

---

## 4.3 Sector parameters

For each sector $s$, let:

$$
\mathcal B_s=\{[\alpha_{sb},\beta_{sb})\}
$$

be confirmed intervals during which the sector is unavailable.

Precompute:

$$
C^{sector}_{jk}\in\{0,1\}
$$

where $C^{sector}_{jk}=1$ means the protected footprints of jobs $j$ and $k$ are not allowed to coexist.

---

## 4.4 Work and power compatibility parameters

Define:

$$
C^{work}_{jk}\in\{0,1\}
$$

where 1 means the pair is operationally incompatible when concurrent.

Define:

$$
C^{power}_{jk}\in\{0,1\}
$$

where 1 means the jobs affect a common power zone and require opposing `ON/OFF` states.

Let:

$$
g_{jk}\ge0
$$

be the minimum transition/changeover time required when job $j$ is followed by $k$. This can be directional, so $g_{jk}$ need not equal $g_{kj}$.

---

## 4.5 Engineer parameters

Qualification:

$$
Q_{eq}\in\{0,1\}
$$

where $Q_{eq}=1$ means engineer $e$ is qualified for competency $q$.

Engineer unavailability:

$$
\mathcal B_e=\{[\alpha_{eh},\beta_{eh})\}
$$

Travel time:

$$
\tau^E_{e,jk}\ge0
$$

is the time required for engineer $e$ to travel from job $j$'s location to job $k$'s location.

For the mock dataset, this may come from a simple sector-to-sector travel-time matrix.

---

## 4.6 Pooled-resource parameters

For each pooled resource $r$:

$$
C_r=\text{available concurrent capacity}
$$

and each job consumes $c_{jr}$ units while active.

---

# 5. Decision Variables

## 5.1 Schedule / defer

$$
y_j\in\{0,1\}
$$

where:

$$
y_j=
\begin{cases}
1 & \text{job }j\text{ is scheduled tonight}\\
0 & \text{job }j\text{ is deferred}
\end{cases}
$$

---

## 5.2 Start, end and interval

$$
s_j,e_j\in\mathbb Z_{\ge0}
$$

with:

$$
e_j=s_j+d_j
$$

For CP-SAT, define optional interval:

$$
I_j=Interval(s_j,d_j,e_j)
$$

active only if $y_j=1$.

---

## 5.3 Engineer assignment

$$
x_{jeq}\in\{0,1\}
$$

where $x_{jeq}=1$ means engineer $e$ is assigned to competency/role $q$ on job $j$.

Define:

$$
a_{je}=\sum_{q\in\mathcal K}x_{jeq}
$$

with $a_{je}\le1$.

For CP-SAT, an optional engineer assignment interval $I_{je}$ is active when $a_{je}=1$.

---

## 5.4 Approved-booking movement

For approved non-frozen jobs:

$$
m_j\in\{0,1\}
$$

where $m_j=1$ indicates that the existing approved start time has been moved.

---

## 5.5 Preferred-time deviation

$$
\delta_j\ge0
$$

measures the absolute deviation from preferred start time.

---

## 5.6 Latest completion

$$
C_{\max}\ge0
$$

is the latest completion time among scheduled jobs.

---

# 6. Hard Constraints

Hard constraints may **never** be violated by a schedule.

## Constraint 1 — Engineering Window & Handback

Duration:

$$
e_j=s_j+d_j
\qquad \forall j
$$

If scheduled:

$$
y_j=1\Rightarrow s_j\ge0
$$

$$
y_j=1\Rightarrow e_j\le T^{use}
$$

---

## Constraint 2 — Sector Availability & Safety Footprint

### 2A. Fixed sector unavailability

For every sector $s\in\Omega_j$ and every blocked interval $[\alpha_{sb},\beta_{sb})$:

$$
y_j=1
\Rightarrow
(e_j\le\alpha_{sb})
\lor
(s_j\ge\beta_{sb})
$$

### 2B. Mutually exclusive protected footprints

For every pair with $C^{sector}_{jk}=1$:

$$
y_j=y_k=1
\Rightarrow
(e_j\le s_k)
\lor
(e_k\le s_j)
$$

---

## Constraint 3 — Work & Traction-Power Compatibility

For every pair where:

$$
C^{work}_{jk}=1
\quad\text{or}\quad
C^{power}_{jk}=1
$$

the jobs must be separated.

If $j$ occurs first:

$$
e_j+g_{jk}\le s_k
$$

If $k$ occurs first:

$$
e_k+g_{kj}\le s_j
$$

Therefore:

$$
y_j=y_k=1
\Rightarrow
(e_j+g_{jk}\le s_k)
\lor
(e_k+g_{kj}\le s_j)
$$

In CP-SAT this is implemented with a Boolean ordering variable and reified constraints rather than an unnecessarily large continuous big-$M$.

---

## Constraint 4 — Resource Requirements, Qualification & Capacity

This has two layers.

### 4A. Individual specialist engineers

Every scheduled job receives the required number of specialists:

$$
\sum_{e\in\mathcal E}x_{jeq}
=
n_{jq}y_j
\qquad \forall j,q
$$

Qualification:

$$
x_{jeq}\le Q_{eq}
\qquad \forall j,e,q
$$

One engineer fills at most one specialist role on the same job:

$$
\sum_{q\in\mathcal K}x_{jeq}\le y_j
\qquad \forall j,e
$$

For each engineer:

$$
NoOverlap(\{I_{je}:j\in\mathcal J\})
$$

The engineer's assignment intervals must also not overlap any fixed unavailability interval in $\mathcal B_e$.

Therefore an engineer must be:

1. qualified,
2. rostered/available,
3. not assigned elsewhere at the same time.

### 4B. Pooled manpower and equipment

For every pooled resource $r$:

$$
Cumulative(\{I_j\},\{c_{jr}\},C_r)
$$

Equivalent time-indexed interpretation:

$$
\sum_{j:y_j=1}
c_{jr}\mathbf 1(s_j\le t<e_j)
\le C_r
\qquad \forall r,t
$$

This catches collective shortages even where no individual specialist is double-booked.

---

## Constraint 5 — Resource Transfer / Travel Time

If engineer $e$ is assigned to both $j$ and $k$, sufficient transfer time is required.

If $j$ occurs first:

$$
e_j+\tau^E_{e,jk}\le s_k
$$

If $k$ occurs first:

$$
e_k+\tau^E_{e,kj}\le s_j
$$

Hence:

$$
a_{je}=a_{ke}=1
\Rightarrow
(e_j+\tau^E_{e,jk}\le s_k)
\lor
(e_k+\tau^E_{e,kj}\le s_j)
$$

The same pattern can later be used for named vehicles or individually tracked equipment.

---

## Constraint 6 — Dependencies & Required Sequence

For every prerequisite $p\in Pred(j)$:

A dependent job cannot run unless its prerequisite also runs:

$$
y_j\le y_p
$$

If the dependent job is scheduled:

$$
s_j\ge e_p+\Delta_{pj}
$$

Dependencies should normally be stored explicitly by request/work-package ID.

The backend may later **suggest** dependencies from workflow rules, but a hard dependency should not be silently inferred from free text.

---

## Constraint 7 — Booking Commitment & Freeze Horizon

### 7A. Approved jobs remain scheduled

$$
A_j=1\Rightarrow y_j=1
$$

### 7B. Frozen jobs cannot move

$$
L_j=1\Rightarrow s_j=\bar s_j
$$

If individual specialist assignments are frozen too:

$$
x_{jeq}=\bar x_{jeq}
$$

for the stored approved allocation.

### 7C. Approved but non-frozen jobs may move

For $A_j=1,L_j=0$:

$$
s_j-\bar s_j\le M^{time}m_j
$$

$$
\bar s_j-s_j\le M^{time}m_j
$$

where $M^{time}$ is safely bounded by the planning horizon.

Thus:

$$
m_j=0\Rightarrow s_j=\bar s_j
$$

and moving the job forces $m_j=1$.

The objective will minimize such movements.

---

## Constraint 8 — Timing Flexibility & Deferral Eligibility

If scheduled:

$$
s_j\ge a_j
$$

$$
e_j\le b_j
$$

This handles exact-slot, flexible-range and any-time requests.

If the request cannot be deferred:

$$
D_j^{allow}=0\Rightarrow y_j=1
$$

If $D_j^{allow}=1$, the solver may choose $y_j=0$, unless another rule forces it to run tonight.

Therefore a job can be:

```text
time flexible = YES
deferrable = NO
```

meaning "choose any valid time tonight, but do not move it to another night."

---

## Constraint 9 — Service-Critical / Mandatory Work

If:

$$
M_j=1
$$

then:

$$
y_j=1
$$

This is intentionally a **hard rule**.

A solver may not resolve a difficult schedule by dropping a service-critical repair.

If mandatory work conflicts with an immutable frozen booking and no feasible schedule exists, the correct output is:

```text
INFEASIBLE — PLANNING OFFICER ESCALATION REQUIRED
```

### Mandatory vs urgency

```text
mandatory = hard feasibility rule
urgency score = optimization preference
```

An urgency score of 5 does not automatically make a request mandatory.

---

# 7. Preferred-Time Deviation

For a request with preferred start $p_j$:

$$
\delta_j\ge s_j-p_j
$$

$$
\delta_j\ge p_j-s_j
$$

so:

$$
\delta_j\ge|s_j-p_j|
$$

For requests without a preferred time:

$$
F_j=0\Rightarrow\delta_j=0
$$

---

# 8. Handback Margin

For each scheduled job:

$$
C_{\max}\ge e_j
$$

The spare margin before the usable engineering window closes is:

$$
Slack=T^{use}-C_{\max}
$$

Therefore minimizing $C_{\max}$ increases the spare handback margin.

---

# 9. Recommended Objective

A single weighted objective is possible, but arbitrary weights can create unintuitive trade-offs.

For this project, use **lexicographic optimization**: optimize one priority first, fix its best value, then optimize the next.

## Stage 0 — Hard feasibility

All nine hard constraints must hold.

Mandatory and frozen work are never automatically relaxed.

## Stage 1 — Preserve approved work

$$
\min
\sum_{j:A_j=1,L_j=0}m_j
$$

This prevents new non-critical requests from unnecessarily disturbing previously coordinated work.

## Stage 2 — Prioritize optional maintenance

Subject to the Stage 1 optimum:

$$
\max
\sum_j U_jy_j
$$

for eligible non-mandatory work.

The urgency score therefore acts as an **objective coefficient**, not a hard constraint.

## Stage 3 — Respect requester preferences

Subject to Stages 1 and 2 remaining optimal:

$$
\min
\sum_j F_j\delta_j
$$

## Stage 4 — Preserve spare handback margin

Finally:

$$
\min C_{\max}
$$

### Recommended priority order

```text
ALL HARD RULES
      ↓
minimum disruption to approved work
      ↓
maximum optional urgency completed
      ↓
minimum deviation from preferred times
      ↓
maximum spare handback margin
```

This deliberately makes schedule stability more important than a merely high urgency score. If a job genuinely justifies disrupting frozen/near-term planning, it should go through the controlled `mandatory/service-critical` pathway.

---

# 10. Solver Output

The scheduler should distinguish:

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNKNOWN / TIME LIMIT
```

Every proposed schedule should also be independently passed through the project's conflict checker before display or approval.

An infeasible result should explain the relevant jobs and constraints, for example:

```text
Mandatory request R17 requires protected sector S03.

Frozen approved request R04 occupies the same protected footprint.

No alternative slot remains before handback.

Result:
manual planning escalation required.
```

Do not claim that CP-SAT automatically provides a mathematically minimal infeasible subset unless an explicit minimization routine has been implemented.

---

# 11. Data Required for the Mock Dataset

The formulation tells us exactly what information the system needs.

## 11.1 Requester-submitted fields

| Field | Required? | Example |
|---|---:|---|
| `request_id` | System generated | `R017` |
| `requester_team` | Yes | `Track` |
| `work_type` | Yes | `Rail Replacement` |
| `asset_id` / `work_package_id` | Recommended | `RAIL-S03-17` |
| `sector_ids` | Yes | `["S03"]` |
| `duration_minutes` | Yes or catalogue default | `75` |
| `timing_mode` | Yes | `EXACT`, `RANGE`, `ANY_TIME` |
| `preferred_start` | If applicable | `02:00` |
| `earliest_start` | If range | `01:30` |
| `latest_finish` | If range | `03:30` |
| `deferrable` | Yes | `false` |
| `dependency_request_ids` | If applicable | `["R012"]` |
| `dependency_notes` | Optional | `Testing follows rail replacement` |
| `priority_reason` | Recommended | `Repeated defect detected` |

### Requesters should not usually choose these directly

```text
specific engineer ID
generic technician count
specific equipment unit
power-zone mapping
standard safety buffer
```

Where possible, these should come from controlled master data.

---

# 12. Backend Master / Reference Data

## 12.1 Job-Type Requirement Catalogue

Example:

```json
{
  "work_type": "RAIL_REPLACEMENT",
  "default_duration_minutes": 75,
  "required_engineer_roles": {
    "TRACK_ENGINEER": 1
  },
  "pooled_resources": {
    "GENERAL_TECHNICIAN": 3,
    "TRACK_MACHINE": 1
  },
  "power_requirement": "OFF",
  "default_protection_rule": "TRACK_WORK_STANDARD"
}
```

This is how:

```text
Rail Replacement
```

becomes:

```text
1 Track Engineer
3 Technicians
1 Track Machine
Power OFF
Required protection footprint
```

---

## 12.2 Engineer Roster

Suggested fields:

```text
engineer_id
skills / competencies
availability intervals
blocked intervals
base sector / location
```

Example:

```json
{
  "engineer_id": "E03",
  "skills": ["TRACK_ENGINEER", "PROTECTION"],
  "availability": [["01:15", "04:45"]],
  "base_sector": "S01"
}
```

---

## 12.3 Pooled Resource Inventory

Example:

```json
{
  "resource_type": "GENERAL_TECHNICIAN",
  "capacity": 5
}
```

```json
{
  "resource_type": "TRACK_MACHINE",
  "capacity": 1
}
```

---

## 12.4 Sector / Network Data

Suggested fields:

```text
sector_id
power_zone_id
fixed_unavailable_intervals
travel_time_to_other_sectors
protection relationships
```

---

## 12.5 Compatibility Rules

Example:

```json
{
  "work_type_a": "RAIL_REPLACEMENT",
  "work_type_b": "DYNAMIC_TEST",
  "compatible": false,
  "transition_minutes": 10
}
```

Compatibility must come from explicit planning assumptions/rules rather than being hidden inside solver code.

---

# 13. Planner-Controlled Fields

These high-impact fields should be controlled or confirmed by a planning officer or explicit business rule.

| Field | Reason |
|---|---|
| `mandatory_before_service` | Otherwise every requester could mark their own work mandatory |
| `urgency_score` | Requires a consistent prioritization policy |
| `approved_status` | Comes from workflow state |
| `frozen_status` | Derived from approval + freeze horizon |
| `manual_unlock` | Must be an explicit planning decision |
| unusual requirement overrides | May materially change feasibility |

---

# 14. Request-to-Solver Pipeline

```text
REQUESTER
submits:
work type
sector
duration
timing preference
deferral preference
dependency references
priority reason
        |
        v
JOB TYPE CATALOGUE
adds:
required competencies
pooled manpower
equipment
power requirement
protection rules
        |
        v
SECTOR / NETWORK DATA
adds:
power zone
availability
travel times
        |
        v
ENGINEER ROSTER
adds:
qualified candidates
availability
        |
        v
CURRENT PLAN
adds:
approved bookings
freeze status
        |
        v
PLANNING OFFICER / RULES
confirms:
mandatory status
urgency
special overrides
        |
        v
CP-SAT MODEL
        |
        v
FEASIBLE / OPTIMAL SCHEDULE
or
INFEASIBILITY EXPLANATION
```

The key design principle is:

> **The requester describes the work. The backend/master data determines what the work requires. The optimizer decides how to schedule and resource it.**

---

# 15. Minimum Synthetic Dataset

A useful demo dataset should contain approximately:

```text
6–10 maintenance requests
6–8 engineers
3–5 competency types
3–5 pooled resource types
6 sectors
2–3 power zones
1 engineering window
several approved bookings
at least 1 frozen booking
at least 1 dependency chain
at least 1 mandatory job
```

It should deliberately contain cases for:

1. engineering-window overflow,
2. sector/safety-footprint conflict,
3. ON/OFF power conflict,
4. unqualified engineer,
5. engineer double-booking,
6. pooled manpower shortage,
7. equipment shortage,
8. insufficient transfer time,
9. dependency violation,
10. frozen-booking conflict,
11. exact-time request,
12. flexible-range request,
13. any-time request,
14. deferrable request,
15. mandatory service-critical request,
16. at least one fully feasible schedule.

The expected solution must **not** be hard-coded. Changing input data should cause the solver to recompute the result.

---

# 16. Compact Mathematical Summary

The solver chooses:

$$
\{y_j,s_j,e_j,x_{jeq},m_j,\delta_j\}
$$

subject to:

$$
\boxed{
\begin{array}{ll}
1. & \text{Engineering window and handback}\\
2. & \text{Sector availability and safety footprint}\\
3. & \text{Work and traction-power compatibility}\\
4. & \text{Engineer qualification and pooled-resource capacity}\\
5. & \text{Resource transfer/travel time}\\
6. & \text{Dependencies and sequencing}\\
7. & \text{Approved-booking commitment and freeze horizon}\\
8. & \text{Timing flexibility and deferral rules}\\
9. & \text{Mandatory/service-critical execution}
\end{array}
}
$$

with lexicographic objectives:

$$
\boxed{
\begin{array}{ll}
\text{First:} & \min \text{ approved jobs moved}\\
\text{Second:} & \max \text{ optional urgency completed}\\
\text{Third:} & \min \text{ preferred-time deviation}\\
\text{Fourth:} & \min C_{\max}
\end{array}
}
$$

All hard constraints take priority over all optimization objectives.

---

# 17. Plain-Language Interpretation

The optimization model answers:

> **Given tonight's engineering window, current approved schedule, track availability, protection footprints, work/power compatibility, engineer roster, manpower/equipment limits, dependencies, requester flexibility and service-critical work, which jobs can be executed tonight, at what times and with which engineers—while disturbing the existing plan as little as possible and prioritizing the most important remaining maintenance?**
