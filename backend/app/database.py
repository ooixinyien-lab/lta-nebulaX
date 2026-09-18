"""SQLite repository. Every mutation has one short transaction and a revision bump.
JSON columns deliberately keep the seed contract readable for a hackathon.
Do not share the database file through Git; migrate before multi-instance hosting.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


class _SelectStmt:
    """Minimal stand-in for a SQLAlchemy select() statement used by railway_map."""
    def __init__(self, model_cls):
        self._model = model_cls
        self._wheres: list[tuple[str, object]] = []
        self._order_cols: list[str] = []
        self._limit_val: int | None = None

    def where(self, *conditions):
        clone = _SelectStmt(self._model)
        clone._wheres = list(self._wheres)
        clone._order_cols = list(self._order_cols)
        clone._limit_val = self._limit_val
        for cond in conditions:
            clone._wheres.append(cond)
        return clone

    def order_by(self, *cols):
        clone = _SelectStmt(self._model)
        clone._wheres = list(self._wheres)
        clone._order_cols = [c._col if hasattr(c, "_col") else str(c) for c in cols]
        clone._limit_val = self._limit_val
        return clone

    def limit(self, n):
        clone = _SelectStmt(self._model)
        clone._wheres = list(self._wheres)
        clone._order_cols = list(self._order_cols)
        clone._limit_val = n
        return clone

    def _build_sql(self):
        table = self._model.table
        sql = f"SELECT * FROM {table}"
        params: list[object] = []
        if self._wheres:
            parts = []
            for w in self._wheres:
                parts.append(f"{w._col} = ?")
                params.append(w._val)
            sql += " WHERE " + " AND ".join(parts)
        if self._order_cols:
            sql += " ORDER BY " + ", ".join(self._order_cols)
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        return sql, params


class _ColRef:
    """Proxy for ModelClass.column_name used in .where() and .order_by()."""
    def __init__(self, model_cls, col: str):
        self._model = model_cls
        self._col = col
        self._val = None

    def __eq__(self, other):  # type: ignore[override]
        ref = _ColRef(self._model, self._col)
        ref._val = other
        return ref

    def desc(self):
        return _ColDesc(self._col)


class _ColDesc:
    def __init__(self, col: str):
        self._col = f"{col} DESC"


class _PydanticModelMeta(type):
    """Metaclass that wires attribute access on model classes to _ColRef proxies."""
    def __getattr__(cls, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return _ColRef(cls, name)


def select(model_cls) -> _SelectStmt:  # noqa: F811 – shadows sqlalchemy.select locally
    return _SelectStmt(model_cls)


class _ModelColumns:
    """Use C(ModelClass).field_name to get a _ColRef without hitting Pydantic's metaclass."""
    def __init__(self, model_cls):
        self._model = model_cls
    def __getattr__(self, name: str) -> _ColRef:
        return _ColRef(self._model, name)


def C(model_cls) -> _ModelColumns:
    """Column reference factory: C(MyModel).field_name → usable in .where() and .order_by()."""
    return _ModelColumns(model_cls)


class _DbSession:
    """Minimal SQLAlchemy Session-like object backed by a raw sqlite3 connection."""

    def __init__(self, con: sqlite3.Connection):
        self._con = con

    def _row_to_model(self, model_cls, row: sqlite3.Row):
        import json as _json
        data = dict(row)
        # Deserialise JSON columns stored as TEXT
        for key, val in data.items():
            if isinstance(val, str) and val.startswith(("[", "{")):
                try:
                    data[key] = _json.loads(val)
                except Exception:
                    pass
        return model_cls(**data)

    def scalar(self, stmt: _SelectStmt):
        sql, params = stmt._build_sql()
        row = self._con.execute(sql, params).fetchone()
        if row is None:
            return None
        return self._row_to_model(stmt._model, row)

    def scalars(self, stmt: _SelectStmt):
        sql, params = stmt._build_sql()
        rows = self._con.execute(sql, params).fetchall()

        class _Result:
            def __init__(self, items):
                self._items = items
            def all(self):
                return self._items

        return _Result([self._row_to_model(stmt._model, r) for r in rows])


class Database:
    """Shared local storage; synthetic state is initialized only on explicit request."""

    def __init__(self, path: str, dataset_path: str | None = None):
        self.path = str(Path(path).resolve())
        self.dataset_path = str(Path(dataset_path).resolve()) if dataset_path else None
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self, write=False):
        con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        try:
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def session(self):
        """SQLAlchemy Session-compatible context manager for railway_map.py."""
        with self.connection() as con:
            yield _DbSession(con)

    def initialize(self, *, seed_legacy: bool = False):
        # WAL must be configured outside a transaction. Schema changes below are
        # additive and transactional, including when upgrading an existing file.
        with closing(sqlite3.connect(self.path)) as con:
            con.execute("PRAGMA journal_mode=WAL")
        with self.connection(write=True) as c:
            for sql in [
                "CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, catalog TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS allocations (request_id TEXT PRIMARY KEY REFERENCES requests(id), payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)",
            ]:
                c.execute(sql)
            from .db.schema import upgrade_schema
            upgrade_schema(c)
            if seed_legacy and c.execute("SELECT id FROM meta").fetchone() is None:
                self.seed(c)

    def seed(self, c):
        """Replace application state with the configured synthetic snapshot."""
        if self.dataset_path is None:
            raise ValueError("Legacy seeding requires an explicit dataset_path")
        old = c.execute("SELECT revision FROM meta WHERE id=1").fetchone()
        revision = old[0] + 1 if old else 1
        fixture = json.loads(Path(self.dataset_path).read_text(encoding="utf-8"))
        requests = fixture.pop("requests")
        allocations = fixture.pop("committed_allocations")
        for table in ["allocations", "requests", "proposals", "audit", "meta"]:
            c.execute(f"DELETE FROM {table}")  # Static table names, never user input.
        c.execute("INSERT INTO meta VALUES (1, ?, ?)", (revision, json.dumps(fixture)))
        for r in requests:
            c.execute("INSERT INTO requests VALUES (?, ?, ?)", (r["id"], r["owner_id"], json.dumps(r)))
        for a in allocations:
            c.execute("INSERT INTO allocations VALUES (?, ?)", (a["request_id"], json.dumps(a)))
        self.audit(c, "system", "synthetic_seed", f"Loaded {Path(self.dataset_path).name}")

    def snapshot(self, c=None):
        if c is None:
            with self.connection() as cx:
                return self.snapshot(cx)
        row = c.execute("SELECT * FROM meta WHERE id=1").fetchone()
        if row is None:
            raise RuntimeError("Legacy catalog is not initialized; explicitly seed the legacy dataset first")
        result = json.loads(row["catalog"])
        result["metadata"]["planning_version"] = row["revision"]
        result["requests"] = [json.loads(r["payload"]) for r in c.execute("SELECT payload FROM requests ORDER BY id")]
        result["committed_allocations"] = [json.loads(r["payload"]) for r in c.execute("SELECT payload FROM allocations ORDER BY request_id")]
        return result

    @staticmethod
    def bump(c):
        c.execute("UPDATE meta SET revision=revision+1 WHERE id=1")

    @staticmethod
    def audit(c, actor, action, detail):
        c.execute("INSERT INTO audit(created_at,actor,action,detail) VALUES (?,?,?,?)", (
            datetime.now(timezone.utc).isoformat(), actor, action, detail))

    @staticmethod
    def save_catalog(c, snapshot):
        catalog = {k: v for k, v in snapshot.items() if k not in ["requests", "committed_allocations"]}
        c.execute("UPDATE meta SET catalog=? WHERE id=1", (json.dumps(catalog),))
