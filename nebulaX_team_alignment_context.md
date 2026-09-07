# NEBULA X Track 1 — Shared Project Context & Alignment Note

> **Purpose:** Shared context handoff for the team. Feed this into your AI assistant so everyone stays aligned on the **problem, solution direction, architecture, constraints, data model, team split, and MVP scope**.

---

# 1. Challenge Context

## Problem Statement

**Scheduling riddle with conflicting requests — Track 1**

Rail assets require constant **maintenance, upgrades, and renewals**, all squeezed into short engineering hours when train services pause.

Schedulers receive many competing requests and must juggle:

- sector availability
- work compatibility
- engineer availability
- manpower
- equipment
- dependencies
- urgency / criticality
- engineering vehicle / transit requirements
- morning handback constraints

Conflicts are common because one maintenance request can interact with another across several dimensions at once.

## Challenge Goal

Build a tool that:

1. **automatically detects scheduling conflicts**
2. **flags and explains them clearly**
3. **suggests feasible alternatives**
4. **automates the scheduling workflow**

---

# 2. Core Product Idea

We are building a **browser-based maintenance scheduling and coordination platform**.

The platform should not only optimize a schedule. It should make conflicts **visually obvious, explainable, and actionable**.

> **Product concept:** A central visual maintenance coordination workspace that transforms competing maintenance requests into an explainable, conflict-free schedule.

---

# 3. Main User Roles

We only need **two actual product roles**.

## A. Requester

Possible requester teams:

- Track maintenance
- Signalling
- Power
- Rolling stock / systems
- Renewal / project teams

Requester can:

- submit a maintenance request
- specify preferred date/time
- specify work sector
- specify work type and duration
- specify manpower / skill requirements
- specify equipment requirements
- specify dependencies
- specify urgency / criticality
- see request status
- see proposed alternatives
- see final approved allocation

## B. Planning Officer / Scheduler

Officer can:

- view all requests
- view current engineering window
- see conflicts visually
- inspect conflict reasons
- generate alternative schedules
- compare proposed plans
- approve / publish the final plan
- view resource usage
- view change history / audit trail

---

# 4. Main Officer Dashboard Vision

The officer dashboard should be highly visual and diagrammatic.

It should answer:

- **WHERE** is the conflict?
- **WHEN** does it happen?
- **WHY** is it a conflict?
- **WHO / WHAT RESOURCE** is causing it?
- **WHAT can be changed to resolve it?**

## Suggested visual layout

```text
+-------------------------------------------------------------------+
|                    MAINTENANCE CONTROL CENTRE                     |
| Date | Engineering Window | Requests | Conflicts | Generate Plan  |
+-------------------------------------------------------------------+
|                                                                   |
|                        TRACK / SECTOR VIEW                        |
|                                                                   |
|  A --S01-- B --S02-- C --S03-- D --S04-- E --S05-- F            |
|       [ R03 ]     [ R01 ]              [ R04 ]                    |
|         \_________ shared power zone / conflict ________/          |
|                                                                   |
+--------------------------------------+----------------------------+
|             TIMELINE                 |      CONFLICT PANEL        |
|                                      |                            |
|  01:00  02:00  03:00  04:00        |  POWER CONFLICT            |
|  R01 ███████████                    |  R01 vs R03                |
|  R02    █████████                   |                            |
|  R03    ███████                     |  R01 requires OFF          |
|  R04         █████████              |  R03 requires ON           |
|                                      |                            |
|                                      |  [Generate Alternatives]   |
+--------------------------------------+----------------------------+
| Resources | Engineers | Equipment | Dependencies | Request Queue  |
+-------------------------------------------------------------------+
```

## Conflict visual categories

Use **colour + icon + text**, not colour alone.

Possible categories:

- `SECTOR / SPACE`
- `TIME WINDOW`
- `POWER / WORK COMPATIBILITY`
- `MANPOWER / ENGINEER`
- `EQUIPMENT`
- `DEPENDENCY`
- `VEHICLE / ACCESS ROUTE`
- `HANDOVER / MORNING BUFFER`

---

# 5. Core System Workflow

```text
REQUESTER SUBMITS WORK REQUEST
            |
            v
REQUEST VALIDATION
            |
            v
CONFLICT DETECTION ENGINE
            |
      +-----+------+
      |            |
      | no issue   | conflict
      v            v
   feasible     explain conflict
      |            |
      |            v
      |       CP-SAT SCHEDULER
      |            |
      |            v
      |      generate alternatives
      |            |
      +------------+
            |
            v
PLANNING OFFICER REVIEWS PROPOSAL
            |
            v
APPROVE / REJECT / REGENERATE
            |
            v
REVALIDATE CURRENT STATE
            |
            v
COMMIT FINAL SCHEDULE
            |
            v
TIMELINE + REQUEST STATUS UPDATE
```

---

# 6. Technical Architecture

Current direction:

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Current HTML/CSS/JS starter; React/Vite optional later | Dashboard, request form, timeline, conflict visualization |
| Backend | Python + FastAPI | API, validation, workflow, conflict checking |
| Optimizer | Google OR-Tools CP-SAT | Scheduling / alternative generation |
| Database | SQLite for MVP | Requests, allocations, resources, planning revisions |
| Authentication | Demo roles first; Supabase later if needed | Requester/officer identity |
| Initial Data | Synthetic JSON / DB seed | Demo railway + maintenance requests |

## High-level architecture

```text
                 FRONTEND
        Requester + Officer Views
                    |
                    | REST API
                    v
               FASTAPI BACKEND
        +-----------+-----------+
        |                       |
        v                       v
 CONFLICT CHECKER         CP-SAT OPTIMIZER
        |                       |
        +-----------+-----------+
                    |
                    v
                 DATABASE
        Requests / Resources / Rules
        Allocations / Proposals / Audit
```

---

# 7. Important Design Principle

## Conflict Checker and Optimizer are separate

### Conflict Checker

Answers:

> **Why does this proposed schedule fail?**

Example output:

```json
{
  "conflict_type": "POWER",
  "requests": ["R01", "R03"],
  "resource": "Z01",
  "start": "01:30",
  "end": "02:20",
  "reason": "R01 requires traction power OFF while R03 requires ON"
}
```

### CP-SAT Optimizer

Answers:

> **What feasible schedule can work instead?**

It can search over:

- start time
- permitted night / date
- eligible engineer
- equipment assignment
- sequencing
- optional deferral where allowed

### Final validation

Every schedule produced by CP-SAT should go back through the **independent conflict checker** before being shown as valid.

```text
CP-SAT generates plan
        |
        v
Independent checker validates
        |
   +----+----+
   |         |
 valid     reject
```

---

# 8. Synthetic Data Strategy

We currently do **not** have actual operator planning data.

Therefore, the MVP will use **clearly labelled synthetic data**.

Important principle:

> We invent the demo railway, requests, and constraints — but the software must genuinely calculate the conflicts and solutions.

Do **not** hard-code the expected final schedule.

When a user changes:

- request time
- duration
- engineer availability
- equipment availability
- priority
- sector

…the system should actually recalculate.

---

# 9. Core Data Model

The domain is formally implemented in `backend/app/models.py` using Pydantic v2 data classes.

## Maintenance Request (Job $j \in \mathcal{J}$)

```text
id                       (e.g., R01)
title                    (human-readable description)
status                   (submitted | scheduled | cancelled)
owner_id                 (requester team / user ID)
work_sector              (S_j: primary sector occupied)
protected_sectors        (Omega_j = S_j U Buf(j): total exclusion footprint)
power_zone               (z in Z: affected traction power zone)
power_requirement        (ON | OFF | NONE; legacy ANY maps to NONE)
phases                   (setup, work, test, handback; sum = duration D_j)
required_skill           (track | inspection | signalling | ...)
eligible_engineers       (list of qualified engineer IDs)
preferred_engineer       (soft preference)
required_equipment_ids   (c_j,r: specific equipment units consumed)
technicians_required     (c_j,tech: cumulative pooled manpower demand)
preferred_start          (requested start datetime)
earliest_start           (hard lower bound)
deadline                 (hard upper bound)
allowed_dates            (eligible schedule dates)
depends_on               (Pred(j): prerequisite work order IDs)
handover_buffer_minutes  (Delta_p,j: clearance buffer after prerequisite)
priority_score           (W_j: 1 to 10 asset failure risk / urgency)
mandatory                (whether job must be scheduled or can be deferred)
split_allowed            (whether job may be partitioned into sub-phases)
```

## Track Sector & Station (Set $\mathcal{S}$)

```text
Station:
  id                     (e.g., N01)
  name                   (e.g., Demo Station A)
  schematic_x            (display grid coordinate)

Sector:
  id                     (e.g., S01)
  from_station           (origin station ID)
  to_station             (destination station ID)
  direction              (track travel direction)
  power_zone             (associated traction power zone ID)
  exclusive_protection   (boolean flag)
```

## Traction Power Zone (Set $\mathcal{Z}$)

```text
power_zone_id            (e.g., Z01)
sector_ids               (S_z subset of S: physical sectors fed by this zone)
```

## Engineering Windows & Blackouts (Set $\mathcal{B}$)

```text
EngineeringWindow:
  date                   (e.g., 2026-09-14)
  sector_ids             (sectors open for engineering hours)
  start                  (window open datetime, e.g. 01:15)
  end                    (window close datetime, e.g. 04:45)

Blackout (Closure/Freeze):
  id                     (e.g., B01)
  sector_ids             (sectors barred from work and transit)
  start                  (freeze start datetime)
  end                    (freeze end datetime)
  reason                 (e.g., system commissioning, third-party work)
```

## Resources (Set $\mathcal{R}$)

```text
Engineer:
  id                     (e.g., E01)
  name                   (personnel name)
  skills                 (list of certifications)
  initial_sector         (starting depot or sector)
  availability           (list of available TimeWindows)
  unavailable            (list of absence/maintenance TimeWindows)

Equipment:
  id                     (e.g., Q01)
  type                   (track_machine | inspection_kit | test_kit)
  initial_sector         (starting depot or sector)
  capacity               (unit capacity = 1)
  availability           (available TimeWindows)
  unavailable            (maintenance TimeWindows)
  serviceable            (boolean operational flag)

ResourcePool:
  id                     (e.g., TECH, TPO)
  name                   (Interchangeable general technicians / officers)
  capacity               (C_r: maximum concurrent capacity)
```

## Engineering Vehicles & Transit Corridors (Set $\mathcal{V}$, §5D)

```text
TransitLeg:
  sector_id              (sector traversed)
  travel_minutes         (tau_v,s: travel duration across sector)

TransitRoute:
  origin_depot           (starting base/siding)
  destination_sector     (target worksite sector)
  legs                   (ordered list of TransitLegs)

TransitSchedule:
  vehicle_id             (vehicle ID)
  sector_id              (sector occupied during transit)
  start                  (start of transit interval)
  end                    (end of transit interval = start + tau_v,s)

Vehicle:
  id                     (e.g., V01)
  name                   (e.g., Tamping Train TT-01)
  type                   (LOCOMOTIVE | TAMPING_MACHINE | INSPECTION_TRAIN)
  home_depot             (base depot location)
  availability           (available TimeWindows)
  routes                 (predefined transit corridors to worksites)
```

## Allocation & Schedule Output

```text
request_id               (target job j)
start                    (scheduled start datetime)
end                      (scheduled completion datetime)
engineer_id              (assigned lead engineer)
equipment_ids            (assigned equipment units)
locked                   (boolean: committed historical booking)
```

## Planning Rules & Parameters

```text
start_grid_minutes       (discrete scheduling step, e.g. 5 mins)
different_site_transfer  (transfer travel allowance, e.g. 15 mins)
opposed_power_transition (power switching guard, e.g. 10 mins)
morning_buffer_minutes   (T_buffer revenue protection margin, e.g. 20 mins)
power_values             ([ON, OFF, NONE])
power_compatibility      (compatibility truth table)
unknown_rule_policy      (REVIEW_REQUIRED)
```

## Conflict Model

```text
code                     (SPACE | POWER | ENGINEER | EQUIPMENT | DEPENDENCY |
                          MANPOWER | ENGINEERING_WINDOW | BLACKOUT |
                          VEHICLE_TRANSIT | LOCKED_BOOKING)
request_ids              (conflicting work order IDs)
message                  (human-readable explanation)
resource                 (conflicted sector, zone, or equipment ID)
severity                 (error | warning)
```

---

# 10. Mathematical Scheduling Model

The formulation is specified in detail in `constraints & LP setup.md`. It is an **integer constraint optimization / CP-SAT scheduling model** operating on a discrete-time horizon:

$$
\mathcal T=\{0,1,\ldots,T\}
$$

where each integer step represents 1 minute. For an illustrative engineering window of 01:15 to 04:45, $T = 210$ minutes. With a mandatory handback buffer $B = 20$ minutes, the usable window deadline is:

$$
T^{use} = T - B = 190 \text{ minutes (04:25)}
$$

---

# 11. Sets / Entities in the Optimization Model

| Symbol | Entity | Description |
|---|---|---|
| $j, k \in \mathcal{J}$ | Work orders | Maintenance requests submitted for execution |
| $s \in \mathcal{S}$ | Track sectors | Discrete track blocks across the rail corridor |
| $z \in \mathcal{Z}$ | Power zones | Traction-power feeding sections ($\mathcal{S}_z \subset \mathcal{S}$) |
| $e \in \mathcal{E}$ | Specialist engineers | Individually tracked and rostered personnel |
| $q \in \mathcal{K}$ | Competency types | Specialist roles/certifications (e.g., TRACK, SIGNALLING, INSPECTION) |
| $r \in \mathcal{R}$ | Pooled resources | Fungible capacity (technicians, tamping machines, test kits) |
| $p \in Pred(j)$ | Prerequisites | Immediate prerequisite work orders required before job $j$ |
| $b \in \mathcal{B}_s$ | Sector unavailabilities | Confirmed blackout/closure intervals for sector $s$ |
| $h \in \mathcal{B}_e$ | Engineer unavailabilities | Blocked / absence intervals for engineer $e$ |
| $v \in \mathcal{V}$ | Engineering vehicles | Heavy vehicles moving between depots and worksites |

---

# 12. Work Order Attributes & Parameters

For each maintenance request $j \in \mathcal{J}$:

```text
d_j       Total reserved duration (setup + work + test + handback)
Omega_j   Total spatial footprint (work sector S_j + safety buffer Buf(j))
Z_j       Affected traction-power zone(s)
P_j       Traction power requirement: ON, OFF, or NONE (legacy ANY maps to NONE)
a_j, b_j  Earliest allowed start and latest allowed finish
p_j, F_j  Preferred start time and indicator flag (F_j = 1 if preferred time given)
D_j^allow Deferral eligibility flag (1 = may be deferred; 0 = must run tonight)
M_j       Service-critical / mandatory flag (1 = hard requirement before next service)
A_j       Approved booking flag (1 = already approved in previous planning cycle)
L_j       Frozen booking flag (1 = approved and inside the freeze horizon H^freeze)
\bar{s}_j Existing approved start time (if A_j = 1)
U_j       Urgency score for optional non-mandatory work (1–5)
n_jq      Specialist engineer role slots of competency q required
c_jr      Quantity of pooled resource r consumed
Delta_pj  Handover / clearance buffer margin following prerequisite p
```

---

# 13. The 9 Real-World Constraints

### 1. Engineering Window & Handback
Every scheduled job must fit inside the engineering window and complete before the morning handback buffer:
$$s_j \ge 0, \qquad e_j = s_j + d_j \le T^{use} \quad \forall j \text{ where } y_j = 1$$

### 2. Sector Availability & Safety Footprint
- **2A. Fixed sector unavailability ($\mathcal{B}_s$):** Scheduled work cannot overlap confirmed blackout/closure intervals in its footprint:
  $$(e_j \le \alpha_{sb}) \lor (s_j \ge \beta_{sb}) \quad \forall [\alpha_{sb}, \beta_{sb}) \in \mathcal{B}_s, \; s \in \Omega_j$$
- **2B. Mutually exclusive footprints ($C^{sector}_{jk} = 1$):** Jobs whose protected spatial footprints overlap cannot run concurrently:
  $$(e_j \le s_k) \lor (e_k \le s_j)$$

### 3. Work & Traction-Power Compatibility
Concurrent jobs must satisfy compatibility rules. If jobs require opposing power (`ON` vs `OFF`) in a shared zone ($C^{power}_{jk}=1$) or are work-incompatible ($C^{work}_{jk}=1$), they must be separated by transition guard $g_{jk}$:
$$(e_j + g_{jk} \le s_k) \lor (e_k + g_{kj} \le s_j)$$

### 4. Resource Requirements, Qualification & Capacity
- **4A. Specialist engineers ($e \in \mathcal{E}, q \in \mathcal{K}$):** Every job receives its required qualified specialists ($x_{jeq} \le Q_{eq}$); engineers cannot be double-booked ($\text{NoOverlap}(\{I_{je}\})$) or assigned during unavailability $\mathcal{B}_e$.
- **4B. Pooled manpower & equipment ($r \in \mathcal{R}$):** Concurrent demand across active jobs cannot exceed fleet/pool capacity $C_r$ ($\text{Cumulative}(\{I_j\}, \{c_{jr}\}, C_r)$).

### 5. Resource Transfer / Travel Time
A specialist engineer or individually tracked vehicle/equipment assigned to consecutive jobs $j$ and $k$ must have sufficient time to travel between locations:
$$(e_j + \tau^E_{e,jk} \le s_k) \lor (e_k + \tau^E_{e,kj} \le s_j)$$

### 6. Dependencies & Required Sequence
For every prerequisite $p \in Pred(j)$, a dependent job cannot proceed if its prerequisite is deferred ($y_j \le y_p$), and must observe the clearance buffer:
$$s_j \ge e_p + \Delta_{pj}$$

### 7. Booking Commitment & Freeze Horizon
- Approved jobs remain scheduled: $A_j = 1 \implies y_j = 1$.
- Frozen jobs within freeze horizon $H^{freeze}$ cannot move: $L_j = 1 \implies s_j = \bar{s}_j$.
- Approved non-frozen jobs ($A_j = 1, L_j = 0$) may move only if necessary, with movements tracked via binary indicator $m_j \in \{0, 1\}$.

### 8. Request Timing Flexibility & Deferral Eligibility
Handles `EXACT` slot ($a_j = p_j, b_j = p_j + d_j$), `RANGE` ($a_j \le s_j, e_j \le b_j$), and `ANY_TIME` ($a_j = 0, b_j = T^{use}$). If $D_j^{allow} = 0$, deferral is barred ($y_j = 1$).

### 9. Service-Critical / Mandatory Work
If $M_j = 1$, then $y_j = 1$ is an unyielding hard rule. The solver cannot resolve a conflict by dropping safety-critical work. If an impasse occurs with a frozen booking, the system raises an **escalation alert**.

---

# 14. Decision Variables

```text
y_j \in {0, 1}          1 if job j is scheduled tonight; 0 if deferred
s_j, e_j \in Z_{>=0}    Start and completion minute (e_j = s_j + d_j)
I_j                     Optional interval variable [s_j, d_j, e_j] active if y_j = 1
x_jeq \in {0, 1}        Assignment of engineer e to competency role q on job j
I_je                    Optional engineer assignment interval
m_j \in {0, 1}          1 if approved start time \bar{s}_j was moved; 0 if preserved
\delta_j >= 0           Absolute deviation from preferred start |s_j - p_j|
C_max >= 0              Latest completion time among scheduled jobs
I_{v,s}                 Transit corridor interval for vehicle v through sector s
```

---

# 15. Lexicographic Optimization Objectives

Rather than arbitrary weighting, the engine solves using **lexicographic stages**:

```text
STAGE 0: ALL 9 HARD CONSTRAINTS SATISFIED
             ↓
STAGE 1: MINIMIZE APPROVED JOBS MOVED
         min \sum_{j: A_j=1, L_j=0} m_j
             ↓
STAGE 2: MAXIMIZE OPTIONAL URGENCY COMPLETED
         max \sum_j U_j y_j
             ↓
STAGE 3: MINIMIZE PREFERRED-TIME DEVIATION
         min \sum_j F_j \delta_j
             ↓
STAGE 4: PRESERVE SPARE HANDBACK MARGIN
         min C_max  (maximizes Slack = T^use - C_max)
```

Schedule stability takes precedence over optional work urgency.

---

# 16. Infeasibility & Alternative Generation

When constraints make scheduling all work orders mathematically infeasible, the engine does **not** silently drop mandatory work.

Instead:

```text
NO FEASIBLE PLAN
      |
      v
Identify conflicting constraints & work orders
      |
      v
Generate explainable repair alternatives
```

Possible repairs:
- **Alternative A (Temporal Shift):** Move non-frozen jobs earlier/later within allowed engineering hours.
- **Alternative B (Specialist Reassignment):** Assign another qualified engineer who possesses competency $q$.
- **Alternative C (Equipment Substitution):** Reassign an equivalent serviceable equipment unit.
- **Alternative D (Sequence Inversion):** Invert execution order between non-dependent tasks.
- **Alternative E (Opportunistic Deferral):** Defer non-mandatory jobs ($D_j^{allow} = 1$) with lower urgency scores $U_j$.

---

# 17. Infeasibility Explanation Note

When explaining infeasibilities, provide the exact conflicting work orders, sectors, resources, or frozen bookings. Avoid asserting mathematical minimality ("Minimal Unsatisfiable Subset" / MUS) unless an explicit minimal-cardinality extraction algorithm has run.

---

# 18. Visual Before / After Scheduling

A strong demo feature should be:

## Requested Plan

```text
4 conflicts

POWER
ENGINEER
EQUIPMENT
DEPENDENCY
```

Officer clicks:

```text
GENERATE OPTIMAL PLAN
```

CP-SAT calculates a repair.

## Proposed Plan

```text
0 hard conflicts
2 requests shifted
1 engineer reassigned
0 locked bookings changed
```

Example:

```text
R03

Requested:
01:30 ---------------- 02:30

Proposed:
          02:30 ---------------- 03:30
```

This makes the optimization visible and explainable.

---

# 19. Planned MVP Pages

## Page 1 — Login

For now:

```text
Requester
Planning Officer
```

Do not expose separate "Track Team / Systems Team / Officer" as three product roles.

Those are just different requester identities.

Later with authentication:

```text
User
- role: requester
- team: Track

User
- role: requester
- team: Signalling

User
- role: officer
- team: Planning
```

## Page 2 — Requester

```text
New Request
My Requests
Request Status
Proposed Alternative
Final Allocation
```

## Page 3 — Officer Dashboard

```text
Request Queue

Track Map
Timeline
Conflict Inspector

Engineer Availability
Equipment Availability
Dependencies

Generate Alternatives
Compare Proposed Plans
Approve / Publish
```

---

# 20. Authentication Direction

Authentication is **not the priority yet**.

For MVP:

```text
demo login / role selection
```

Later:

```text
Supabase Auth
```

If Supabase is added:

- Supabase verifies identity
- backend determines requester/officer role
- browser should never be trusted to decide its own permissions
- real secrets stay in `.env`
- privileged keys must never be committed to GitHub

---

# 21. Current Repository Direction

GitHub repository:

```text
ooixinyien-lab/lta-nebulaX
```

Main project folder:

```text
nebulaX/
```

Current architecture:

```text
nebulaX/
|
+-- frontend/
|
+-- backend/
|   +-- app/
|       +-- api/
|       +-- auth/
|       +-- services/
|           +-- checker.py
|           +-- cp_sat.py
|           +-- scheduler.py
|           +-- demo_search.py
|
+-- data/
|
+-- docs/
|
+-- scripts/
|
+-- requirements.txt
+-- requirements-cpsat.txt
+-- README.md
```

---

# 22. Git Workflow

`main` should be the shared stable baseline.

Each major workstream should use a feature branch.

Suggested branches:

```text
feature/data-domain
feature/conflict-engine
feature/cp-sat
feature/officer-dashboard
feature/supabase-auth
```

Workflow:

```text
feature branch
      |
      v
Pull Request
      |
      v
review
      |
      v
main
```

---

# 23. Team Split

Recommended four-person split:

## Person 1 — Data + Domain Model

Not just "dummy data".

Owns:

- `backend/app/models.py` (Pydantic v2 data classes modeling all sets, parameters, and constraints)
- request schema
- sector & station schema
- power zone model
- blackout period model
- engineering vehicle & transit corridor model
- engineer & equipment schema
- resource pool capacities
- planning rules & compatibility matrix
- synthetic demo dataset & mock data generators
- test scenarios
- domain assumptions

Deliverables:

```text
backend/app/models.py (Pydantic v2 domain model)
DATA_CONTRACT.md
demo_data.json

conflict scenarios:
- sector / spatial conflict
- power zone conflict (ON vs OFF vs NONE)
- manpower shortage (cumulative capacity)
- equipment conflict (inter-site transfer allowance)
- dependency violation & clearance buffer
- engineering window violation
- blackout period violation
- vehicle transit corridor blockage

plus:
- at least one fully feasible scenario
```

## Person 2 — Conflict Engine + Backend

Owns:

```text
checker.py
FastAPI routes
database workflow
structured conflict output
```

Goal:

```text
given a proposed allocation
        |
        v
detect all modelled conflicts
        |
        v
return structured explanations
```

## Person 3 — CP-SAT Optimization

Owns:

```text
cp_sat.py
scheduler.py
```

Goal:

```text
requests + constraints
        |
        v
find feasible assignments
        |
        v
rank alternatives
```

Tasks:

- interval variables
- NoOverlap
- cumulative resources
- dependencies
- accepted/deferred task variables
- engineer/equipment assignment
- objective function
- alternative generation
- solver status handling

## Person 4 — Frontend / Visualization

Owns:

```text
Requester UI
Officer dashboard
Track map
Timeline
Conflict visualization
Alternative comparison
Approval flow
```

Important:

Frontend should **display** backend logic.

Do not duplicate planning rules in JavaScript.

---

# 24. Integration Contract

Before everyone codes independently, the team must agree on:

1. request schema
2. conflict types
3. API request / response shape
4. demo scenario
5. hard vs soft constraints
6. field naming conventions

Example shared request format:

```json
{
  "request_id": "R04",
  "requester_team": "Track",
  "work_type": "Rail repair",
  "sector_ids": ["S04"],
  "protected_sector_ids": ["S03", "S04"],
  "preferred_start": "2026-09-14T02:00:00+08:00",
  "duration_minutes": 75,
  "required_skill": "TRACK",
  "required_equipment_type": "TRACK_MACHINE",
  "power_requirement": "OFF",
  "priority": 4,
  "dependencies": []
}
```

---

# 25. Current MVP Scope

First prove this vertical slice:

```text
Requester submits request
        |
        v
Request stored
        |
        v
Officer sees request
        |
        v
Conflict checker detects conflict
        |
        v
Officer sees visual explanation
        |
        v
CP-SAT generates alternative
        |
        v
Independent checker validates it
        |
        v
Officer approves
        |
        v
Final schedule updates
```

If this works reliably, the core challenge is solved.

---

# 26. Features We Should NOT Prioritize Yet

Do not distract the team with these before the scheduling workflow works:

- chatbot
- LLM scheduling
- multi-agent negotiation
- predictive maintenance AI
- full Singapore rail digital twin
- live TAMS integration
- real traction power control
- complicated deployment
- overly detailed authentication

These can be stretch features.

---

# 27. Potential Higher-Order / Stretch Features

## A. Explainable Schedule Repair

Instead of:

```text
Conflict detected
```

say:

```text
R03 cannot begin at 01:30 because:

1. prerequisite R01 ends at 02:20
2. shared power zone Z01 has opposing requirements
3. required transition buffer has not elapsed

Earliest feasible start:
02:30
```

## B. What-If Analysis

Example:

```text
What if another qualified engineer is available?

What if equipment Q01 becomes unavailable?

What if R04 becomes critical?

What if engineering hours are shortened by 20 minutes?
```

Re-run solver and show impact.

## C. Bottleneck Detection

Example:

```text
Current bottleneck:
Qualified track engineer availability

Adding another generic technician
does not improve schedule feasibility.
```

## D. Engineering Vehicle Route Conflict

Show that two worksites may individually be free, but a maintenance vehicle cannot travel through an occupied route.

## E. Schedule Resilience

Future version:

- model delays / overruns
- preserve morning handback margin
- re-plan dynamically after a disruption

---

# 28. Important Assumptions / Unknowns

We do **not yet know**:

- exact LTA definition of a sector
- actual power-zone boundaries
- actual engineering windows
- real compatibility matrix
- actual engineer qualifications
- actual manpower requirements
- actual equipment inventory
- actual access-route rules
- whether jobs may be split
- whether approved shared work is allowed
- how existing TAMS is integrated internally

Therefore:

> The MVP uses **synthetic but internally consistent assumptions**.

Any actual operational rules provided later by LTA should replace the synthetic rules.

---

# 29. Success Criteria for the Demo

The demo should prove that the system is **dynamic**, not hard-coded.

Suggested demo:

1. Show current requests.
2. Show 3-4 hidden conflicts.
3. Click one conflict and highlight:
   - affected track sector
   - timeline overlap
   - engineer/equipment
   - reason
4. Click **Generate Plan**.
5. Show repaired timeline.
6. Explain what changed.
7. Mark one engineer unavailable live.
8. Re-run.
9. Show that the schedule changes again.
10. Approve and publish final plan.

---

# 30. Evaluation Metrics

For synthetic testing, measure:

- number of hard conflicts before / after
- mandatory jobs successfully scheduled
- high-priority work completed
- jobs deferred
- existing allocations moved
- total shift from preferred start times
- engineer reassignment count
- equipment utilization
- remaining morning buffer
- solver runtime

Do not claim real operational savings unless validated with real operator data.

---

# 31. One-Line Product Pitch

> **nebulaX is a visual railway maintenance coordination platform that detects hidden conflicts across track access, work compatibility, manpower, equipment and dependencies, then uses constraint optimization to generate and explain feasible maintenance schedules.**

---

# 32. Short Alignment Summary

The product is **not just a calendar**.

It combines:

```text
VISUALIZE
track + timeline + resources

        +

DIAGNOSE
why requests conflict

        +

OPTIMIZE
find feasible alternatives

        +

COORDINATE
review + approve + publish
```

The current technical core is:

```text
Synthetic data
      |
      v
FastAPI
      |
      +--> Conflict Checker
      |
      +--> CP-SAT Optimizer
      |
      v
SQLite
      |
      v
Visual Officer Dashboard
```

The first priority is getting the entire request-to-approved-schedule workflow working reliably.

Only after that should we add more advanced AI or integration features.

---

# 33. Constraint Specification Source Note

The current mathematical formulation used by the team is defined in `constraints & LP setup.md`. It specifies a minute-level discrete planning horizon, handback buffer protection, the 9 real-world hard constraints (engineering window, sector availability/unavailability, work/power compatibility, specialist engineer competencies and pooled resource capacities, transfer travel times, dependencies, booking commitments/freeze horizon, timing flexibility/deferral, and mandatory work), alongside lexicographic optimization stages.

This alignment note translates that mathematical model into implementation, data classes (`backend/app/models.py`), and product architecture for the whole team.

