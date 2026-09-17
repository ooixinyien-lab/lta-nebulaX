# NebulaX Demonstration Script

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> All presentations, walkthroughs, and demo videos must reflect [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md).
>
> **Target:** First place in Problem Statement 1 (PS1).
> The demonstration must showcase full activity workload satisfaction, Scenario A/B/C performance, official scoring, and disruption replanning.

---

## Part 1: Official PS1 Challenge Demonstration (Target Workflow)

This script outlines the official 3-minute hackathon video and judge presentation workflow.

### 1. Establish the Problem and Source of Truth
- Show [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md) and the 8 official CSV input files (`01_LINES.csv` through `08_ACTIVITY_DETAILS.csv`).
- Explain the real railway challenge: scheduling 54 activities across 14 contracts and 76 network locations over a 30-week horizon.
- Emphasise **Priority 1: 100% complete activity workloads** (192 workload units). In PS1, dropping or deferring work is strictly forbidden.

### 2. Multi-Scenario Solving (Scenarios A, B, C)
- **Scenario A (Strict Supply):** Demonstrate strict capacity compliance where location excess is forbidden; show the solver finding a complete schedule with minimal activity overrun penalty ($P$). Note that lower bounds (e.g. A036 and A059) prove that a non-zero penalty is unavoidable under weekly frequency rules.
- **Scenario B (Strict Schedule):** Demonstrate strict adherence to planned completion dates (zero overrun permitted); show how flexible location supply and ECLO accesses are leveraged at minimal penalty ($7V + 5E$).
- **Scenario C (Balanced Trade-Off):** Demonstrate joint optimisation of overrun, supply excess (max 1 slot/loc-wk), and line-specific ECLO windows ($\le 2$ weeks per line) to minimise $P + 7V + 5E$.

### 3. Disruption Replanning Demonstration (Winning Differentiator)
- Inject an unexpected disruption: reduce nominal possession supply at a critical interchange bottleneck.
- Automatically identify the specific invalidated location possessions.
- Trigger the replan: show the solver re-routing and rescheduling affected activities while preserving unaffected commitments where possible.
- Present the before/after operational comparison and objective score breakdown grounded in binding constraints.

### 4. Verification and Official Exports
- Display the independent validation results covering workload yield, legal possession mixes, buffer footprints, and contract workfronts.
- Download and inspect the three generated scenario artifacts:
  - `SCHEDULE_ACCESS.csv` (192 access rows);
  - `SCHEDULE_OCCUPANCY.csv` (core location possession groups);
  - `RESULTS.csv` (simulated completion date and overrun days per contract).

---

## Part 2: Legacy Synthetic Prototype Walkthrough (Historical Scaffold)

*Note: This walkthrough demonstrates the application UI infrastructure (FastAPI, auth, transactions, audit). The single-night model is retired as PS1 authority because its recovery mode defers 5 of 12 requests, violating PS1's full-workload baseline.*

1. **Start the app:** Run `python -m uvicorn backend.app.main:app --reload`.
2. **Planning officer view:** Select Planning Officer, inspect the 12 synthetic requests, and click **Generate proposal**.
3. **Recovery review:** Review the returned status and note the 7 scheduled requests and 5 deferred requests (historical synthetic behavior).
4. **Publish transaction:** Click **Approve & publish**; show that the backend commits all bookings atomically and bumps the planning revision.
5. **Stale proposal rejection:** Change a resource's availability to demonstrate that older proposals are invalidated.

