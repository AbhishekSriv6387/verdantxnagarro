"""Single-writer transactions and database-enforced append-only decision history."""
import copy
import hashlib
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
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS explanations (
            decision_id INTEGER PRIMARY KEY REFERENCES decisions(id), recorded_at TEXT NOT NULL, prose TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS explanations_no_update BEFORE UPDATE ON explanations
            BEGIN SELECT RAISE(ABORT, 'Explanation history is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS explanations_no_delete BEFORE DELETE ON explanations
            BEGIN SELECT RAISE(ABORT, 'Explanation history is append-only'); END;
        CREATE TABLE IF NOT EXISTS curves (hash TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS curves_no_update BEFORE UPDATE ON curves
            BEGIN SELECT RAISE(ABORT, 'Curve evidence is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS curves_no_delete BEFORE DELETE ON curves
            BEGIN SELECT RAISE(ABORT, 'Curve evidence is append-only'); END;
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

    def freeze(self, decision: dict) -> dict:
        result = copy.deepcopy(decision)
        summary = result.get("candidate_window_summary", {})
        candidates = summary.get("candidates", [])
        if len(candidates) > 4:  # Compact copied legacy evidence without rewriting old rows.
            retained = sorted(candidates, key=lambda c: (c["carbon_g"], c["start"]))[:3]
            chosen = next((c for c in candidates if c["start"] == result.get("chosen_start")), None)
            if chosen and chosen not in retained:
                retained.append(chosen)
            summary["candidates"] = retained
            summary["retained"] = "Best three plus chosen"
        curve = result.pop("curve_snapshot", None)
        if curve is not None:
            payload = json.dumps(curve, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(payload.encode()).hexdigest()
            self.db.execute("INSERT OR IGNORE INTO curves VALUES (?, ?)", (digest, payload))
            result["curve_hash"] = digest
        return result

    def curve(self, decision: dict) -> dict:
        if "curve_snapshot" in decision:  # Legacy append-only records remain readable.
            return decision["curve_snapshot"]
        row = self.db.execute("SELECT payload FROM curves WHERE hash=?", (decision["curve_hash"],)).fetchone()
        if row is None:
            raise KeyError("Frozen curve not found")
        return json.loads(row[0])

    def evidence(self, decision_id: int) -> dict:
        row = self.db.execute("SELECT payload FROM decisions WHERE id=?", (decision_id,)).fetchone()
        if row is None:
            raise KeyError("Decision not found")
        entry = json.loads(row[0])
        return {**entry, "id": decision_id, "curve_snapshot": self.curve(entry)}

    def append(self, entry: dict) -> int:
        entry = self.freeze(entry)
        cursor = self.db.execute("INSERT INTO decisions(run_id,job_id,actor,outcome,payload) VALUES(?,?,?,?,?)",
                        (entry["run_id"], entry["job_id"], entry["actor"], entry["outcome"], json.dumps(entry)))
        return cursor.lastrowid

    def append_explanation(self, decision_id: int, recorded_at: str, prose: str) -> None:
        self.db.execute("INSERT INTO explanations VALUES (?, ?, ?)", (decision_id, recorded_at, prose))

    def logs(self, run_id: str | None = None) -> list[dict]:
        query = "SELECT id,payload FROM decisions"
        args = ()
        if run_id:
            query += " WHERE run_id=?"
            args = (run_id,)
        query += " ORDER BY id DESC"
        entries = [{**json.loads(r["payload"]), "id": r["id"]} for r in self.db.execute(query, args)]
        narratives = {r["decision_id"]: r["prose"] for r in self.db.execute("SELECT * FROM explanations")}
        for entry in entries:
            if entry["id"] in narratives:
                entry["llm_explanation"] = narratives[entry["id"]]
        return entries
