"""SQLite repository. Every mutation has one short transaction and a revision bump.
JSON columns deliberately keep the seed contract readable for a hackathon.
Do not share the database file through Git; migrate before multi-instance hosting.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
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
