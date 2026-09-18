"""Create and reconstruct immutable PS1 instance revisions."""
from __future__ import annotations

from hashlib import sha256
from uuid import uuid4

from sqlite3 import Connection
from backend.app.db.records import decode, get, insert, insert_many

from backend.app.domain_models import ProblemInstance
from backend.app.db.models import (
    ActivityRow, BufferRuleRow, ContractRow, Instance, InstanceFile, InstanceRevision,
    LineRow, LocationRow, ParameterRow, SectorRow, StationRow,
)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def fingerprint_files(files: dict[str, bytes]) -> str:
    digest = sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[name])
        digest.update(b"\0")
    return digest.hexdigest()


def create_instance_revision(
    session: Connection,
    problem: ProblemInstance,
    *,
    name: str,
    created_by: str,
    input_fingerprint: str,
    parser_version: str = "ps1-v1",
    validation_status: str = "VALID",
    validation_errors: list[dict] | None = None,
    files: dict[str, dict[str, str | int]] | None = None,
) -> tuple[Instance, InstanceRevision]:
    """Persist a validated ProblemInstance as a new immutable revision."""
    existing = find_fingerprint(session, input_fingerprint)
    if existing is not None:
        return get(session, Instance, existing.instance_id), existing
    instance = insert(session, Instance(id=_id("inst"), name=name, fingerprint=input_fingerprint, created_by=created_by))
    revision_number = 0
    revision = InstanceRevision(
        id=_id("rev"), instance_id=instance.id, revision_number=revision_number + 1,
        input_fingerprint=input_fingerprint, parser_version=parser_version,
        validation_status=validation_status, validation_errors=validation_errors, created_by=created_by,
    )
    insert(session, revision)
    rid = revision.id
    insert_many(session, [LineRow(revision_id=rid, line_code=x.line_code, line_name=x.line_name) for x in problem.lines])
    insert_many(session, [StationRow(revision_id=rid, line_code=x.line_code, station_id=x.station_id, seq=x.seq, is_interchange=x.is_interchange) for x in problem.stations])
    insert_many(session, [SectorRow(revision_id=rid, sector_id=x.sector_id, line_code=x.line_code, from_station_id=x.from_station_id, to_station_id=x.to_station_id, seq=x.seq, is_shared=x.is_shared) for x in problem.sectors])
    insert_many(session, [LocationRow(revision_id=rid, location_id=x.location_id, location_kind=x.location_kind.value, line_code=x.line_code, bound=x.bound.value, supply_capacity=x.supply_capacity) for x in problem.locations])
    insert_many(session, [BufferRuleRow(revision_id=rid, nature_of_works=x.nature_of_works.value, up_to_buffer_sectors=x.up_to_buffer_sectors, opposite_bound_required=x.opposite_bound_required) for x in problem.buffer_rules])
    insert_many(session, [ParameterRow(revision_id=rid, key="horizon_start", value=problem.parameters.horizon_start.isoformat()), ParameterRow(revision_id=rid, key="horizon_weeks", value=str(problem.parameters.horizon_weeks))])
    insert_many(session, [ContractRow(revision_id=rid, contract_number=x.contract_number, contract_description=x.contract_description, contract_award_date=x.contract_award_date, activity_type=x.activity_type.value, nature_of_activity=x.nature_of_activity.value, contract_priority=int(x.contract_priority), contract_completion_date=x.contract_completion_date, planned_completion_date=x.planned_completion_date, number_of_workfronts=x.number_of_workfronts, access_type=x.access_type.value, number_of_maximum_access_per_week=x.number_of_maximum_access_per_week) for x in problem.contracts])
    insert_many(session, [ActivityRow(revision_id=rid, activity_id=x.activity_id, contract_number=x.contract_number, activity_type=x.activity_type.value, start_location_id=x.start_location_id, end_location_id=x.end_location_id, total_accesses=x.total_accesses, planned_start_date=x.planned_start_date, predecessor_activity_id=x.predecessor_activity_id, activity_priority=int(x.activity_priority)) for x in problem.activities])
    if files:
        insert_many(session, [InstanceFile(revision_id=rid, file_type=kind, original_filename=str(meta["filename"]), storage_key=str(meta["storage_key"]), sha256=str(meta["sha256"]), size_bytes=int(meta["size_bytes"])) for kind, meta in files.items()])
    return instance, revision


def get_revision(session: Connection, revision_id: str) -> InstanceRevision | None:
    return get(session, InstanceRevision, revision_id)


def find_fingerprint(connection: Connection, fingerprint: str) -> InstanceRevision | None:
    return decode(InstanceRevision, connection.execute(
        "SELECT * FROM instance_revisions WHERE input_fingerprint=? ORDER BY revision_number DESC LIMIT 1",
        (fingerprint,),
    ).fetchone())


def load_revision(connection: Connection, revision_id: str) -> ProblemInstance:
    """Reconstruct the typed official instance without depending on source files."""
    if get_revision(connection, revision_id) is None:
        raise KeyError(revision_id)
    entities = {}
    for field, model in (("lines", LineRow), ("stations", StationRow), ("sectors", SectorRow),
                         ("locations", LocationRow), ("buffer_rules", BufferRuleRow),
                         ("contracts", ContractRow), ("activities", ActivityRow)):
        entities[field] = [decode(model, row).model_dump(exclude={"revision_id"}) for row in
                           connection.execute(f"SELECT * FROM {model.table} WHERE revision_id=? ORDER BY rowid", (revision_id,))]
    entities["parameters"] = dict(connection.execute("SELECT key,value FROM instance_parameters WHERE revision_id=?", (revision_id,)))
    return ProblemInstance.model_validate(entities)
