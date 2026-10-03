"""Single-writer transactions and database-enforced append-only decision history."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator

from app.models import Job


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            job_id TEXT NOT NULL, actor TEXT NOT NULL, outcome TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS decisions_run ON decisions(run_id, id);
        CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions
            BEGIN SELECT RAISE(ABORT, 'Decision history is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
            BEGIN SELECT RAISE(ABORT, 'Decision history is append-only'); END;
        """)
        self.db.commit()

    @contextmanager
    def transaction(self) -> Iterator["Store"]:
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                yield self
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def jobs(self) -> list[Job]:
        return [Job.model_validate_json(row[0]) for row in self.db.execute("SELECT payload FROM jobs ORDER BY rowid")]

    def save(self, job: Job) -> None:
        self.db.execute("INSERT INTO jobs VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                        (job.id, job.model_dump_json()))

    def get(self, key: str, default=None):
        row = self.db.execute("SELECT payload FROM state WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value) -> None:
        self.db.execute("INSERT INTO state VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
                        (key, json.dumps(value)))

    def append(self, entry: dict) -> None:
        self.db.execute("INSERT INTO decisions(run_id,job_id,actor,outcome,payload) VALUES(?,?,?,?,?)",
                        (entry["run_id"], entry["job_id"], entry["actor"], entry["outcome"], json.dumps(entry)))

    def logs(self, run_id: str | None = None) -> list[dict]:
        query = "SELECT id,payload FROM decisions"
        args = ()
        if run_id:
            query += " WHERE run_id=?"
            args = (run_id,)
        query += " ORDER BY id DESC"
        return [{**json.loads(r["payload"]), "id": r["id"]} for r in self.db.execute(query, args)]
