class Schedule:
    def __init__(self, available_manpower, available_equipment):
        self.jobs = []
        self.available_manpower = available_manpower
        self.available_equipment = available_equipment

    def add_job(self, job):
        self.jobs.append(job)

    def get_sorted_jobs(self):
        return sorted(
            self.jobs,
            key=lambda job: (job.date, job.start)
        )

    def display(self):
        for job in self.get_sorted_jobs():
            print(
                f"{job.date} | "
                f"{job.start:04d}-{job.end:04d} | "
                f"{job.name}"
            )