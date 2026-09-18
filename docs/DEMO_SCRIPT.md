# NebulaX Demonstration Script

> [!IMPORTANT]
> **AUTHORITATIVE SOURCE OF TRUTH: [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md)**  
> All presentations, walkthroughs, and demo videos must reflect [PS1_OFFICIAL_ADOPTION_PLAN.md](../PS1_OFFICIAL_ADOPTION_PLAN.md).
>
> **Target:** First place in Problem Statement 1 (PS1).
> The demonstration must showcase full workload, Scenario A/B/C performance, exact global nights, recurrence, low-churn emergency replanning, safe manual edits and grounded explanations without confusing operational extensions with official scoring.

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

### 3. Calendar Nights and Recurring Maintenance

- Load an explicit `Asia/Singapore` operating calendar and show the second solver mapping weekly accesses to actual `service_date` values.
- Point out that `access_night` remains a local contract/type/week index and is not the weekday.
- Add a station or sector recurrence policy with `max_interval_days` and a last completion date. Show deterministic generated jobs, shared possession consumption and cadence compliance.
- Mark the view as operational and show that generated IDs/`service_date` do not enter the official CSV bundle.

### 4. Emergency Replanning with Minimum Churn

- Set an `as_of` instant, then inject an emergency job or reduce calendar/supply availability at a critical bottleneck.
- Show completed, occurred, in-progress and locked accesses frozen before solving.
- Trigger a replan under one selected A/B/C policy. Show that the selected scenario objective is optimised first, then churn among equally scoring plans; label an enriched run's cost operational rather than official.
- Present frozen/unchanged/moved/new counts, absolute date movement and before/after scenario score. Pure group-label changes must not appear as churn.

### 5. Manual Drag, Conflict and Repair

- Drag one future access to an invalid global night. Show the server-generated rule code, conflicting activities/locations and simple reason without altering the published plan.
- Drag to a valid night and show score/churn warnings. Save with a revision token or pin it and run complete repair of the remaining movable schedule.
- Demonstrate that a stale or frozen-history edit is rejected.

### 6. Grounded Explanation and Chat

- Click a displaced activity. Show the visible auto-prompt and fact-backed answer naming the emergency/closure, binding capacity/deadline, date and score impact, and measured alternative.
- Ask a general schedule question such as “Which station is next due for recurring maintenance?” and show cited activity/run IDs.
- State that the chatbot is read-only and falls back to a deterministic summary; it does not validate or publish schedules.

### 7. Verification and Official Exports
- Display the independent validation results covering workload yield, legal possession mixes, buffer footprints, and contract workfronts.
- Separately display calendar, recurrence, freeze and churn validation for the operational run.
- Download and inspect the three generated scenario artifacts:
  - `SCHEDULE_ACCESS.csv` (row count depends on ECLO usage);
  - `SCHEDULE_OCCUPANCY.csv` (core location possession groups);
  - `RESULTS.csv` (simulated completion date and overrun days per contract).
- Confirm that the official files have exact headers and no `service_date`, generated maintenance ID or chatbot content.

---

## Part 2: Legacy Synthetic Prototype Walkthrough (Historical Scaffold)

*Note: This walkthrough demonstrates the application UI infrastructure (FastAPI, auth, transactions, audit). The single-night model is retired as PS1 authority because its recovery mode defers 5 of 12 requests, violating PS1's full-workload baseline.*

1. **Start the app:** Run `python -m uvicorn backend.app.main:app --reload`.
2. **Planning officer view:** Select Planning Officer, inspect the 12 synthetic requests, and click **Generate proposal**.
3. **Recovery review:** Review the returned status and note the 7 scheduled requests and 5 deferred requests (historical synthetic behavior).
4. **Publish transaction:** Click **Approve & publish**; show that the backend commits all bookings atomically and bumps the planning revision.
5. **Stale proposal rejection:** Change a resource's availability to demonstrate that older proposals are invalidated.
