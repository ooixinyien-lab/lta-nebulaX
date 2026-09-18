"""Generate the checked-in operational schedule-insertion CSV bundle."""

from pathlib import Path

from backend.app.schedule_insertion.fixture_generator import generate_fixture


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    generate_fixture(root / "data", root / "data" / "schedule_insertion")
