# Schedule insertion and low-churn replanning

NebulaX's operational schedule-insertion workflow lives under
`backend/app/schedule_insertion/`. It is additive to the official PS1 solver:
the existing weekly solver, validation, scoring and exact three-CSV export
paths are not imported as execution engines and are not changed by this
workflow.

## Architecture

The workflow has one CP-SAT engine and three configuration policies:

| Policy | Hard rules | Primary cost |
|---|---|---|
| A | Nominal weekly supply; no ECLO | Project lateness `P` |
| B | Project deadlines; flexible nominal supply and ECLO | `7V + 5E` |
| C | At most one excess slot per location-week; a two-week ECLO span per affected line | `P + 7V + 5E` |

The engine models project weekly placement, contract-local access nights,
date choice from an explicit `Asia/Singapore` calendar, possession groups and
maintenance closures in the same model. Maintenance remains a separate
resource: generated visits count once against the synthetic daily maintenance
capacity and are not subtracted from `04_LOCATION_SUPPLY.csv` again.

For a clean public instance with no operational project accesses yet, the
workflow may use a bounded incumbent from the canonical weekly PS1 solve as a
starting seed, then calendarize and independently validate it. This bridge is
not used after a run has been promoted to an operational baseline or when
insertions exist; those cases use the schedule-insertion model and retain
persistent access identities.

The operational fixture is generated from the official topology, then saved
under `data/schedule_insertion/`. Solving reads those saved CSVs; it does not
regenerate a baseline during a solve. A maintenance occurrence has three
distinct visits, a 245-day repeating target, and a 364-day rolling coverage
requirement. Historical and lookahead visits are included so both horizon
boundaries are checkable.

## Replanning and disruption

`BaselineBundle` is immutable by revision. A replan supplies a baseline
revision, `as_of`, typed additions/changes, a scenario and one overall runtime
budget. Completed, occurred, in-progress and locked accesses are fixed. Their
doubled workload is credited exactly once; only the remaining mandatory
workload is variable.

The first candidate minimizes the selected scenario cost. A second candidate
is searched under a configurable operational allowance (10 points by default;
zero gives strict scenario-cost preservation) and minimizes, in order:

1. changed existing jobs;
2. changed existing visits;
3. absolute service-date displacement;
4. ECLO and sharing changes; and
5. scenario cost.

The 10-point allowance is a demo default, not an official scoring rule. A
candidate is labelled best-known unless CP-SAT proves optimality. Group-label
renaming and access-sequence renumbering are ignored by disruption accounting.

## API examples

The operational API is under `/api/ps1/schedule-insertion/`:

```json
POST /baselines
{
  "official_revision_id": "rev-...",
  "baseline": {"baseline_id": "baseline-fixture-v1", "revision": 1, "horizon_start": "2027-01-04", "horizon_weeks": 52, "maintenance_jobs": [], "maintenance_visits": [], "calendar": []}
}
```

Additions create a new immutable baseline revision:

```json
POST /baselines/baseline-fixture-v1/additions
{"baseline_revision": 1, "additions": [{"requested_source": "emergency", "job": {"job_id": "EM-001", "contract_number": "EM-001", "activity_type": "Renewal", "nature_of_activity": "Non-live (Others)", "access_type": "C", "start_location_id": "SEC:ALP:S01_S02:EB", "end_location_id": "SEC:ALP:S01_S02:EB", "total_accesses": 1, "planned_start_date": "2027-05-03", "planned_completion_date": "2027-05-10", "hard_completion_date": "2027-05-10"}}]}
```

Run a selected policy with an explicit freeze boundary:

```json
POST /runs
{"official_revision_id": "rev-...", "request": {"baseline_id": "baseline-fixture-v1", "baseline_revision": 2, "scenario": "C", "as_of": "2027-05-01T12:00:00+08:00", "options": {"time_limit_seconds": 60, "scenario_cost_allowance": 10}}}
```

After a successful run, promote its validated candidate to the next immutable
baseline before inserting the next emergency:

```json
POST /baselines/baseline-fixture-v1/from-run/sir-...
{"expected_baseline_revision": 2}
```

Operational runs return exact project service dates, maintenance visits,
scenario cost, disruption, validation findings, runtime, bound/proof status
and a structured result diff. They do not enter the official PS1 export path.

## Deliberate differences from the official solver

- The official solver remains the authoritative competition implementation and
  retains its 30-week horizon and exact three-CSV schemas.
- Operational models add maintenance occurrence/visit identities, service
  dates, global-night IDs, baseline revisions, freeze facts and disruption
  metrics; those fields never contaminate official exports.
- Maintenance closures use the explicit synthetic both-bound sector plus
  endpoint-platform policy declared by the operational fixture. This is not a
  claim of official-checker parity.
- Operational scenario costs are PS1-derived and are labelled operational.
  The replan allowance and churn tie-breakers are workflow configuration, not
  additional official score terms.
- The API reports local validation and `official_checker_status=unavailable`
  honestly because the organiser's executable checker is not in this repo.

## Reproducible demonstration

1. Generate/read the saved maintenance baseline.
2. Import it as a baseline revision and add the existing official projects.
3. Solve A, B or C and store the validated combined schedule.
4. Add an emergency with a real release date and hard deadline.
5. Replan from the resulting baseline and inspect reference/lower-disruption
   candidates and the measured diff.
