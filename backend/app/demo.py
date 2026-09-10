# demo.py
from datetime import date, timedelta
from models import Job, Location, Schedule
from checker import conflict_checker


def main():
    print("==================================================")
    print("      NEBULA X MULTI-DAY SCHEDULER DEMO           ")
    print("==================================================\n")

    today = date.today()
    tomorrow = today + timedelta(days=1)

    schedule = Schedule(
        equipment_available={"TAMPING_01": 2, "GRINDER_01": 1, "CART_01": 2},
        manpower_available={"TEAM_ALPHA": 1, "TEAM_BETA": 2, "TEAM_GAMMA": 1},
        buffer_minutes=15,
        window_length_minutes=210,
    )

    # JOB 1: Priority 1 (Mandatory), Location S01
    job1 = Job(
        name="Rail Grinding Section A",
        date=today,
        start=0,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S01", track_number=1)],
        manpower_requirement="TEAM_ALPHA",
        manpower_count=1,
        equipment_requirement=["GRINDER_01"],
        power_requirement="OFF",
        priority=1,  # Mandatory
    )

    # JOB 2: Priority 2 (Deferrable), Location S03
    job2 = Job(
        name="Signal Equipment Inspection",
        date=today,
        start=0,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S03", track_number=1)],
        manpower_requirement="TEAM_BETA",
        manpower_count=1,
        equipment_requirement=["CART_01"],
        power_requirement="NONE",
        priority=2,  # Deferrable
    )

    # JOB 3: Priority 3 (Routine), Location S04
    job3 = Job(
        name="Track Tamping Maintenance",
        date=today,
        start=75,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S04", track_number=1)],
        manpower_requirement="TEAM_BETA",
        manpower_count=1,
        equipment_requirement=["TAMPING_01"],
        power_requirement="NONE",
        priority=3,  # Routine
    )

    # JOB 4: Night 2, Location S02
    job4 = Job(
        name="Rail Grinding Section B (Night 2)",
        date=tomorrow,
        start=0,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S02", track_number=1)],
        manpower_requirement="TEAM_ALPHA",
        manpower_count=1,
        equipment_requirement=["GRINDER_01"],
        power_requirement="OFF",
        priority=1,
    )

    # JOB 5: Night 2, Depends on Job 4
    job5 = Job(
        name="Post-Grinding Track Verification",
        date=tomorrow,
        start=75,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S02", track_number=1)],
        manpower_requirement="TEAM_GAMMA",
        manpower_count=1,
        equipment_requirement=["CART_01"],
        power_requirement="OFF",
        priority=2,
        prerequisite_jobs=[job4.id],
    )

    # JOB 6: Multi-Violation Job (Location S03, Manpower overcapacity, Premature dependency)
    job6 = Job(
        name="Emergency Multi-Conflict Repair",
        date=today,
        start=30,
        duration=60,
        locations=[Location(line_code="EW", sector_id="S03", track_number=1)],
        manpower_requirement="TEAM_BETA",
        manpower_count=2,
        equipment_requirement=["CART_01"],
        power_requirement="NONE",
        priority=1,
        prerequisite_jobs=[job5.id],
    )

    jobs_to_schedule = [job1, job2, job3, job4, job5, job6]

    for idx, job in enumerate(jobs_to_schedule, start=1):
        print(f"[EVALUATING] Job {idx} ({job.id}): '{job.name}' on {job.date} ({job.start:04d}-{job.end:04d} mins)...")
        print(f"   -> Priority: {job.priority} (Mandatory: {job.is_mandatory}, Deferrable: {job.is_deferrable})")
        print(f"   -> Auto-Combined Sectors: {job.protected_sectors}")
        if job.prerequisite_jobs:
            print(f"   -> Required Prerequisites: {job.prerequisite_jobs}")

        issues = conflict_checker(schedule, job)

        if not issues:
            schedule.add_job(job)
            print(f"[SUCCESS] Added {job.id}: '{job.name}' to schedule.")
            print("CURRENT UPDATED SCHEDULE:")
            schedule.display()
            print("-" * 50 + "\n")
        else:
            print(f"\n[REJECTED] Conflict detected for {job.id}. Stopping scheduling pipeline.\n")
            print(f"Total Conflicts Found: {len(issues)}\n")
            for issue_idx, issue in enumerate(issues, start=1):
                print(f"   Issue {issue_idx}:")
                print(f"   - Code:        {issue['code']}")
                print(f"   - Severity:    {issue['severity']}")
                print(f"   - Request IDs: {issue['request_ids']}")
                print(f"   - Resource:    {issue['resource']}")
                print(f"   - Message:     {issue['message']}\n")
            break


if __name__ == "__main__":
    main()