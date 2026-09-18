"""HTTP boundary for immutable schedule imports and operational calendarisation."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile

from backend.app.auth.dependencies import current_user, officer_only
from backend.app.config import DEMO_USERS
from backend.app.db.models import CalendarAttemptRecord, CalendarRevisionRecord, ScheduleBundleRecord
from backend.app.db.records import get
from backend.app.db.repositories.audit import record_event
from backend.app.db.repositories.calendars import (
    OUTPUT_FILENAMES,
    create_calendar_attempt,
    create_calendar_revision,
    create_schedule_bundle,
    find_bundle,
    get_bundle_file_bytes,
    load_assignments,
    load_calendar,
    load_preview_context,
    load_schedule_bundle,
)
from backend.app.db.repositories.instances import load_revision
from backend.app.domain_models import PS1Base
from pydantic import Field
from backend.app.ps1.artifacts import (
    ArtifactFormatError,
    read_access_schedule_bytes,
    read_occupancy_schedule_bytes,
    read_results_bytes,
)
from backend.app.ps1.calendar_models import (
    CalendariseOptions,
    CalendarPreviewContext,
    DateCommitment,
    OperatingCalendarInput,
    demo_calendar,
)
from backend.app.ps1.calendar_validation import (
    validate_calendar_definition,
    validate_fixed_bundle,
)
from backend.app.ps1.scoring import compute_score
from backend.app.ps1.calendar_worker import process_attempt
from backend.app.schemas import User


router = APIRouter(prefix="/api/ps1", tags=["ps1-calendar"])


class DemoCalendarRequest(PS1Base):
    instance_revision_id: str


class CalendariseRequest(PS1Base):
    calendar_revision_id: str
    expected_instance_revision_id: str
    commitments: list[DateCommitment] = Field(default_factory=list)
    options: CalendariseOptions = Field(default_factory=CalendariseOptions)


def _db(request: Request):
    return request.app.state.db


@router.get("/auth/config")
def auth_config(request: Request):
    settings = request.app.state.settings
    return {
        "auth_mode": settings.auth_mode,
        "demo_users": list(DEMO_USERS.values()) if settings.auth_mode == "demo" else [],
        "supabase_url": settings.supabase_url if settings.auth_mode == "supabase" else "",
        "supabase_publishable_key": (
            settings.supabase_publishable_key if settings.auth_mode == "supabase" else ""
        ),
    }


@router.get("/auth/me", response_model=User)
def auth_me(user: User = Depends(current_user)):
    return user


@router.get("/calendar-preview/context", response_model=CalendarPreviewContext)
def get_preview_context(
    request: Request,
    bundle_id: str | None = None,
    user: User = Depends(current_user),
):
    del user
    with _db(request).connection() as connection:
        try:
            return load_preview_context(connection, bundle_id)
        except KeyError as exc:
            raise HTTPException(404, "Schedule bundle not found") from exc


@router.post("/schedule-bundles", status_code=201)
async def import_schedule_bundle(
    request: Request,
    instance_revision_id: str = Form(...),
    files: list[UploadFile] = File(...),
    user: User = Depends(officer_only),
):
    supplied = [item.filename for item in files]
    if len(supplied) != 3 or set(supplied) != set(OUTPUT_FILENAMES):
        raise HTTPException(
            422,
            {
                "message": "Exactly the three official output CSV files are required",
                "required": list(OUTPUT_FILENAMES),
            },
        )
    contents = {item.filename: await item.read() for item in files}
    try:
        access_rows = read_access_schedule_bytes(contents["SCHEDULE_ACCESS.csv"])
        occupancy_rows = read_occupancy_schedule_bytes(
            contents["SCHEDULE_OCCUPANCY.csv"]
        )
        result_rows = read_results_bytes(contents["RESULTS.csv"])
    except ArtifactFormatError as exc:
        raise HTTPException(422, str(exc)) from exc
    scenarios = {row.scenario for row in result_rows}
    if len(scenarios) != 1 or not scenarios <= {"A", "B", "C"}:
        raise HTTPException(422, "RESULTS.csv must contain exactly one scenario A, B or C")
    scenario = next(iter(scenarios))
    with _db(request).connection() as connection:
        try:
            problem = load_revision(connection, instance_revision_id)
        except KeyError as exc:
            raise HTTPException(404, "Instance revision not found") from exc
    draft = {
        "bundle_id": "validation-only",
        "instance_revision_id": instance_revision_id,
        "scenario": scenario,
        "fingerprint": "pending",
        "access_rows": access_rows,
        "occupancy_rows": occupancy_rows,
        "result_rows": result_rows,
    }
    from backend.app.ps1.calendar_models import FixedScheduleBundle

    validation = validate_fixed_bundle(problem, FixedScheduleBundle.model_validate(draft))
    if not validation.passed:
        raise HTTPException(422, validation.model_dump(mode="json"))
    with _db(request).connection(write=True) as connection:
        from backend.app.db.repositories.instances import fingerprint_files

        fingerprint = fingerprint_files(contents)
        duplicate = find_bundle(connection, instance_revision_id, fingerprint)
        bundle = create_schedule_bundle(
            connection,
            revision_id=instance_revision_id,
            scenario=scenario,
            files=contents,
            access_rows=access_rows,
            occupancy_rows=occupancy_rows,
            result_rows=result_rows,
            validation=validation.model_dump(mode="json"),
            created_by=user.id,
        )
        if duplicate is None:
            record_event(
                connection,
                actor=user.id,
                action="schedule_bundle_imported",
                entity_type="schedule_bundle",
                entity_id=bundle.id,
                detail={"fingerprint": bundle.fingerprint, "scenario": scenario},
            )
    return {
        "bundle_id": bundle.id,
        "instance_revision_id": bundle.revision_id,
        "scenario": bundle.scenario,
        "source_mode": "fixed_output_bundle",
        "fingerprint": bundle.fingerprint,
        "duplicate": duplicate is not None,
        "access_count": len(access_rows),
        "original_files_preserved": True,
        "validation": validation.model_dump(mode="json"),
    }


@router.get("/schedule-bundles/{bundle_id}")
def get_schedule_bundle(
    bundle_id: str, request: Request, user: User = Depends(current_user)
):
    del user
    with _db(request).connection() as connection:
        try:
            bundle = load_schedule_bundle(connection, bundle_id)
            problem = load_revision(connection, bundle.instance_revision_id)
        except KeyError as exc:
            raise HTTPException(404, "Schedule bundle not found") from exc
        stored = get(connection, ScheduleBundleRecord, bundle_id)
        files = get_bundle_file_bytes(connection, bundle_id)
    return {
        "bundle_id": bundle.bundle_id,
        "instance_revision_id": bundle.instance_revision_id,
        "scenario": bundle.scenario,
        "fingerprint": bundle.fingerprint,
        "horizon_start": problem.parameters.horizon_start.isoformat(),
        "horizon_end": problem.parameters.horizon_end.isoformat(),
        "horizon_weeks": problem.parameters.horizon_weeks,
        "accesses": [
            {
                **row.model_dump(mode="json"),
                "access_id": f"{bundle.bundle_id}:{row.activity_id}:{row.access_seq}",
            }
            for row in bundle.access_rows
        ],
        "source_score": compute_score(
            problem, bundle.scenario, bundle.access_rows, bundle.occupancy_rows
        ).model_dump(mode="json"),
        "file_sizes": {name: len(content) for name, content in files.items()},
        "validation": stored.validation,
    }


def _create_calendar(
    request: Request, calendar: OperatingCalendarInput, user: User
):
    with _db(request).connection() as connection:
        try:
            problem = load_revision(connection, calendar.instance_revision_id)
        except KeyError as exc:
            raise HTTPException(404, "Instance revision not found") from exc
    issues = validate_calendar_definition(problem, calendar)
    if issues:
        raise HTTPException(422, [item.model_dump(mode="json") for item in issues])
    with _db(request).connection(write=True) as connection:
        record, created = create_calendar_revision(
            connection, calendar, created_by=user.id
        )
        if created:
            record_event(
                connection,
                actor=user.id,
                action="calendar_revision_created",
                entity_type="calendar_revision",
                entity_id=record.id,
                detail={"assumed_calendar": record.assumed_calendar},
            )
    return {
        "calendar_revision_id": record.id,
        "instance_revision_id": record.revision_id,
        "fingerprint": record.fingerprint,
        "assumed_calendar": record.assumed_calendar,
        "assumptions": record.assumptions,
        "created": created,
    }


@router.post("/enrichments", status_code=201)
def create_calendar(
    calendar: OperatingCalendarInput,
    request: Request,
    user: User = Depends(officer_only),
):
    return _create_calendar(request, calendar, user)


@router.post("/enrichments/demo-calendar", status_code=201)
def create_demo_calendar(
    payload: DemoCalendarRequest,
    request: Request,
    user: User = Depends(officer_only),
):
    return _create_calendar(request, demo_calendar(payload.instance_revision_id), user)


@router.get("/enrichments/{calendar_revision_id}")
def get_calendar(
    calendar_revision_id: str,
    request: Request,
    user: User = Depends(current_user),
):
    del user
    with _db(request).connection() as connection:
        try:
            record, calendar = load_calendar(connection, calendar_revision_id)
        except KeyError as exc:
            raise HTTPException(404, "Calendar revision not found") from exc
    return {
        "calendar_revision_id": record.id,
        "fingerprint": record.fingerprint,
        "definition": calendar.model_dump(mode="json"),
    }


@router.post("/schedule-bundles/{bundle_id}/calendarize", status_code=202)
def queue_calendarisation(
    bundle_id: str,
    payload: CalendariseRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(officer_only),
):
    with _db(request).connection(write=True) as connection:
        bundle = get(connection, ScheduleBundleRecord, bundle_id)
        calendar = get(
            connection, CalendarRevisionRecord, payload.calendar_revision_id
        )
        if bundle is None:
            raise HTTPException(404, "Schedule bundle not found")
        if calendar is None:
            raise HTTPException(404, "Calendar revision not found")
        if (
            bundle.revision_id != payload.expected_instance_revision_id
            or calendar.revision_id != payload.expected_instance_revision_id
        ):
            raise HTTPException(409, "Source, calendar and expected instance revisions differ")
        attempt = create_calendar_attempt(
            connection,
            bundle_id=bundle_id,
            calendar_revision_id=calendar.id,
            commitments=payload.commitments,
            options=payload.options,
            created_by=user.id,
        )
        record_event(
            connection,
            actor=user.id,
            action="calendarisation_queued",
            entity_type="calendarisation_attempt",
            entity_id=attempt.id,
            detail={"bundle_id": bundle_id, "calendar_revision_id": calendar.id},
        )
    # Starlette executes this synchronous task in its thread pool after sending
    # the response. The persisted queue and claim check also support a CLI worker.
    background_tasks.add_task(process_attempt, _db(request), attempt.id)
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "bundle_id": bundle_id,
        "calendar_revision_id": calendar.id,
    }


@router.get("/calendarisations/{attempt_id}")
def get_calendarisation(
    attempt_id: str, request: Request, user: User = Depends(current_user)
):
    del user
    with _db(request).connection() as connection:
        attempt = get(connection, CalendarAttemptRecord, attempt_id)
        if attempt is None:
            raise HTTPException(404, "Calendarisation attempt not found")
        bundle = load_schedule_bundle(connection, attempt.bundle_id)
        problem = load_revision(connection, bundle.instance_revision_id)
        calendar_record, _calendar = load_calendar(
            connection, attempt.calendar_revision_id
        )
        assignments = load_assignments(connection, attempt_id) if attempt.complete else []
        source_score = compute_score(
            problem, bundle.scenario, bundle.access_rows, bundle.occupancy_rows
        )
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "solver_status": attempt.solver_status,
        "solver_version": attempt.solver_version,
        "validator_version": attempt.validator_version,
        "complete": attempt.complete,
        "preference_value": attempt.preference_value,
        "error_message": attempt.error_message,
        "bundle_id": attempt.bundle_id,
        "calendar_revision_id": attempt.calendar_revision_id,
        "instance_revision_id": bundle.instance_revision_id,
        "scenario": bundle.scenario,
        "run_mode": "operational",
        "source_fingerprint": bundle.fingerprint,
        "source_score_unchanged": True,
        "source_score": source_score.model_dump(mode="json"),
        "official_export_eligible": False,
        "horizon_start": problem.parameters.horizon_start.isoformat(),
        "horizon_end": problem.parameters.horizon_end.isoformat(),
        "horizon_weeks": problem.parameters.horizon_weeks,
        "assumed_calendar": calendar_record.assumed_calendar,
        "assumptions": calendar_record.assumptions,
        "conflicts": attempt.conflicts,
        "validation": attempt.validation,
        "assignments": [item.model_dump(mode="json") for item in assignments],
    }
