"""Authenticated directory APIs; no integration secret is returned to the browser."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.access import Directory, password_hash

Role = Literal["client_admin", "project_operator", "approver", "viewer"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class Password(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class Named(Input):
    name: str = Field(min_length=1, max_length=100)


class Project(Named):
    tenant_id: str


class Environment(Named):
    project_id: str
    provider: Literal["synthetic", "auto", "electricity_maps", "uk", "recorded"] = "synthetic"


class Policy(Input):
    threshold_pct: float = Field(ge=0, le=100)
    threshold_g: float = Field(ge=0)
    safety_min: int = Field(ge=0, le=240)


class Consent(Input):
    share_aggregate: bool


class Grant(Input):
    tenant_id: str
    project_id: str | None = None
    role: Role

    @model_validator(mode="after")
    def scope(self):
        if (self.role == "client_admin") != (self.project_id is None):
            raise ValueError("Client administrators require client scope; other roles require a project")
        return self


class Membership(Grant):
    user_id: str


class NewUser(Grant):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(pattern=r"^[a-zA-Z0-9_.@-]{3,100}$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=256)


def access_router(directory: Directory) -> APIRouter:
    router = APIRouter(prefix="/api")

    def validate_grant(user: dict, grant: Grant):
        directory.require_admin(user, grant.tenant_id)
        if not directory.db.execute("SELECT 1 FROM tenants WHERE id=?", (grant.tenant_id,)).fetchone():
            raise HTTPException(404, "Client not found")
        if grant.project_id and not directory.db.execute("SELECT 1 FROM projects WHERE id=? AND tenant_id=?", (grant.project_id, grant.tenant_id)).fetchone():
            raise HTTPException(404, "Project not found in client")

    def project_admin(user: dict, project_id: str) -> dict:
        row = directory.db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Project not found")
        directory.require_admin(user, row["tenant_id"])
        return dict(row)

    @router.post("/auth/login")
    def login(data: Login, request: Request, response: Response):
        token = directory.login(data.username, data.password, request.client.host if request.client else "local")
        response.set_cookie("verdant_session", token, httponly=True, samesite="strict", secure=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true", max_age=28800, path="/")
        response.headers["Cache-Control"] = "no-store"
        return {"signed_in": True}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        with directory.transaction():
            directory.db.execute("DELETE FROM sessions WHERE digest=?", (hashlib.sha256(request.cookies.get("verdant_session", "").encode()).hexdigest(),))
        response.delete_cookie("verdant_session", path="/")
        return {"signed_out": True}

    @router.post("/auth/password")
    def password(data: Password, request: Request, response: Response):
        user = request.state.user
        with directory.transaction():
            row = directory.db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if not hmac.compare_digest(password_hash(data.current_password, row["salt"]), row["digest"]):
                raise HTTPException(403, "Current password is incorrect")
            salt = secrets.token_hex(16)
            directory.db.execute("UPDATE users SET salt=?,digest=? WHERE id=?", (salt, password_hash(data.new_password, salt), user["id"]))
            directory.db.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
            directory.event(user, "PASSWORD_CHANGED", user["id"], {})
        response.delete_cookie("verdant_session", path="/")
        return {"signed_out": True}

    @router.get("/auth/me")
    def me(request: Request):
        return {"user": request.state.user, "environments": directory.environments(request.state.user)}

    @router.get("/admin/directory")
    def listing(request: Request):
        user = request.state.user
        with directory.lock:
            tids = {r[0] for r in directory.db.execute("SELECT id FROM tenants") if user["platform_admin"] or "client_admin" in directory.membership(user, r[0])}
            # Non-admins receive only their accessible hierarchy, not user listings.
            if not tids:
                return {"tenants": [], "projects": [], "environments": [], "memberships": []}
            tenants = [dict(r) for r in directory.db.execute("SELECT * FROM tenants") if r["id"] in tids]
            projects = [dict(r) for r in directory.db.execute("SELECT * FROM projects") if r["tenant_id"] in tids]
            environments = [{**e, "credential_variable": directory.credential_name(e["id"]),
                             "credential_configured": bool(os.getenv(directory.credential_name(e["id"]))) or (e["id"] == "env-default" and bool(directory.settings.electricity_token))}
                            for e in directory.environments(user) if e["tenant_id"] in tids]
            grants = [dict(r) for r in directory.db.execute("SELECT m.rowid id,m.*,u.username,u.display_name FROM memberships m JOIN users u ON u.id=m.user_id") if r["tenant_id"] in tids]
            return {"tenants": tenants, "projects": projects, "environments": environments, "memberships": grants,
                    "guardrails": {"threshold_pct": directory.settings.threshold_pct, "threshold_g": directory.settings.threshold_g, "safety_min": directory.settings.safety_min}}

    @router.post("/admin/tenants", status_code=201)
    def tenant(data: Named, request: Request):
        directory.require_admin(request.state.user)
        tid = str(uuid4())
        with directory.transaction():
            directory.db.execute("INSERT INTO tenants VALUES (?,?,0)", (tid, data.name))
            directory.event(request.state.user, "CLIENT_CREATED", tid, {"name": data.name})
        return {"id": tid, "name": data.name, "share_aggregate": False}

    @router.post("/admin/projects", status_code=201)
    def project(data: Project, request: Request):
        directory.require_admin(request.state.user, data.tenant_id)
        pid = str(uuid4())
        with directory.transaction():
            if not directory.db.execute("SELECT 1 FROM tenants WHERE id=?", (data.tenant_id,)).fetchone():
                raise HTTPException(404, "Client not found")
            s = directory.settings
            directory.db.execute("INSERT INTO projects VALUES (?,?,?,?,?,?)", (pid, data.tenant_id, data.name, s.threshold_pct, s.threshold_g, s.safety_min))
            directory.event(request.state.user, "PROJECT_CREATED", pid, data.model_dump())
        return {"id": pid, **data.model_dump()}

    @router.post("/admin/environments", status_code=201)
    def environment(data: Environment, request: Request):
        eid = str(uuid4())
        with directory.transaction():
            project_admin(request.state.user, data.project_id)
            directory.db.execute("INSERT INTO environments VALUES (?,?,?,?)", (eid, data.project_id, data.name, data.provider))
            directory.event(request.state.user, "ENVIRONMENT_CREATED", eid, data.model_dump())
        # New workspaces start empty. Demo seeding is always an explicit action.
        env = directory.environment(request.state.user, eid)
        directory.service(env)
        return {"id": eid, **data.model_dump(), "credential_variable": directory.credential_name(eid)}

    @router.put("/admin/projects/{project_id}/policy")
    def policy(project_id: str, data: Policy, request: Request):
        s = directory.settings
        if data.threshold_pct < s.threshold_pct or data.threshold_g < s.threshold_g or data.safety_min < s.safety_min:
            raise HTTPException(422, "Project policy cannot weaken platform savings thresholds or SLA buffer")
        with directory.transaction():
            project_admin(request.state.user, project_id)
            directory.db.execute("UPDATE projects SET threshold_pct=?,threshold_g=?,safety_min=? WHERE id=?", (data.threshold_pct, data.threshold_g, data.safety_min, project_id))
            directory.event(request.state.user, "POLICY_CHANGED", project_id, data.model_dump())
            directory.invalidate(project_id)
        return data

    @router.put("/admin/environments/{environment_id}/provider")
    def provider(environment_id: str, data: Environment, request: Request):
        with directory.transaction():
            env = directory.environment(request.state.user, environment_id)
            project_admin(request.state.user, env["project_id"])
            if data.project_id != env["project_id"]:
                raise HTTPException(422, "An environment cannot be moved to another project")
            directory.db.execute("UPDATE environments SET name=?,provider=? WHERE id=?", (data.name, data.provider, environment_id))
            directory.event(request.state.user, "PROVIDER_CHANGED", environment_id, data.model_dump())
            directory.invalidate(env["project_id"])
        return {"id": environment_id, **data.model_dump()}

    @router.put("/admin/tenants/{tenant_id}/reporting")
    def consent(tenant_id: str, data: Consent, request: Request):
        user = request.state.user
        with directory.transaction():
            # Platform ownership alone is not client consent.
            if not directory.db.execute("SELECT 1 FROM memberships WHERE user_id=? AND tenant_id=? AND role='client_admin' AND project_id IS NULL", (user["id"], tenant_id)).fetchone():
                raise HTTPException(403, "A designated client administrator must authorize aggregate sharing")
            directory.db.execute("UPDATE tenants SET share_aggregate=? WHERE id=?", (int(data.share_aggregate), tenant_id))
            directory.event(user, "REPORTING_CONSENT_CHANGED", tenant_id, data.model_dump())
        return data

    @router.post("/admin/users", status_code=201)
    def new_user(data: NewUser, request: Request):
        with directory.transaction():
            validate_grant(request.state.user, data)
            try:
                uid = directory.create_user(data.username, data.display_name, data.password)
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Username is unavailable") from None
            directory.db.execute("INSERT INTO memberships VALUES (?,?,?,?)", (uid, data.tenant_id, data.project_id, data.role))
            directory.event(request.state.user, "USER_CREATED", uid, {"tenant_id": data.tenant_id, "project_id": data.project_id, "role": data.role})
        return {"id": uid, "username": data.username, "display_name": data.display_name}

    @router.post("/admin/memberships", status_code=201)
    def membership(data: Membership, request: Request):
        with directory.transaction():
            validate_grant(request.state.user, data)
            # Only platform administrators can link an existing identity to a new client.
            if not request.state.user["platform_admin"] and not directory.db.execute("SELECT 1 FROM memberships WHERE user_id=? AND tenant_id=?", (data.user_id, data.tenant_id)).fetchone():
                raise HTTPException(403, "Platform administrator must link identities across clients")
            if not directory.db.execute("SELECT 1 FROM users WHERE id=?", (data.user_id,)).fetchone():
                raise HTTPException(404, "User not found")
            if directory.db.execute("SELECT 1 FROM memberships WHERE user_id=? AND tenant_id=? AND project_id IS ? AND role=?",
                                    (data.user_id, data.tenant_id, data.project_id, data.role)).fetchone():
                return {"granted": True}
            directory.db.execute("INSERT INTO memberships VALUES (?,?,?,?)", (data.user_id, data.tenant_id, data.project_id, data.role))
            directory.event(request.state.user, "ACCESS_GRANTED", data.user_id, data.model_dump())
        return {"granted": True}

    @router.delete("/admin/memberships/{membership_id}")
    def revoke(membership_id: int, request: Request):
        with directory.transaction():
            row = directory.db.execute("SELECT * FROM memberships WHERE rowid=?", (membership_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Membership not found")
            directory.require_admin(request.state.user, row["tenant_id"])
            directory.db.execute("DELETE FROM memberships WHERE rowid=?", (membership_id,))
            directory.event(request.state.user, "ACCESS_REVOKED", row["user_id"], {"tenant_id": row["tenant_id"], "project_id": row["project_id"], "role": row["role"]})
        return {"revoked": True}

    @router.get("/admin/events")
    def events(request: Request):
        directory.require_admin(request.state.user)
        with directory.lock:
            return [dict(r) for r in directory.db.execute("SELECT * FROM admin_events ORDER BY id DESC LIMIT 500")]

    @router.get("/organization/report")
    def organization(request: Request):
        directory.require_admin(request.state.user)
        rows = []
        with directory.lock:
            for env in directory.environments(request.state.user):
                if not env["share_aggregate"]:
                    continue
                report = directory.service(env).report()
                rows.append({"tenant_id": env["tenant_id"], "client": env["tenant_name"], "project_id": env["project_id"],
                             "project": env["project_name"], "environment_id": env["id"], "environment": env["name"],
                             **{k: report[k] for k in ("source", "baseline_g", "scheduled_g", "avoided_g", "included_jobs", "total_jobs")}})
        baseline = sum(r["baseline_g"] for r in rows)
        saving = sum(r["avoided_g"] for r in rows)
        return {"scope": "Only client-authorized aggregate sharing; no job names or evidence", "accounting": "Modeled estimates, not measured emissions",
                "source": " + ".join(sorted({r["source"] for r in rows})) or "NO AUTHORIZED DATA",
                "baseline_g": baseline, "avoided_g": saving, "reduction_pct": saving * 100 / baseline if baseline else 0,
                "environments": rows}

    return router
