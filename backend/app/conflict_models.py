import itertools
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

_job_id_counter = itertools.count(start=1)


@dataclass
class Location:
    line_code: str       # e.g., "NS", "EW"
    sector_id: str       # e.g., "S02", "S03"
    track_number: int    # e.g., 1 (Inbound), 2 (Outbound)


@dataclass
class Job:
    name: str
    duration: int
    date: date = field(default_factory=date.today)
    start: int = 0                                       # 0 = 01:00 AM, 210 = 04:30 AM
    locations: list[Location] = field(default_factory=list)
    protected_sectors: list[str] = field(default_factory=list)  # Auto-populated from locations + buffers
    
    manpower_requirement: Optional[str] = None          # e.g., "TEAM_ALPHA"
    manpower_count: int = 1                             # Quantity of teams required
    
    equipment_requirement: list[str] = field(default_factory=list)  # e.g., ["TAMPING_01", "GRINDER_01"]
    prerequisite_jobs: list[str] = field(default_factory=list)  # Predecessor job IDs
    
    power_requirement: Optional[str] = "NONE"           # "ON", "OFF", "NONE", or "BOTH" / 2
    
    # Priority replaces explicit boolean flags
    # 1: Service-Critical / Mandatory (non-deferrable)
    # 2: High Priority (deferrable if necessary)
    # 3: Flexible / Routine Maintenance (highly deferrable)
    priority: int = 1
    
    # Timing bounds & freeze status
    earliest_start: int = 0                             # Requester timing bound
    latest_finish: int = 210                            # Requester timing bound
    is_frozen: bool = False                             # Frozen inside booking horizon
    
    id: str = field(default_factory=lambda: f"JOB-{next(_job_id_counter)}")

    def __post_init__(self):
        """Automatically combines sector IDs from locations into protected_sectors."""
        loc_sectors = [loc.sector_id for loc in self.locations if loc.sector_id]
        combined = set(self.protected_sectors) | set(loc_sectors)
        self.protected_sectors = sorted(combined)

    @property
    def end(self) -> int:
        return self.start + self.duration

    @property
    def is_mandatory(self) -> bool:
        """Priority 1 represents mandatory, non-negotiable service-critical work."""
        return self.priority == 1

    @property
    def is_deferrable(self) -> bool:
        """Priority 2 and 3 represent flexible work eligible for deferral."""
        return self.priority in (2, 3)

    def validate_bounds(self, max_usable_window: int = 210) -> list[dict]:
        """Validates job parameters and returns UI-friendly field-level errors."""
        errors = []
        if self.duration <= 0:
            errors.append({
                "field": "duration",
                "code": "INVALID_DURATION",
                "message": "Job duration must be a positive integer."
            })
        if self.start < 0 or self.end > max_usable_window:
            errors.append({
                "field": "time_window",
                "code": "ENGINEERING_WINDOW_EXCEEDED",
                "message": (
                    f"Job timing window [{self.start:04d}-{self.end:04d}] exceeds "
                    f"the available engineering window (00:00 to {max_usable_window} mins)."
                )
            })
        return errors

    def check_power(self, other: "Job") -> bool:
        """Returns True if power requirements are compatible, False if conflicting."""
        if self.date != other.date:
            return True

        p1, p2 = self.power_requirement, other.power_requirement

        if p1 in ("NONE", None) or p2 in ("NONE", None):
            return True

        if p1 in ("BOTH", "2") or p2 in ("BOTH", "2"):
            return False

        if (p1 == "ON" and p2 == "OFF") or (p1 == "OFF" and p2 == "ON"):
            return False

        return True

    def check_dependency(self, other: "Job") -> bool:
        """Returns True if dependency order is respected across dates; False if violated."""
        if other.id in self.prerequisite_jobs:
            if self.date < other.date:
                return False
            if self.date == other.date:
                return self.start >= other.end
        return True


class Schedule:
    def __init__(
        self,
        equipment_available: Optional[dict[str, int]] = None,
        manpower_available: Optional[dict[str, int]] = None,
        buffer_minutes: int = 15,
        window_length_minutes: int = 210,
    ):
        self.jobs: list[Job] = []
        self.equipment_available = equipment_available if equipment_available else {}
        self.manpower_available = manpower_available if manpower_available else {}
        self.buffer = buffer_minutes
        self.window_length_minutes = window_length_minutes

    def add_job(self, job: Job):
        self.jobs.append(job)

    def edit_job(self, job_id: str, updated_fields: dict) -> tuple[bool, str]:
        """Updates a job while enforcing freeze horizon locks."""
        job = next((j for j in self.jobs if j.id == job_id), None)
        if not job:
            return False, f"Job '{job_id}' not found in schedule."

        if job.is_frozen:
            time_or_resource_changing = any(
                k in updated_fields for k in ("date", "start", "duration", "manpower_requirement", "equipment_requirement")
            )
            if time_or_resource_changing:
                return False, f"Job {job_id} is locked in the freeze horizon and cannot be modified without planner override."

        for key, val in updated_fields.items():
            setattr(job, key, val)
        
        # Re-trigger location expansion if locations or protected_sectors updated
        if "locations" in updated_fields or "protected_sectors" in updated_fields:
            job.__post_init__()

        return True, f"Job {job_id} updated successfully."

    def display(self):
        """Prints schedule sorted chronologically across dates."""
        sorted_jobs = sorted(self.jobs, key=lambda j: (j.date, j.start))
        for j in sorted_jobs:
            sectors_str = ", ".join(j.protected_sectors)
            print(f"[{j.date}] {j.start:04d}-{j.end:04d} mins | ID: {j.id} | Priority: {j.priority} | Sectors: [{sectors_str}] | Name: {j.name}")

    def time_overlap(self, job: Job) -> list[Job]:
        """Returns scheduled jobs overlapping on the SAME DATE."""
        return [
            j for j in self.jobs
            if j.date == job.date and j.id != job.id and max(j.start, job.start) < min(j.end, job.end)
        ]

    def buffer_overlap(self, job: Job) -> list[Job]:
        """Returns jobs overlapping on the SAME DATE when including travel/transit buffers."""
        buf_start = max(0, job.start - self.buffer)
        buf_end = job.end + self.buffer

        return [
            j for j in self.jobs
            if j.date == job.date
            and j.id != job.id
            and max(j.start, buf_start) < min(j.end, buf_end)
            and not (max(j.start, job.start) < min(j.end, job.end))
        ]

    def equipment_in_use_at(self, date_val: date, start: int, end: int, eq_type: str) -> int:
        """Returns count of equipment units in use during [start, end) on a specific date."""
        active = [j for j in self.jobs if j.date == date_val and max(j.start, start) < min(j.end, end)]
        return sum(j.equipment_requirement.count(eq_type) for j in active)

    def manpower_in_use_at(self, date_val: date, start: int, end: int, team_type: str) -> int:
        """Returns count of manpower teams engaged during [start, end) on a specific date."""
        active = [j for j in self.jobs if j.date == date_val and max(j.start, start) < min(j.end, end)]
        return sum(j.manpower_count for j in active if j.manpower_requirement == team_type)