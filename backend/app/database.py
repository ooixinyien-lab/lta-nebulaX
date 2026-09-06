"""SQLite repository. Every mutation has one short transaction and a revision bump.
JSON columns deliberately keep the seed contract readable for a hackathon.
Do not share the database file through Git; migrate before multi-instance hosting.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from .config import ROOT

class Database:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self, write=False):
        con = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            con.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self):
        with self.connection(write=True) as c:
            for sql in [
                "CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, catalog TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS allocations (request_id TEXT PRIMARY KEY REFERENCES requests(id), payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS proposals (id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)",
            ]:
                c.execute(sql)
            if c.execute("SELECT id FROM meta").fetchone() is None:
                self.seed(c)

    def seed(self, c):
        old = c.execute("SELECT revision FROM meta WHERE id=1").fetchone()
        revision = old[0] + 1 if old else 1
        fixture = json.loads((ROOT / "data" / "demo_data.json").read_text())
        requests = fixture.pop("requests")
        allocations = fixture.pop("committed_allocations")
        for table in ["allocations", "requests", "proposals", "audit", "meta"]:
            c.execute(f"DELETE FROM {table}")  # Static table names, never user input.
        c.execute("INSERT INTO meta VALUES (1, ?, ?)", (revision, json.dumps(fixture)))
        for r in requests:
            c.execute("INSERT INTO requests VALUES (?, ?, ?)", (r["id"], r["owner_id"], json.dumps(r)))
        for a in allocations:
            c.execute("INSERT INTO allocations VALUES (?, ?)", (a["request_id"], json.dumps(a)))
        self.audit(c, "system", "demo_seed", "Synthetic fixture loaded")

    def snapshot(self, c=None):
        if c is None:
            with self.connection() as cx:
                return self.snapshot(cx)
        row = c.execute("SELECT * FROM meta WHERE id=1").fetchone()
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
