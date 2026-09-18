"""Small typed record helpers. Identifiers come only from model definitions."""
import json
import sqlite3
from typing import TypeVar
from backend.app.domain_models import PS1Base

T = TypeVar('T', bound=PS1Base)
JSON_FIELDS = {
    'detail', 'validation_errors', 'rule_results', 'score_components',
    'validation', 'assumptions', 'definition', 'commitments', 'options',
    'conflicts', 'line_codes', 'location_ids',
}


def decode(model: type[T], row: sqlite3.Row | None) -> T | None:
    if row is None:
        return None
    values = dict(row)
    for key in JSON_FIELDS & values.keys():
        if values[key] is not None:
            values[key] = json.loads(values[key])
    return model.model_validate(values)


def get(connection: sqlite3.Connection, model: type[T], identifier: str) -> T | None:
    return decode(model, connection.execute(f'SELECT * FROM {model.table} WHERE id=?', (identifier,)).fetchone())


def insert(connection: sqlite3.Connection, record: T) -> T:
    values = record.model_dump(mode='json')
    if values.get('id') == 0:
        del values['id']
    for key in JSON_FIELDS & values.keys():
        if values[key] is not None:
            values[key] = json.dumps(values[key])
    columns = ','.join(values)
    placeholders = ','.join('?' for _ in values)
    cursor = connection.execute(f'INSERT INTO {record.table} ({columns}) VALUES ({placeholders})', tuple(values.values()))
    if getattr(record, 'id', None) == 0:
        record.id = cursor.lastrowid
    return record


def insert_many(connection: sqlite3.Connection, records) -> None:
    for record in records:
        insert(connection, record)
