# Operational schedule-insertion fixture

These generated CSVs are an operational input bundle, not part of the eight
official PS1 inputs.

- `maintenance_jobs.csv`: one stable occurrence per sector and 245-day target.
- `baseline_visits.csv`: three distinct visits per occurrence, including
  synthetic historical actuals and future committed lookahead.
- `operating_calendar.csv`: explicit `Asia/Singapore` service dates, physical
  availability, ECLO eligibility, synthetic gross date capacity and a global
  night identity.
- `project_jobs.csv` and `project_accesses.csv`: intentionally empty in the
  maintenance-only baseline; official project jobs are loaded from the
  selected immutable PS1 revision when the combined schedule is solved.
- `metadata.csv`: fixture/version, horizon and resource-policy metadata.

The files were generated from the repository's current official CSVs with
`scripts/generate_schedule_insertion_fixture.py`. The generator uses the
actual sector IDs and does not hardcode the network size. Maintenance reserves
are validated as a separate daily resource; they are not subtracted from the
official residual location supply a second time.
