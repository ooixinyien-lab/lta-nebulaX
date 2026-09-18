"""Focused tests for immutable-source calendar mapping."""

from __future__ import annotations

from datetime import date, datetime, timezone

from backend.app.domain_models import (
    AccessScheduleRow,
    AccessType,
    Activity,
    ActivityPriority,
    ActivityType,
    Bound,
    BufferRule,
    Contract,
    ContractPriority,
    Line,
    LocationKind,
    LocationSupply,
    NatureOfWorks,
    OccupancyScheduleRow,
    PlanningParameters,
    ProblemInstance,
    ScenarioResultRow,
    Sector,
    Station,
)
from backend.app.ps1.calendar_models import (
    CalendariseOptions,
    ContractCalendarRule,
    DateCommitment,
    FixedScheduleBundle,
    LineNightRule,
    OperatingCalendarInput,
    demo_calendar,
)
from backend.app.ps1.calendar_validation import validate_calendarisation
from backend.app.ps1.calendarisation import calendarise


def problem(*, workfronts: int = 2) -> ProblemInstance:
    locations = [
        LocationSupply(
            location_id=location_id,
            location_kind=kind,
            line_code="TST",
            bound=Bound.EB,
            supply_capacity=1,
        )
        for location_id, kind in (
            ("SEC:TST:S01_S02:EB", LocationKind.TUNNEL_SECTOR),
            ("PLAT:TST:S01:EB", LocationKind.PLATFORM_SECTOR),
            ("PLAT:TST:S02:EB", LocationKind.PLATFORM_SECTOR),
        )
    ]
    return ProblemInstance(
        lines=[Line(line_code="TST", line_name="Test")],
        stations=[
            Station(station_id="S01", line_code="TST", seq=1, is_interchange=False),
            Station(station_id="S02", line_code="TST", seq=2, is_interchange=False),
        ],
        sectors=[
            Sector(
                sector_id="SEC:TST:S01_S02",
                line_code="TST",
                from_station_id="S01",
                to_station_id="S02",
                seq=1,
                is_shared=False,
            )
        ],
        locations=locations,
        buffer_rules=[
            BufferRule(
                nature_of_works=NatureOfWorks.NON_LIVE_OTHERS,
                up_to_buffer_sectors=0,
                opposite_bound_required=False,
            )
        ],
        parameters=PlanningParameters(horizon_start=date(2027, 1, 4), horizon_weeks=2),
        contracts=[
            Contract(
                contract_number="C001",
                contract_description="Test contract",
                contract_award_date=date(2026, 1, 1),
                activity_type=ActivityType.RENEWAL,
                nature_of_activity=NatureOfWorks.NON_LIVE_OTHERS,
                contract_priority=ContractPriority.P1,
                contract_completion_date=date(2027, 1, 17),
                planned_completion_date=date(2027, 1, 10),
                number_of_workfronts=workfronts,
                access_type=AccessType.C,
                number_of_maximum_access_per_week=2,
            )
        ],
        activities=[
            Activity(
                activity_id=activity_id,
                contract_number="C001",
                activity_type=ActivityType.RENEWAL,
                start_location_id="SEC:TST:S01_S02:EB",
                end_location_id="SEC:TST:S01_S02:EB",
                total_accesses=1,
                planned_start_date=date(2027, 1, 4),
                activity_priority=ActivityPriority.P1,
            )
            for activity_id in ("A001", "A002")
        ],
    )


def bundle(instance: ProblemInstance) -> FixedScheduleBundle:
    access = [
        AccessScheduleRow(
            activity_id="A001", access_seq=1, week=1, eclo=False, access_night=1
        ),
        AccessScheduleRow(
            activity_id="A002", access_seq=1, week=1, eclo=False, access_night=2
        ),
    ]
    occupancy = [
        OccupancyScheduleRow(
            activity_id=activity_id,
            week=1,
            location_id=location.location_id,
            co_share_group="G1",
        )
        for activity_id in ("A001", "A002")
        for location in instance.locations
    ]
    return FixedScheduleBundle(
        bundle_id="bundle-test",
        instance_revision_id="rev-test",
        scenario="A",
        fingerprint="unchanged",
        access_rows=access,
        occupancy_rows=occupancy,
        result_rows=[
            ScenarioResultRow(
                scenario="A",
                contract_number="C001",
                simulated_completion_date=date(2027, 1, 10),
                overrun_days=0,
            )
        ],
    )


def test_maps_fixed_accesses_to_real_date_without_using_local_index_as_weekday():
    instance = problem()
    source = bundle(instance)
    calendar = demo_calendar("rev-test").model_copy(
        update={
            "contract_rules": [
                ContractCalendarRule(
                    contract_number="C001",
                    eligible_dates=[date(2027, 1, 6)],
                )
            ]
        }
    )
    result = calendarise(
        instance,
        source,
        "calendar-test",
        calendar,
        options=CalendariseOptions(time_limit_seconds=5, num_search_workers=1),
    )
    assert result.complete
    assert {row.service_date for row in result.assignments} == {date(2027, 1, 6)}
    assert [row.access_night for row in result.assignments] == [1, 2]
    assert [row.model_dump() for row in source.access_rows] == [
        row.model_dump() for row in bundle(instance).access_rows
    ]
    assert result.validation.passed


def test_fixed_sharing_that_exceeds_real_workfronts_returns_conflict():
    instance = problem(workfronts=1)
    source = bundle(instance)
    before = source.model_dump()
    result = calendarise(instance, source, "calendar-test", demo_calendar("rev-test"))
    assert not result.complete
    assert any(
        issue.rule_code == "SHARING_EXCEEDS_WORKFRONTS"
        for issue in result.conflicts
    )
    assert source.model_dump() == before


def test_location_blackouts_move_accesses_without_changing_local_indices():
    from backend.app.ps1.calendar_models import LocationNightRule

    instance = problem()
    source = bundle(instance)
    blocked = [
        LocationNightRule(
            service_date=date(2027, 1, day),
            location_id="SEC:TST:S01_S02:EB",
            maintenance_available=False,
            possession_capacity=0,
        )
        for day in range(4, 10)
    ]
    calendar = demo_calendar("rev-test").model_copy(
        update={"location_nights": blocked}
    )
    result = calendarise(instance, source, "calendar-test", calendar)
    assert result.complete
    assert {item.service_date for item in result.assignments} == {date(2027, 1, 10)}
    assert [item.access_night for item in result.assignments] == [1, 2]


def test_same_local_index_for_different_contracts_can_use_different_weekdays():
    base = problem()
    second_contract = base.contracts[0].model_copy(
        update={"contract_number": "C002", "contract_description": "Second"}
    )
    second_activity = base.activities[1].model_copy(
        update={"contract_number": "C002"}
    )
    instance = ProblemInstance(
        lines=base.lines,
        stations=base.stations,
        sectors=base.sectors,
        locations=[item.model_copy(update={"supply_capacity": 2}) for item in base.locations],
        buffer_rules=base.buffer_rules,
        parameters=base.parameters,
        contracts=[base.contracts[0], second_contract],
        activities=[base.activities[0], second_activity],
    )
    source = bundle(instance).model_copy(
        update={
            "scenario": "B",
            "access_rows": [
                AccessScheduleRow(
                    activity_id="A001", access_seq=1, week=1, eclo=False, access_night=1
                ),
                AccessScheduleRow(
                    activity_id="A002", access_seq=1, week=1, eclo=False, access_night=1
                ),
            ],
            "occupancy_rows": [
                row.model_copy(
                    update={"co_share_group": "G2" if row.activity_id == "A002" else "G1"}
                )
                for row in bundle(instance).occupancy_rows
            ],
            "result_rows": [
                ScenarioResultRow(
                    scenario="B",
                    contract_number=contract,
                    simulated_completion_date=date(2027, 1, 10),
                    overrun_days=0,
                )
                for contract in ("C001", "C002")
            ],
        }
    )
    calendar = demo_calendar("rev-test").model_copy(
        update={
            "contract_rules": [
                ContractCalendarRule(
                    contract_number="C001", eligible_dates=[date(2027, 1, 6)]
                ),
                ContractCalendarRule(
                    contract_number="C002", eligible_dates=[date(2027, 1, 8)]
                ),
            ]
        }
    )
    result = calendarise(instance, source, "calendar-test", calendar)
    assert result.complete
    assert {item.activity_id: item.service_date for item in result.assignments} == {
        "A001": date(2027, 1, 6),
        "A002": date(2027, 1, 8),
    }


def test_final_horizon_sunday_is_a_valid_service_date():
    instance = problem()
    source = bundle(instance).model_copy(
        update={
            "access_rows": [
                row.model_copy(update={"week": 2}) for row in bundle(instance).access_rows
            ],
            "occupancy_rows": [
                row.model_copy(update={"week": 2})
                for row in bundle(instance).occupancy_rows
            ],
            "result_rows": [
                ScenarioResultRow(
                    scenario="A",
                    contract_number="C001",
                    simulated_completion_date=date(2027, 1, 17),
                    overrun_days=7,
                )
            ],
        }
    )
    calendar = demo_calendar("rev-test").model_copy(
        update={
            "contract_rules": [
                ContractCalendarRule(
                    contract_number="C001", eligible_dates=[date(2027, 1, 17)]
                )
            ]
        }
    )
    result = calendarise(instance, source, "calendar-test", calendar)
    assert result.complete
    assert {row.service_date for row in result.assignments} == {
        instance.parameters.horizon_end
    }


def test_conflicting_fixed_dates_for_one_shared_group_return_no_mapping():
    instance = problem()
    source = bundle(instance)
    before = source.model_dump()
    result = calendarise(
        instance,
        source,
        "calendar-test",
        demo_calendar("rev-test"),
        commitments=[
            DateCommitment(
                activity_id="A001", access_seq=1, service_date=date(2027, 1, 5)
            ),
            DateCommitment(
                activity_id="A002", access_seq=1, service_date=date(2027, 1, 6)
            ),
        ],
    )
    assert not result.complete
    assert result.assignments == []
    assert any(
        conflict.rule_code in {
            "SHARED_GROUP_NO_COMMON_DATE",
            "SHARING_COMPONENT_NO_COMMON_DATE",
        }
        for conflict in result.conflicts
    )
    assert source.model_dump() == before


def test_calendar_eclo_blackout_rejects_fixed_eclo_without_changing_it():
    instance = problem()
    source = bundle(instance).model_copy(
        update={
            "scenario": "B",
            "access_rows": [
                row.model_copy(update={"eclo": True})
                for row in bundle(instance).access_rows
            ],
            "result_rows": [
                ScenarioResultRow(
                    scenario="B",
                    contract_number="C001",
                    simulated_completion_date=date(2027, 1, 10),
                    overrun_days=0,
                )
            ],
        }
    )
    calendar = demo_calendar("rev-test").model_copy(
        update={
            "line_nights": [
                LineNightRule(
                    service_date=date(2027, 1, day),
                    line_code="TST",
                    eclo_eligible=False,
                )
                for day in range(4, 11)
            ]
        }
    )
    result = calendarise(instance, source, "calendar-test", calendar)
    assert not result.complete
    assert result.assignments == []
    assert all(row.eclo for row in source.access_rows)
    assert any(conflict.rule_code == "NO_ELIGIBLE_DATE" for conflict in result.conflicts)


def test_unknown_solver_status_is_not_reported_as_infeasible(monkeypatch):
    from ortools.sat.python import cp_model

    instance = problem()
    source = bundle(instance)
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda _self, _model: cp_model.UNKNOWN)
    result = calendarise(instance, source, "calendar-test", demo_calendar("rev-test"))
    assert result.solver_status.value == "UNKNOWN"
    assert not result.complete
    assert result.assignments == []
    assert result.conflicts[0].rule_code == "CALENDAR_SEARCH_INCOMPLETE"


def test_calendarisation_never_calls_the_weekly_solver(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("weekly solver was called")

    monkeypatch.setattr("backend.app.ps1.solver.solve_ps1", forbidden)
    result = calendarise(
        problem(), bundle(problem()), "calendar-test", demo_calendar("rev-test")
    )
    assert result.complete


def test_independent_validator_rejects_changed_week():
    instance = problem()
    source = bundle(instance)
    result = calendarise(instance, source, "calendar-test", demo_calendar("rev-test"))
    assert result.complete
    corrupted = result.assignments[0].model_copy(update={"week": 2})
    validation = validate_calendarisation(
        instance,
        source,
        demo_calendar("rev-test"),
        [],
        [corrupted, *result.assignments[1:]],
    )
    assert not validation.passed
    assert any(issue.rule_code == "SOURCE_ACCESS_CHANGED" for issue in validation.issues)


def test_calendar_model_rejects_duplicate_location_date_rules():
    from backend.app.ps1.calendar_models import LocationNightRule
    import pytest

    repeated = LocationNightRule(
        service_date=date(2027, 1, 4),
        location_id="SEC:TST:S01_S02:EB",
    )
    with pytest.raises(ValueError, match="Duplicate location/date"):
        OperatingCalendarInput(
            instance_revision_id="rev-test",
            location_nights=[repeated, repeated],
        )


def test_http_import_worker_and_result_preserve_original_bytes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.config import ROOT, Settings
    from backend.app.db.repositories.calendars import get_bundle_file_bytes
    from backend.app.db.repositories.calendars import (
        claim_next_calendar_attempt,
        recover_stale_calendar_attempts,
    )
    from backend.app.db.models import CalendarAttemptRecord
    from backend.app.db.records import get
    from backend.app.db.repositories.instances import create_instance_revision
    from backend.app.main import create_app
    from backend.app.ps1.calendar_worker import process_next

    # Exercise the optional CLI worker separately from the automatic web path.
    # Automatic HTTP execution is covered in test_ps1_calendar_preview.py.
    monkeypatch.setattr(
        "backend.app.api.ps1_calendar_routes.process_attempt",
        lambda *_args, **_kwargs: False,
    )

    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            auth_mode="demo",
            database_path=str(tmp_path / "calendar.sqlite3"),
            dataset_path=str(tmp_path / "unused.json"),
            official_data_path=str(ROOT / "data"),
        )
    )
    headers = {"X-Demo-User": "demo-officer"}
    source_bytes = {
        "SCHEDULE_ACCESS.csv": (
            b"activity_id,access_seq,week,eclo,access_night\n"
            b"A001,1,1,0,1\nA002,1,1,0,2\n"
        ),
        "SCHEDULE_OCCUPANCY.csv": (
            b"activity_id,week,location_id,co_share_group\n"
            b"A001,1,SEC:TST:S01_S02:EB,G1\n"
            b"A001,1,PLAT:TST:S01:EB,G1\n"
            b"A001,1,PLAT:TST:S02:EB,G1\n"
            b"A002,1,SEC:TST:S01_S02:EB,G1\n"
            b"A002,1,PLAT:TST:S01:EB,G1\n"
            b"A002,1,PLAT:TST:S02:EB,G1\n"
        ),
        "RESULTS.csv": (
            b"scenario,contract_number,simulated_completion_date,overrun_days\n"
            b"A,C001,2027-01-10,0\n"
        ),
    }
    with TestClient(app) as client:
        assert client.post(
            "/api/ps1/enrichments/demo-calendar",
            json={"instance_revision_id": "missing"},
        ).status_code in {401, 403}
        with app.state.db.connection(write=True) as connection:
            _instance, revision = create_instance_revision(
                connection,
                problem(),
                name="Calendar test instance",
                created_by="test",
                input_fingerprint="calendar-test-instance",
            )
        response = client.post(
            "/api/ps1/schedule-bundles",
            headers=headers,
            data={"instance_revision_id": revision.id},
            files=[
                ("files", (name, content, "text/csv"))
                for name, content in source_bytes.items()
            ],
        )
        assert response.status_code == 201, response.text
        bundle_id = response.json()["bundle_id"]
        calendar_response = client.post(
            "/api/ps1/enrichments/demo-calendar",
            headers=headers,
            json={"instance_revision_id": revision.id},
        )
        assert calendar_response.status_code == 201
        calendar_id = calendar_response.json()["calendar_revision_id"]
        queued = client.post(
            f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
            headers=headers,
            json={
                "calendar_revision_id": calendar_id,
                "expected_instance_revision_id": revision.id,
                "options": {
                    "time_limit_seconds": 5,
                    "num_search_workers": 1,
                    "random_seed": 0,
                },
            },
        )
        assert queued.status_code == 202
        mismatch = client.post(
            f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
            headers=headers,
            json={
                "calendar_revision_id": calendar_id,
                "expected_instance_revision_id": "different-revision",
            },
        )
        assert mismatch.status_code == 409
        assert process_next(app.state.db, "test-worker")
        result = client.get(
            f"/api/ps1/calendarisations/{queued.json()['attempt_id']}",
            headers=headers,
        )
        assert result.status_code == 200
        payload = result.json()
        assert payload["status"] == "SUCCEEDED"
        assert payload["complete"] is True
        assert len(payload["assignments"]) == 2
        assert payload["source_score_unchanged"] is True
        with app.state.db.connection() as connection:
            assert get_bundle_file_bytes(connection, bundle_id) == source_bytes

        crashed = client.post(
            f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
            headers=headers,
            json={
                "calendar_revision_id": calendar_id,
                "expected_instance_revision_id": revision.id,
            },
        )
        with monkeypatch.context() as patcher:
            patcher.setattr(
                "backend.app.ps1.calendar_worker.calendarise",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            assert process_next(app.state.db, "crash-worker")
        crashed_result = client.get(
            f"/api/ps1/calendarisations/{crashed.json()['attempt_id']}",
            headers=headers,
        ).json()
        assert crashed_result["status"] == "FAILED"
        assert crashed_result["complete"] is False
        assert crashed_result["assignments"] == []

        for _ in range(2):
            response = client.post(
                f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
                headers=headers,
                json={
                    "calendar_revision_id": calendar_id,
                    "expected_instance_revision_id": revision.id,
                },
            )
            assert response.status_code == 202
        with app.state.db.connection(write=True) as connection:
            stale = claim_next_calendar_attempt(connection, "stale-worker")
            fresh = claim_next_calendar_attempt(connection, "fresh-worker")
            assert stale is not None and fresh is not None
            connection.execute(
                "UPDATE calendarisation_attempts SET started_at=? WHERE id=?",
                ("2000-01-01T00:00:00+00:00", stale.id),
            )
            recovered = recover_stale_calendar_attempts(
                connection, now=datetime.now(timezone.utc)
            )
            assert stale.id in recovered
            assert get(connection, CalendarAttemptRecord, stale.id).status == "FAILED"
            assert get(connection, CalendarAttemptRecord, fresh.id).status == "RUNNING"
        restrictive = demo_calendar(revision.id).model_copy(
            update={
                "contract_rules": [
                    ContractCalendarRule(
                        contract_number="C001", nightly_workfront_limit=1
                    )
                ]
            }
        )
        calendar_response = client.post(
            "/api/ps1/enrichments",
            headers=headers,
            json=restrictive.model_dump(mode="json"),
        )
        restrictive_id = calendar_response.json()["calendar_revision_id"]
        failed = client.post(
            f"/api/ps1/schedule-bundles/{bundle_id}/calendarize",
            headers=headers,
            json={
                "calendar_revision_id": restrictive_id,
                "expected_instance_revision_id": revision.id,
            },
        )
        assert process_next(app.state.db, "failure-worker")
        failed_result = client.get(
            f"/api/ps1/calendarisations/{failed.json()['attempt_id']}",
            headers=headers,
        ).json()
        assert failed_result["complete"] is False
        assert failed_result["assignments"] == []
        assert any(
            item["rule_code"] == "SHARING_EXCEEDS_WORKFRONTS"
            for item in failed_result["conflicts"]
        )
        with app.state.db.connection() as connection:
            assert get_bundle_file_bytes(connection, bundle_id) == source_bytes


def test_schema_v1_upgrades_once_and_preserves_existing_rows(tmp_path):
    from backend.app.database import Database

    database = Database(str(tmp_path / "migration.sqlite3"))
    database.initialize()
    with database.connection(write=True) as connection:
        connection.execute("DELETE FROM ps1_schema_version WHERE version=2")
        for table in (
            "calendar_assignments",
            "calendarisation_attempts",
            "calendar_revisions",
            "schedule_bundle_results",
            "schedule_bundle_occupancies",
            "schedule_bundle_accesses",
            "schedule_bundle_files",
            "schedule_bundles",
        ):
            connection.execute(f"DROP TABLE {table}")
        connection.execute(
            "INSERT INTO instances VALUES (?,?,?,?,?,?)",
            ("kept", "Kept", "f" * 64, "test", "ACTIVE", "2027-01-01"),
        )
    database.initialize()
    database.initialize()
    with database.connection() as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM ps1_schema_version"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT name FROM instances WHERE id='kept'"
        ).fetchone()[0] == "Kept"
