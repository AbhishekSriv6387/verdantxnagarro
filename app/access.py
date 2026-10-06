"""Local identity and tenant directory. Scheduling data lives in isolated environment stores."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException

from app.config import Settings
from app.service import SchedulerService
from app.store.sqlite import Store

ROLES = {"platform_admin", "client_admin", "project_operator", "approver", "viewer"}
DEFAULT_ENV = "env-default"


def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()


class Directory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = RLock()
        self.services: dict[str, SchedulerService] = {}
        self.path = ":memory:" if settings.database_path == ":memory:" else settings.database_path + ".control.db"
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
          display_name TEXT NOT NULL, salt TEXT NOT NULL, digest TEXT NOT NULL, platform_admin INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS tenants(id TEXT PRIMARY KEY, name TEXT NOT NULL, share_aggregate INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
          name TEXT NOT NULL, threshold_pct REAL NOT NULL, threshold_g REAL NOT NULL, safety_min INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS environments(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
          name TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'synthetic');
        CREATE TABLE IF NOT EXISTS memberships(user_id TEXT REFERENCES users(id), tenant_id TEXT REFERENCES tenants(id),
          project_id TEXT REFERENCES projects(id), role TEXT NOT NULL,
          UNIQUE(user_id, tenant_id, project_id, role));
        CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(subject TEXT PRIMARY KEY, count INTEGER NOT NULL, since REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_events(id INTEGER PRIMARY KEY, recorded_at REAL NOT NULL,
          user_id TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, details TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS admin_events_no_update BEFORE UPDATE ON admin_events
          BEGIN SELECT RAISE(ABORT, 'Administration history is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS admin_events_no_delete BEFORE DELETE ON admin_events
          BEGIN SELECT RAISE(ABORT, 'Administration history is append-only'); END;
        """)
        self.db.commit()
        with self.transaction():
            if not self.db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                password = os.getenv("VERDANT_ADMIN_PASSWORD") or secrets.token_urlsafe(24)
                if len(password) < 12:
                    raise ValueError("VERDANT_ADMIN_PASSWORD must be at least 12 characters")
                self.create_user("admin", "Platform administrator", password, True)
                if not os.getenv("VERDANT_ADMIN_PASSWORD") and self.path != ":memory:":
                    credential_file = Path(self.path).with_suffix(".bootstrap.txt")
                    fd = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as stream:
                        stream.write(f"Username: admin\nPassword: {password}\nChange the password after sign-in, then delete this file.\n")
            self.db.execute("INSERT OR IGNORE INTO tenants VALUES ('client-default','Local demo',0)")
            self.db.execute("INSERT OR IGNORE INTO projects VALUES ('project-default','client-default','Default project',?,?,?)",
                            (settings.threshold_pct, settings.threshold_g, settings.safety_min))
            self.db.execute("INSERT OR IGNORE INTO environments VALUES (?, 'project-default','Demo',?)",
                            (DEFAULT_ENV, settings.carbon_provider))

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def event(self, user: dict, action: str, target: str, details: dict) -> None:
        self.db.execute("INSERT INTO admin_events(recorded_at,user_id,action,target,details) VALUES(?,?,?,?,?)",
                        (time.time(), user["id"], action, target, json.dumps(details)))

    def create_user(self, username: str, name: str, password: str, platform_admin: bool = False) -> str:
        uid, salt = str(uuid4()), secrets.token_hex(16)
        self.db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
                        (uid, username.lower(), name, salt, password_hash(password, salt), int(platform_admin)))
        return uid

    def login(self, username: str, password: str, address: str) -> str:
        # Bound both per-account and per-address attempts; persist across restarts.
        now = time.time()
        blocked = False
        with self.transaction():
            for subject in ("user:" + username.lower(), "ip:" + address):
                row = self.db.execute("SELECT * FROM attempts WHERE subject=?", (subject,)).fetchone()
                count = row["count"] if row and now - row["since"] < 900 else 0
                since = row["since"] if count else now
                blocked |= count >= 20
                self.db.execute("INSERT OR REPLACE INTO attempts VALUES (?,?,?)", (subject, count + 1, since))
        if blocked:
            raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
        with self.transaction():
            row = self.db.execute("SELECT * FROM users WHERE username=?", (username.lower(),)).fetchone()
            actual = password_hash(password, row["salt"] if row else "00" * 16)
            if not row or not hmac.compare_digest(actual, row["digest"]):
                raise HTTPException(401, "Invalid username or password")
            token = secrets.token_urlsafe(32)
            self.db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            self.db.execute("INSERT INTO sessions VALUES (?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], now + 28800))
            self.event(dict(row), "SIGN_IN", row["id"], {})
            return token

    def user(self, token: str | None) -> dict:
        if not token:
            raise HTTPException(401, "Sign in to continue")
        with self.lock:
            row = self.db.execute("SELECT u.id,u.username,u.display_name,u.platform_admin FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.digest=? AND s.expires>?",
                                  (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not row:
            raise HTTPException(401, "Session expired. Sign in again.")
        return dict(row)

    def membership(self, user: dict, tenant_id: str, project_id: str | None = None) -> set[str]:
        if user["platform_admin"]:
            return {"platform_admin"}
        with self.lock:
            return {r[0] for r in self.db.execute("SELECT role FROM memberships WHERE user_id=? AND tenant_id=? AND (project_id IS NULL OR project_id=?)",
                                                (user["id"], tenant_id, project_id))}

    def require_admin(self, user: dict, tenant_id: str | None = None) -> None:
        if user["platform_admin"]:
            return
        if tenant_id and "client_admin" in self.membership(user, tenant_id):
            return
        raise HTTPException(403, "Administrator permission required for this client")

    def environments(self, user: dict) -> list[dict]:
        with self.lock:
            rows = [dict(r) for r in self.db.execute("""SELECT e.*,p.tenant_id,p.name project_name,t.name tenant_name,
              p.threshold_pct,p.threshold_g,p.safety_min,t.share_aggregate FROM environments e
              JOIN projects p ON p.id=e.project_id JOIN tenants t ON t.id=p.tenant_id ORDER BY t.name,p.name,e.name""")]
            return [{**r, "roles": sorted(roles)} for r in rows
                    if (roles := self.membership(user, r["tenant_id"], r["project_id"]))]

    def environment(self, user: dict, environment_id: str) -> dict:
        env = next((e for e in self.environments(user) if e["id"] == environment_id), None)
        if not env:
            raise HTTPException(404, "Workspace not found")
        return env

    @staticmethod
    def credential_name(environment_id: str) -> str:
        return "VERDANT_EM_TOKEN_" + environment_id.replace("-", "_").upper()

    def service(self, env: dict) -> SchedulerService:
        # IDs come exclusively from the directory, never from filesystem paths supplied by users.
        with self.lock:
            if env["id"] not in self.services:
                path = self.settings.database_path if env["id"] == DEFAULT_ENV else (
                    ":memory:" if self.path == ":memory:" else str(Path(self.path).parent / "environments" / (env["id"] + ".db")))
                token = os.getenv(self.credential_name(env["id"]), "")
                # Backward compatibility: the original token belongs only to the original demo.
                if env["id"] == DEFAULT_ENV and not token:
                    token = self.settings.electricity_token
                config = replace(self.settings, database_path=path, carbon_provider=env["provider"],
                                 electricity_token=token, enable_llm=False, openai_key="",
                                 threshold_pct=max(env["threshold_pct"], self.settings.threshold_pct),
                                 threshold_g=max(env["threshold_g"], self.settings.threshold_g),
                                 safety_min=max(env["safety_min"], self.settings.safety_min))
                store = Store(path)
                with store.transaction():
                    if env["id"] != DEFAULT_ENV and not store.get("clock"):
                        from app.seed import DEMO_START
                        store.set("clock", DEMO_START.isoformat())
                        store.set("run_id", str(uuid4()))
                        store.set("replay", None)
                    store.set("scope", {"tenant_id": env["tenant_id"], "project_id": env["project_id"], "environment_id": env["id"]})
                self.services[env["id"]] = SchedulerService(config, store)
                # Add stable IDs to legacy mutable jobs; historical audit rows are never rewritten.
                with store.transaction():
                    for job in store.jobs():
                        for key, value in store.get("scope").items():
                            setattr(job, key, value)
                        store.save(job)
            return self.services[env["id"]]

    def invalidate(self, project_id: str) -> None:
        # Directory writes serialize here; the store lock protects running scheduler transactions.
        for eid in [r[0] for r in self.db.execute("SELECT id FROM environments WHERE project_id=?", (project_id,))]:
            if service := self.services.get(eid):
                # Keep the open store (including in-memory stores); refresh policy/provider in place.
                env = dict(self.db.execute("SELECT e.*,p.threshold_pct,p.threshold_g,p.safety_min FROM environments e JOIN projects p ON p.id=e.project_id WHERE e.id=?", (eid,)).fetchone())
                token = os.getenv(self.credential_name(eid), "") or (self.settings.electricity_token if eid == DEFAULT_ENV else "")
                with service.store.lock:
                    service.settings = replace(service.settings, carbon_provider=env["provider"], electricity_token=token,
                                               threshold_pct=max(env["threshold_pct"], self.settings.threshold_pct),
                                               threshold_g=max(env["threshold_g"], self.settings.threshold_g),
                                               safety_min=max(env["safety_min"], self.settings.safety_min))
                    from app.providers.carbon import FallbackProvider
                    service.provider = FallbackProvider(service.settings)

    def close(self) -> None:
        for service in self.services.values():
            service.store.db.close()
        self.db.close()
