from dataclasses import dataclass
from datetime import date


@dataclass
class Job:
    name: str
    date: date
    start: int
    end: int
    stations: list[str]
    manpower: int
    equipment: list[str]

    def time_overlap(self, other):
        # Jobs on different dates cannot overlap
        if self.date != other.date:
            return False

        return self.start < other.end and other.start < self.end

    def station_conflict(self, other):
        if not self.time_overlap(other):
            return []

        return list(set(self.stations) & set(other.stations))

    def equipment_conflict(self, other):
        if not self.time_overlap(other):
            return []

        return list(set(self.equipment) & set(other.equipment))