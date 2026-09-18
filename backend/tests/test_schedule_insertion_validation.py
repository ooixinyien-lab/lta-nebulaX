"""Independent validation cases for maintenance/project separation."""

from datetime import timedelta
from pathlib import Path

from backend.app.domain_models import AccessType, ProblemInstance
from backend.app.io import load_problem_from_directory
from backend.app.schedule_insertion.geometry import maintenance_closure_locations, project_core_locations
from backend.app.schedule_insertion.io import load_baseline_bundle
from backend.app.schedule_insertion.models import ProjectAccess, ProjectJob, ScheduleScenario
from backend.app.schedule_insertion.validation import validate_operational_schedule


ROOT = Path(__file__).resolve().parents[2]


def _problem() -> tuple[ProblemInstance, object]:
    from backend.app.schedule_insertion.solver import _official_jobs

    problem = load_problem_from_directory(ROOT / "data")
    bundle = load_baseline_bundle(ROOT / "data" / "schedule_insertion")
    job = _official_jobs(problem)[0]
    return problem, bundle.model_copy(update={"project_jobs": [job]})


def test_maintenance_closure_blocks_project_sharing() -> None:
    problem, bundle = _problem()
    job = bundle.project_jobs[0]
    core = project_core_locations(job, problem)
    closure_visit = next(
        visit for visit in bundle.maintenance_visits
        if visit.service_date >= bundle.horizon_start
        and set(maintenance_closure_locations(problem, visit.sector_id)) & set(core)
    )
    group_by_location = {location_id: "G1" for location_id in core}
    access = ProjectAccess(
        access_id="A001:ACCESS:001",
        job_id=job.job_id,
        access_seq=1,
        week=((closure_visit.service_date - bundle.horizon_start).days // 7) + 1,
        service_date=closure_visit.service_date,
        group_by_location=group_by_location,
    )
    validation = validate_operational_schedule(problem, bundle, bundle.project_jobs, [access], ScheduleScenario.A)

    assert not validation.passed
    assert any(f.rule == "maintenance_project_conflict" for f in validation.findings)


def test_label_renaming_is_not_a_material_disruption() -> None:
    from backend.app.schedule_insertion.scoring import compute_disruption

    problem, bundle = _problem()
    job = bundle.project_jobs[0]
    service_date = bundle.horizon_start + timedelta(days=7)
    core = project_core_locations(job, problem)
    before = ProjectAccess(
        access_id="A001:ACCESS:001", job_id=job.job_id, access_seq=1, week=2,
        service_date=service_date, group_by_location={location_id: "G1" for location_id in core},
    )
    after = before.model_copy(update={"group_by_location": {location_id: "RENAMED" for location_id in core}, "access_seq": 8})
    baseline = bundle.model_copy(update={"project_jobs": [job], "project_accesses": [before]})
    metrics = compute_disruption(baseline, [after])

    assert metrics.changed_existing_jobs == 0
    assert metrics.changed_existing_visits == 0
    assert metrics.label_only_changes == 0
