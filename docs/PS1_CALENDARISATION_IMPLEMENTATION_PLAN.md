Implement actual Monday–Sunday night scheduling for ForRail using this plan.

This is a scoped implementation prompt, based on the repository inspected on 19 September 2026. Read `AGENTS.md`, the root `PS1_OFFICIAL_ADOPTION_PLAN.md` (especially “Map weekly accesses to actual global nights”), `docs/TEAM_WORK.md`, and the relevant code before editing. Follow the user's scope clarifications: the original solver's three CSV outputs and every weekly scheduling decision are fixed, and the calendar interface must stay simple because a detailed scheduling UI will be built later. This milestone adds a separate date mapping and a minimal read-only weekly preview. Automatic weekly repair described in the broader adoption plan is outside this milestone. Follow the authoritative domain rules and implement the phases in order, with working integration and focused verification at each phase. Do not stop after producing another plan.

1. **Outcome and scope**

   Consume the existing weekly A/B/C solver's completed output as read-only input. Add a second OR-Tools CP-SAT solver that assigns each scheduled access to a real engineering night within its assigned week. Render the validated result in a simple, read-only React week view with Monday–Sunday columns and actual dates. Prioritise correct mapping and reusable backend results; the detailed scheduling workspace is a future feature. Preserve all original rows, including weeks, local indices, ECLO flags, possession memberships, access sequences and reported results; preserve the original file bytes. Only the separate date mapping is new.

   The flow is:

   ```text
   Existing solver's fixed three-CSV output
     + matching original instance (contracts, topology and planning horizon)
     + explicit, versioned operating calendar
     -> date assignment solver
     -> independent weekly + date validation
     -> stored operational result -> seven-day React view

   Proven date infeasibility -> report conflicts; retain fixed source unchanged
   Failure/timeout without a valid complete result -> preserve previous result
   ```

   Include read-only source-bundle import, calendar inputs, the date solver, validation, persistence/API integration, execution of date-assignment jobs, and the date view. Weekly re-solving, regrouping, recurrence generation, emergency replanning, drag-and-drop editing, chatbot, named crew assignment and minute-level scheduling are outside this milestone. The three CSVs do not contain all contract/topology/availability data, so bind them to the matching original instance and calendar rather than guessing missing restrictions.

2. **Meanings that must remain separate**

   - `week`: official planning week, derived from `PlanningParameters`.
   - `access_night`: an existing contract/activity-type/week-local allocation index. Preserve it. Never implement `1 = Monday`, `2 = Tuesday`, or use it as a global index.
   - `co_share_group`: scoped to `(location_id, week, co_share_group)`. The same text at two different locations does not identify one possession.
   - `service_date`: new operational date on which the engineering night begins, in `Asia/Singapore`.
   - `global_night_id`: stable within the immutable calendar revision, e.g. `<calendar_revision_id>:2027-01-06`.

   For example, an access with `week=1, access_night=2` could receive `service_date=2027-01-06` and display “Wednesday night, 6 Jan 2027”. Another contract's local night 2 could receive Friday. An activity's many weekly accesses receive separate dates; do not give the whole activity one date.

   A Sunday engineering night belongs to Sunday's service date even if work would continue after midnight. Do not invent start/end clock times. Read the horizon from the instance: the public fixture runs from Monday 2027-01-04 through Sunday 2027-08-01, but do not hardcode those dates.

   Official Sunday-based completion dates, scenario scoring, and all three official CSV schemas remain unchanged. Actual dispatch dates are additional operational information.

3. **Repository seams and gaps to account for**

   Reuse `domain_models.py::PS1Base`, `ProblemInstance`, the official row types, `PlanningParameters`, `topology.py::FootprintCache`, `ps1/validation.py::validate_schedule`, and existing scoring helpers. Import the three CSVs with `ps1/artifacts.py::read_access_schedule`, `read_occupancy_schedule`, and `read_results`, which enforce their headers. Compare imported contract results with existing scoring helpers without rewriting them. Do not call `solve_ps1` or modify its model as part of calendarisation.

   The active HTTP lifecycle is `backend/app/api/ps1_routes.py`; `backend/app/ps1/ps1_routes.py` is a separate compatibility path. The existing CLI can already produce the three output files without persisting runs. Support importing those files directly, as well as using an existing complete stored source. `POST /api/ps1/solve` currently queues a record without an active application worker; fixing that upstream lifecycle is not required for this output-based milestone. Wire up the date-assignment execution path in section 7.

   `db/repositories/runs.py` already provides `claim_next_run`, `store_results`, `update_progress`, and `finish_run`. `instances.py::load_revision` reconstructs the typed official instance. Use `app.state.db` and short transactions through the existing `Database` class.

   `db/schema.py` currently supports schema version 1. Add an additive migration for existing databases; editing the fresh schema alone is insufficient. `plans.py::publish_plan` does not validate schedules, so it is not a sufficient publication gate.

   The React `ScheduleDashboard.jsx` currently consumes sample/mock data. Build a small read-only calendar preview page using real results, with a small navigation addition. Do not migrate the teammate-owned dashboard, depend on its sample cards, or implement new features in `frontend/`.

4. **Phase 1 — typed, versioned calendar inputs**

   Add `backend/app/ps1/calendar_models.py`. New input/output schemas inherit `PS1Base` with explicit types and validators. Use dates rather than unvalidated date strings internally. Keep these fields out of official input/output models.

   Define at least these concepts:

   | Model | Essential contents |
   | --- | --- |
   | Calendar revision | ID, official instance revision ID, timezone fixed to `Asia/Singapore`, schema/policy versions, provenance, fingerprint, assumption flag and assumption descriptions |
   | Night availability | Service date; line/location maintenance availability; integer possession capacity per location/date; ECLO eligibility on affected lines |
   | Contract availability | Contract/type eligible dates, optional local-slot-specific eligibility, actual weekly date limit, actual nightly workfront limit |
   | Date commitment | Persistent access ID, fixed service date, reason/state such as pinned, completed, occurred or locked |
   | Operational access | Persistent access ID, source access reference, original weekly fields, service date, global night ID, source/policy provenance |
   | Calendar result | Source bundle/run/instance/calendar IDs, selected scenario, status, complete assignment flag, assignments, conflicts, validation and solve timings |
   | Conflict | Stable rule code, severity, access/activity IDs, dates, locations, required/available capacity where relevant, readable explanation |

   Distinguish a maintenance blackout from a railway closure that permits maintenance. Use unambiguous fields such as `maintenance_available`; do not guess from a bare `closed` flag. Reject unknown IDs, duplicate date/location records, negative capacities, wrong revisions, invalid timezone, and conflicting commitments. Require complete effective availability after resolving explicitly declared defaults; missing data must not silently become unlimited capacity.

   Provide a demo-calendar factory because official CSVs do not contain real weekday availability. Materialise and persist its defaults:

   - All seven service dates in each planning week are eligible.
   - One possession group per location per night is the default nightly capacity. This is a demo assumption, not a value derived from weekly supply.
   - No maintenance blackouts or additional contract date restrictions.
   - Calendar ECLO availability is enabled on all dates; the selected A/B/C policy still restricts its use.
   - Actual distinct work nights per contract/type/week are at most `number_of_maximum_access_per_week`; actual simultaneous activities per contract/type/date are at most `number_of_workfronts`. Record this operational interpretation explicitly.
   - Apply the conservative protection policy described in phase 2.
   - Set `assumed_calendar=true` and record every default. A user-supplied calendar may override them through explicit, versioned input.

   Weekly possession supply and nightly capacity are separate constraints. Do not copy weekly supply into each of seven nights or divide it by seven. Keep the weekly A/B/C supply policy enforced by the weekly validator.

   Add an example calendar JSON and document its units and missing-data behavior. No full calendar editor is required: JSON import plus “Create demo calendar” is enough for this milestone.

5. **Phase 2 — solve dates for a fixed weekly schedule**

   Add `backend/app/ps1/calendarisation.py` with a pure entry point similar to:

   ```python
   calendarise(problem, weekly_result, calendar, commitments, options)
       -> CalendarisationResult
   ```

   Validate the source bundle against its matching original instance before solving; do not trust a file's existence or a stored completion status. Give each source access a persistent internal ID in a separate mapping keyed by `(source_bundle_id, activity_id, access_seq)` when imported. Repeated calendarisation of the same source must reuse its IDs. Preserve a one-to-one relationship with source access rows: never add, remove, renumber or alter source occurrences. Keep stored original bytes and hashes as well as typed parsed rows; do not rewrite the CSVs as part of importing or dating them. Round-trip row equality alone does not prove byte identity; never export back over the source paths.

   For access `a`, create Boolean `y[a,d]` only for eligible dates in its official week. Enforce `sum_d y[a,d] = 1`. Candidate dates must satisfy calendar availability, applicable exact release dates, contract restrictions, ECLO restrictions, and fixed commitments. An empty domain is an explicit conflict. Honour the existing strict-week predecessor policy and also verify predecessor completion precedes successor start in service dates; do not relax weekly precedence.

   Implement these constraints:

   - An access has one date, so its complete footprint is on that date.
   - All members of each scoped location/week/group have equal dates. Equality is transitive: if A shares with B at one location and B shares with C at another, all three align. Grouping accesses into connected components is an optional simplification; intersect candidate domains across each component.
   - Count each occupied scoped possession group once against that location/date's capacity. Do not count every co-sharing activity as a separate possession. If a connected component contains two different groups at a location, those remain two capacity units.
   - For each contract/type/date, count actual accesses against the workfront limit, even when their local indices differ. Sharing a possession does not merge their workfront demand.
   - Introduce a date-used Boolean per contract/type/date and cap distinct used dates per week by the calendar's explicit actual-night limit. Do not force equal local indices to share a date unless an explicit slot mapping says so.
   - ECLO accesses must be eligible on every affected line, including Live cross-line protection; reuse `affected_line_codes`. Retain Scenario A's prohibition and Scenario C's selected weekly windows. Never change ECLO flags just to fit the fixed-date solve.
   - Check maintenance availability across core and required protection locations, using composite station identities and existing topology helpers.
   - Respect every supplied pinned/frozen/completed date commitment. All source weekly fields are immutable regardless of commitment state. Reject a commitment that cannot fit the source rather than quietly moving it.

   Protection compatibility needs an explicit operational policy. The current official validator reports it `UNVERIFIED`; do not replace that with an unsupported safety claim. For an explicitly selected demo calendar, implement versioned `conservative_demo_v1`. Let `C_a` be an access's core locations, `R_a` the union of its buffer, mirrored and cross-line locations, and `F_a = C_a union R_a`. Accesses `a,b` can use the same date only when `R_a intersect F_b` and `R_b intersect F_a` are both empty, and they share the exact scoped possession group at every location in `C_a intersect C_b`. Thus disjoint footprints are compatible and legal core co-sharing is possible, but an overlap involving protection locations is conservatively incompatible. This may reject combinations a future verified policy permits, including co-sharers with overlapping buffers. Report those as operational demo-policy conflicts, not official PS1 violations. Compute the sets from `FootprintCache`; a connected component is never a blanket protection exemption. Persist this assumption and keep official safety/checker provenance unchanged. Put the policy in an inspectable helper with dedicated cases so a verified policy can replace it later.

   First find complete feasibility within a bounded budget. A simple secondary preference for earlier eligible dates is sufficient initially; expose its value separately. No balancing or convenience preference can alter fixed weekly decisions or official scores. Sort inputs and use a fixed seed/single worker in deterministic tests; do not promise unique solutions just because a seed is set.

   Treat CP-SAT `FEASIBLE` and `OPTIMAL` as candidate incumbents needing independent validation. `UNKNOWN` without an incumbent means the search did not establish feasibility, not that the calendar is infeasible. Preserve a previously validated incumbent if an improvement stage times out. Return useful precheck conflicts and solver status; never invent a minimal infeasible core.

6. **Phase 3 — independent validation and clear failure reporting**

   Add `calendar_validation.py`. Recalculate date coverage, week membership, full workload preservation, commitments, scoped sharing, nightly group counts, actual workfront/date limits, restrictions, ECLO, precedence and protection compatibility from returned rows and immutable inputs. Do not trust solver variables or only check that dates are non-null. Reusing topology and the declared policy is fine; recalculate assignments/counts independently. Call the weekly validator too. Report weekly accounting, date validation, operational protection policy and official checker status separately.

   A source weekly schedule can be valid yet impossible to calendarise: for example, two activities belonging to a one-workfront contract may share a possession despite having different local night indices. They must align in the date layer and then exceed the real nightly workfront limit. Return that evidence; do not split the possession silently.

   Keep a bounded wall-clock deadline for date feasibility and optional date-preference improvement. On proven infeasibility, return structured evidence identifying affected accesses, groups, dates and capacity/restriction conflicts. On timeout without a valid assignment, report unknown/timeout rather than infeasible. A failure is about this fixed source under the selected calendar; do not claim every possible weekly schedule is infeasible.

   Do not rerun the weekly solver, add repair hooks, move accesses across weeks, change ECLO, or repack/rename possession groups. There is no `allow_weekly_repair` option in this milestone. A different calendar may be explicitly supplied as a new revision and tried against the same unchanged source. Any request to change weekly scheduling belongs to a separately authorised future feature.

   Every successful result must map all original accesses. If that is impossible, return no new complete calendar and retain the previous validated result. Never fabricate fallback dates, omit difficult accesses, or relax restrictions to force success. The selected scenario score is fixed because the source rows are fixed.

7. **Phase 4 — persistence, execution and API**

   Add an additive, repeatable schema upgrade for immutable calendar/enrichment revisions, calendarisation attempts, operational access identities/assignments, validation/provenance and audit metadata. Use `db/repositories/calendars.py` or similarly scoped modules. Preserve existing instance revisions, weekly runs, plans and original CSV bytes. Calendar revisions reference the exact official instance revision.

   Calendarisation creates a separate operational mapping linked to a fixed source bundle/run. Store source ID/fingerprint, instance revision, calendar revision, scenario, `run_mode=operational`, policy/solver/validator versions, assumptions and `official_export_eligible=false`. Keep the exact original three-file bytes and parsed weekly snapshot immutable. Persist each attempt's commitments/options and input fingerprints. Bind assignments and validation to that exact source. Store dates separately; do not add operational columns to `AccessScheduleRow` or the three-file bundle. Actual completion summaries, if exposed, need separate operational field names. Any optional dated CSV must be a separately named operational download, outside the three-file submission.

   Implement a small worker/service for calendar jobs, following existing repository transaction patterns. Claim work in a short write transaction, load immutable inputs, release the transaction, solve dates/validate, and atomically store complete assignments plus terminal status. Persist validation reports and solver versions. Separate job lifecycle (`QUEUED`/`RUNNING`/terminal) from actual CP-SAT status (`FEASIBLE`, `UNKNOWN`, etc.). Use claim ownership and conditional terminal writes, or explicitly enforce a single worker. Give the worker a documented executable command and a `--once` path for integration tests. Do not run CP-SAT inside a long database transaction or leave accepted jobs without an execution path. Recover interrupted owned jobs to an explicit failed/retryable state without treating incomplete rows as results or resetting another active worker's job. The calendar worker must never execute the weekly solver.

   Follow the documented planned route name `POST /api/ps1/runs/{source_run_id}/calendarize`. Add typed, authenticated routes in the active PS1 router or a registered sibling router:

   | Route | Behavior |
   | --- | --- |
   | `POST /api/ps1/schedule-bundles` | Import exactly the three original output CSVs against a matching instance revision; validate and preserve their bytes/rows; return a source ID usable for calendarisation |
   | `POST /api/ps1/enrichments` | Initially accept the typed calendar-only enrichment; return immutable enrichment/calendar revision IDs |
   | `GET /api/ps1/enrichments/{revision_id}` | Return the stored calendar and provenance |
   | `POST /api/ps1/runs/{source_run_id}/calendarize` | Accept calendar revision, expected instance revision, commitments and bounded date-solver options; return 202 and attempt ID |
   | `GET /api/ps1/calendarisations/{attempt_id}` | Return progress/status, complete validated assignments if available, assumptions, conflicts, unchanged source score and validation provenance |

   Exact route additions may follow existing conventions; make imported bundles addressable through the calendarisation route without solving them again. Distinguish imported-source provenance from an actually executed solver run. Update `docs/API_CONTRACT.md` to match the implementation. Do not implement all other planned enrichment features just because they appear in the same document.

   Use existing authentication and revision checks. Distinguish 404 missing inputs, 409 revision conflicts, and 422 malformed/incomplete inputs. A completed solver attempt with no solution is represented by its typed result status, not a fabricated success. Validate the source rows independently even if their database status says completed. Expose stable access IDs and source-row mappings before accepting ID-based commitments. Return the planning horizon and backend-joined contract/line/location display metadata so the React page can render actual result rows.

   This milestone can expose immutable validated results without adding a manual publication system. If an active-plan pointer is changed, atomically check expected revisions and the matching complete validation before swapping it. Never rely only on the current `publish_plan` primitive. Failed attempts leave the previous pointer intact. If no official HTTP export exists yet, adding it is not required; preserve and test the existing exporter boundary.

8. **Phase 5 — a minimal, read-only weekly calendar**

   Suggested files: `pages/CalendarPage.jsx`, `components/calendar/WeekCalendar.jsx`, `services/calendarApi.js`, an optional `hooks/useCalendarRun.js` if it simplifies polling, and `styles/calendar.css`, all under `nebula-ui/src/`. Add a narrow entry in `App.jsx`. Use ordinary React and a CSS grid or table; do not introduce a calendar library or a general scheduling UI framework for this preview.

   Put source-bundle import/existing source ID, matching instance, calendar JSON import/demo creation and “Assign actual nights” in one compact setup area that can collapse after a result loads. Reuse available import controls. A plain source/revision field is sufficient; do not build a run browser, upload wizard or calendar-availability editor. If original-instance upload is needed, reuse the active eight-file upload API and handle duplicate-upload 409 using its returned IDs. Calendarisation never queues a weekly solve or silently selects sample data.

   New requests must carry the configured authentication. React currently lacks shared auth state and the old `/api/config` and `/api/me` belong to the unavailable legacy router. Add only the narrow active PS1 public-auth-configuration/identity integration needed to use this page: local demo-profile selection sends `X-Demo-User` only in demo mode, while configured bearer sessions use the existing verified-token dependency. Reuse the existing server-owned roles and production restrictions; never bypass authentication or expose secrets. A broader login/account UI is outside this milestone.

   The main view needs only previous/next-week buttons, a week number/date-range label, and seven Monday–Sunday columns with actual dates. List each access as a compact entry showing activity ID/short name, contract and an ECLO badge when applicable. Use “No activities” for empty days. Keep line/location and original local access index available in a small optional inline detail or native disclosure; no detailed inspector panel is required. Clearly distinguish “Local access index: 2” from the assigned weekday. Render backend assignments and conflict messages; do not calculate capacity, protection or candidate dates in JavaScript.

   Use a compact source/scenario caption and one status/assumptions area. Show “Assumed demo calendar” when applicable; detailed revision/provenance data can live in an optional disclosure. Loading, missing input, infeasibility and timeout need only a plain status message and a short list of backend conflicts. Retain the last complete displayed schedule while explaining a failed subsequent attempt; identify the source/calendar of the visible result. No mock-success fallback or conflict-resolution dashboard.

   Format ISO date-only values without UTC-midnight/browser-timezone shifts. Show every access in the selected week exactly once, including multiple accesses for an activity across different weeks. Stack the days into a simple list on narrow screens. Use accessible button labels and existing visual styles; all new component styling belongs in `src/styles/`.

   Leave drag-and-drop, editing, resizing, pin/lock controls, month/day/Gantt views, resource lanes, network-map synchronisation, advanced filtering/search, analytics and publication workflows for the future detailed scheduling UI. Do not redesign the existing dashboard or add a new navigation system. Keep `WeekCalendar` a small display component receiving week dates and validated assignments; keep loading/API calls outside it so the later UI can reuse the backend results without depending on this preview's layout. Build no speculative extension/plugin system.

9. **Meaningful acceptance checks**

   Add focused calendar solver/validator/API tests and React tests. Cover these behaviors with small synthetic fixtures, rather than depending only on the large public instance:

   - Correct Monday/Sunday boundaries, final horizon date and non-UTC browser date rendering.
   - Same local access index across contracts can map to different weekdays; no implicit Monday mapping.
   - Exactly one date per original access. No added, removed, renumbered, duplicated or out-of-week accesses; all source weekly fields and full workload preserved.
   - Exact scoped sharing equality, unrelated equal group labels, transitive sharing chains and disjoint-domain failure.
   - Shared groups count once, distinct groups count separately, nightly capacity and actual contract workfront/date limits are enforced.
   - Blackouts and contract availability remove dates; missing coverage is not unlimited availability.
   - Live buffers, opposite-bound/cross-line effects, conservative protection conflicts and allowed core co-sharing; official safety provenance stays honest.
   - A forbids ECLO, B retains completion rules, C retains line windows; cross-line ECLO must satisfy both calendars.
   - Pins/frozen dates are preserved; all original identity and ECLO/yield facts remain unchanged; inconsistent commitments return conflicts.
   - A tiny weekly-valid but undateable fixture returns a conflict and no new calendar. Assert the weekly solver is never called and no source packing/week/ECLO field changes, including on failure.
   - Deterministically exercised timeout/unknown and improvement-timeout paths retain an incumbent correctly. Do not depend on tiny timing values to make tests pass.
   - Validator rejects deliberately corrupted date rows independently of the solver.
   - Fresh, v1-to-new and repeated migrations preserve official rows. An end-to-end test imports a pre-generated three-CSV bundle through HTTP, queues calendarisation, executes the calendar worker `--once`, and reads independently validated dates. Test worker crash/rollback, stale revisions/auth failures and retention of previous valid results.
   - Before/after official CSV bytes, every source row/field, headers and score remain identical after both successful and failed calendarisation.
   - The simple React preview displays returned dates, week navigation, empty days, assumptions, loading/failure messages and the previous valid run correctly. Check responsive readability and keyboard navigation; no scheduling-edit interaction is part of this milestone.

   Run relevant existing targeted suites, including `test_data_layer.py`, `test_ps1_solver.py`, `test_ps1_scoring_validation.py`, `test_ps1_database.py`, and `test_ps1_startup_upload.py`, plus the new suites. Use `.venv/bin/python -m pytest` and run `npm test`, `npm run lint`, and `npm run build` in `nebula-ui` after UI changes. Avoid bare full-repository pytest because obsolete legacy imports are known to fail collection. Report pre-existing failures separately; do not silently suppress them.

   Finish by documenting how to import existing solver outputs with their matching instance, start the calendar worker, create/import a calendar, assign nights, and open the calendar view. Report changed files, executed checks, defaults and remaining limitations. Do not claim that a demo calendar represents supplied LTA operating availability or that the absent official checker has certified it.

Reference for solver statuses: [OR-Tools CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver). In particular, `UNKNOWN` is not a proof of infeasibility.
