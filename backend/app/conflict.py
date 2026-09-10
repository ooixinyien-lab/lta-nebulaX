from job import *
from datetime import date


def main():
    schedule = []

    job1 = Job(
        name="Rail Grinding",
        date=date(2026, 9, 7),
        start=60,                  # 01:00
        end=120,                   # 02:00
        stations=["EW01", "EW02"],
        manpower=4,
        equipment=["Grinder"]
    )

    job2 = Job(
        name="Signal Inspection",
        date=date(2026, 9, 7),
        start=120,                 # 02:00
        end=180,                   # 03:00
        stations=["EW03"],
        manpower=3,
        equipment=["Inspection Cart"]
    )

    job3 = Job(
        name="Track Inspection",
        date=date(2026, 9, 7),
        start=60,                  # 01:00
        end=150,                   # 02:30
        stations=["NS01", "NS02"],
        manpower=2,
        equipment=["Inspection Cart"]
    )

    job4 = Job(
        name="Cable Replacement",
        date=date(2026, 9, 7),
        start=150,                 # 02:30
        end=210,                   # 03:30
        stations=["EW04", "EW05"],
        manpower=3,
        equipment=["Cable Machine"]
    )

    job5 = Job(
        name="Platform Repair",
        date=date(2026, 9, 7),
        start=180,                 # 03:00
        end=240,                   # 04:00
        stations=["NS03"],
        manpower=2,
        equipment=["Repair Kit"]
    )


    # ==========================================
    # 3. ADD 5 JOBS TO SCHEDULE
    # ==========================================

    schedule.append(job1)
    schedule.append(job2)
    schedule.append(job3)
    schedule.append(job4)
    schedule.append(job5)


    # ==========================================
    # 4. CREATE NEW JOB
    # ==========================================

    new_job = Job(
        name="Emergency Track Work",
        date=date(2026, 9, 7),
        start=90,                  # 01:30
        end=150,                   # 02:30
        stations=["EW02", "EW03"],
        manpower=3,
        equipment=["Grinder"]
    )


    # ==========================================
    # 5. CHECK NEW JOB AGAINST SCHEDULE
    # ==========================================

    print("==========================================")
    print("EXISTING SCHEDULE")
    print("==========================================")

    for job in schedule:
        print(
            f"{job.name}: "
            f"{job.start}-{job.end}, "
            f"Stations={job.stations}"
        )


    print("\n==========================================")
    print("NEW REQUEST")
    print("==========================================")

    print(
        f"{new_job.name}: "
        f"{new_job.start}-{new_job.end}, "
        f"Stations={new_job.stations}"
    )


    print("\n==========================================")
    print("CONFLICT CHECK")
    print("==========================================")


    conflicts_found = False


    for job in schedule:

        station_conflicts = new_job.station_conflict(job)
        equipment_conflicts = new_job.equipment_conflict(job)


        if station_conflicts or equipment_conflicts:

            conflicts_found = True

            print(f"\n⚠️ Conflict with: {job.name}")

            if station_conflicts:
                print(
                    f"  Station conflict: "
                    f"{station_conflicts}"
                )

            if equipment_conflicts:
                print(
                    f"  Equipment conflict: "
                    f"{equipment_conflicts}"
                )


    if not conflicts_found:
        print("\n✅ No conflicts found.")


# ==========================================
# RUN PROGRAM
# ==========================================

if __name__ == "__main__":
    main()