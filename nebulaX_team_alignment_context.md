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

The current optimization direction is a **discrete-time CP-SAT Constraint Satisfaction and Optimization Problem**.

The planning horizon is modeled in minute-level time steps.

The current constraints document uses an illustrative engineering window of:

```text
01:15 -> 04:45
210 minutes total
```

This is a **model assumption from the current constraint specification**, not something we should present as a universal Singapore rail engineering window.

---

# 11. Sets / Entities in the Optimization Model

The current model includes:

- maintenance requests / work orders
- discrete track sectors
- traction power zones
- shared operational resources
- engineering vehicles

Conceptually:

```text
Jobs        J
Sectors     S
Power Zones Z
Resources   R
Vehicles    V
Blackouts   B
```

---

# 12. Work Order Attributes

For each maintenance request `j`, the model currently considers:

```text
D_j       duration

S_j       work sectors

Buf(j)    safety buffer sectors

Omega_j   total footprint
           = work sectors + safety buffer

P_j       traction power requirement
           ON / OFF / NONE (legacy "ANY" maps to "NONE")

W_j       urgency / criticality score (1-10)

c_jr      quantity of resource r consumed (equipment units, pooled technicians)

Pred(j)   prerequisite jobs

Delta_pj  required handover / clearance buffer margin
```

---

# 13. Core Conflict Types / Hard Constraints

## A. Engineering Window / Morning Handback

Every scheduled task must:

- start within the allowed engineering window
- finish within the window
- preserve a final clearance / morning sweep buffer

```text
JOB
|-----------------------|

Engineering window
|-----------------------------------|

                             |buffer|
```

---

## B. Spatial Conflict / Safety Buffer

A job does not only occupy its direct work area.

It can also require adjacent protection / buffer sectors.

```text
          protected footprint

      +-----------------------+
      |                       |
---- S01 ---- S02 ---- S03 ---- S04 ----
             ^^^^^
            work area
```

If two jobs' protected footprints overlap, they may not be able to run simultaneously.

Current model concept:

```text
NoOverlap(all jobs occupying the same protected sector)
```

---

## C. Traction Power Compatibility

Two jobs can be in **different physical sectors** but share the same traction power zone.

Example:

```text
            POWER ZONE Z01
     +----------------------------+

A ---- S01 ---- B ---- S02 ---- C

R03: S01 requires ON
R01: S02 requires OFF
```

Even though the work locations differ:

```text
ON != OFF
```

therefore they cannot overlap if they affect the same power zone.

---

## D. Engineering Vehicle / Transit Corridor Conflict

Engineering trains or maintenance vehicles may need to travel through sectors to reach worksites.

Therefore:

```text
worksite available
```

does **not** automatically mean:

```text
job executable
```

The route into or out of the worksite may be blocked.

```text
Depot ---- S01 ---- S02 ---- S03 ---- Worksite

                    XXXXX
                another worksite

vehicle cannot reach destination
```

The current formulation includes transit intervals for engineering vehicles and prevents incompatible overlap with stationary work intervals.

For MVP, if real route data is unavailable, use **explicit synthetic predefined routes**.

Do not infer real authorised engineering routes from MRT station coordinates.

---

## E. Manpower and Equipment Capacity

Resource conflicts are not only pairwise.

Example:

```text
Job A needs 2 technicians
Job B needs 2 technicians
Job C needs 2 technicians

Available technicians = 4
```

Each pair may be feasible.

But:

```text
A + B + C = 6 > 4
```

The full schedule is infeasible.

CP-SAT should use **cumulative resource constraints** for these cases.

Resources may include:

- technicians
- qualified engineers
- Track Protection Officers
- engineering trains
- tamping machines
- inspection equipment
- locomotives
- other shared equipment

---

## F. Dependencies / Precedence

Some jobs can only happen after another job is complete.

Example:

```text
R01 rail repair
      |
      v
R03 signalling verification
```

Constraint:

```text
R03 cannot begin before R01 completes
+ required handover / clearance buffer
```

If R01 is deferred, R03 may also need to be deferred.

---

## G. Blackout Periods / Track Maintenance Freezes

Certain track sectors may be subject to scheduled blackout windows (e.g. system upgrades, third-party infrastructure works, or power isolation testing).

```text
Track Sector: ---- S01 ---- S02 ---- S03 ---- S04 ----
Blackout B01:               |==== BLACKOUT ====|
                             (No work / No transit)
```

Constraint:

- No maintenance work order ($j \in \mathcal{J}$) whose spatial footprint $\Omega_j$ overlaps the blackout sectors may be scheduled during the blackout window.
- No engineering vehicle transit interval ($I_{v,s}$) may traverse the blackout sectors during the blackout window.

---

# 14. Decision Variables

Current CP-SAT formulation includes:

```text
y_j
whether job j is scheduled tonight

start_j
job start time

end_j
job completion time

I_j
job interval

I_v,s
engineering vehicle transit interval
```

Future / extended model can also include:

```text
engineer assignment
equipment assignment
night/date assignment
approved execution mode
```

---

# 15. Optimization Objective

Current objective direction:

## Primary goal

Schedule **high-priority / high-criticality work** where possible.

## Secondary goals

- finish jobs earlier
- preserve handback margin
- reduce unnecessary vehicle transit
- minimize unnecessary schedule changes
- minimize deviation from preferred time
- minimize engineer reassignment
- minimize low-value deferrals

Conceptually:

```text
MAXIMIZE
maintenance value completed

MINIMIZE
delay
schedule disruption
resource friction
deadhead travel
```

Prefer strict objective ordering where possible:

1. satisfy all hard constraints
2. preserve mandatory work
3. maximize high-priority work
4. minimize changes to existing allocations
5. minimize deviation from requested time

---

# 16. Infeasibility / Alternative Generation

If all requests cannot fit, the system should **not silently force them into the schedule**.

Instead:

```text
NO FEASIBLE PLAN
      |
      v
identify conflicting constraints / requests
      |
      v
generate alternative repairs
```

Possible repairs:

## Alternative A — Temporal Shift

Move a job later / earlier.

```text
Requested
01:30 -------- 02:30

Suggested
         02:30 -------- 03:30
```

## Alternative B — Different Engineer

Where another engineer has the required qualification.

## Alternative C — Different Equipment

Where an equivalent serviceable unit exists.

## Alternative D — Change Sequence

Run one task before another.

## Alternative E — Defer Lower-Priority Job

Move a lower-criticality task to the next allowed night.

## Alternative F — Shared / Bundled Window

Potential future feature.

Compatible jobs may be grouped under one coordinated access arrangement, **only if explicitly allowed by the planning rules**.

---

# 17. Important Caveat About "MUS"

The current constraints document proposes identifying a **Minimal Unsatisfiable Subset (MUS)**.

For implementation, be careful with this wording.

A practical first version can:

- identify a small or sufficient conflicting subset
- show which requests and constraints make the plan infeasible
- generate repair scenarios

Do not claim the tool mathematically guarantees the **smallest possible** root-cause subset unless that behavior is explicitly implemented and verified.

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

The current mathematical formulation used by the team defines a minute-level discrete planning horizon, explicit sectors, traction power zones, shared resources, engineering vehicles, optional scheduling variables, safety-buffer footprints, power compatibility, vehicle-transit interlocking, cumulative resource capacity, work-order dependencies, and a multi-objective scheduling direction.

This alignment note preserves that structure but translates it into implementation and product language for the whole team.
