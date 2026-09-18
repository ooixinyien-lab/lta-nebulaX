from pathlib import Path

from backend.app.db.engine import create_engine_and_session, create_schema
from backend.app.db.repositories.instances import create_instance_revision, fingerprint_files
from backend.app.db.repositories.plans import create_plan, publish_plan, replace_draft_rows
from backend.app.db.repositories.runs import create_run, finish_run
from backend.app.domain_models import AccessScheduleRow, OccupancyScheduleRow
from backend.app.io import load_problem_from_directory


def test_official_instance_revision_is_relationally_persisted():
    database = create_engine_and_session("sqlite:///:memory:")
    create_schema(database)
    problem = load_problem_from_directory(Path("data"))
    session = database._factory()
    try:
        instance, revision = create_instance_revision(
            session, problem, name="official", created_by="tester",
            input_fingerprint=fingerprint_files({"01_LINES.csv": b"test"}),
        )
        session.commit()
        assert instance.id.startswith("inst-")
        assert revision.revision_number == 1
        assert len(revision.instance.revisions) == 1
    finally:
        session.close()


def test_runs_and_plans_have_optimistic_versions():
    database = create_engine_and_session("sqlite:///:memory:")
    create_schema(database)
    session = database._factory()
    try:
        from backend.app.db.models import Instance, InstanceRevision
        instance = Instance(id="inst-test", name="test", fingerprint="a" * 64, created_by="tester")
        session.add(instance)
        session.flush()
        revision = InstanceRevision(id="rev-test", instance_id=instance.id, revision_number=1, input_fingerprint="a" * 64, parser_version="test", validation_status="VALID", created_by="tester")
        session.add(revision)
        session.flush()
        run = create_run(session, revision_id=revision.id, scenario="A", created_by="tester", time_limit=10)
        plan = create_plan(session, revision_id=revision.id, scenario="A", created_by="tester", base_run_id=run.id)
        replace_draft_rows(session, plan.id, expected_version=1, actor="tester", access=[AccessScheduleRow(activity_id="A1", access_seq=1, week=1, eclo=False, access_night=1)], occupancy=[OccupancyScheduleRow(activity_id="A1", week=1, location_id="L1", co_share_group="G1")])
        assert plan.version == 2
        publish_plan(session, plan.id, expected_version=2, actor="tester")
        finish_run(session, run.id, status="SUCCEEDED")
        session.commit()
        assert plan.status == "PUBLISHED"
        assert run.status == "SUCCEEDED"
    finally:
        session.close()
