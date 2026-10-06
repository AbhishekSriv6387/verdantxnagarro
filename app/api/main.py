import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.access import Directory, DEFAULT_ENV
from app.api.access import access_router
from app.config import Settings, ZONES
from app.models import AdvanceInput, ApprovalInput, JobInput, ScaleInput
from app.service import Conflict, SchedulerService

UI = Path(__file__).resolve().parents[1] / "ui"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname, "event": record.getMessage(),
                           **{key: getattr(record, key) for key in ("job_id", "outcome", "actor", "zone", "endpoint") if hasattr(record, key)}})


def create_app(settings: Settings | None = None) -> FastAPI:
    load_dotenv()
    settings = settings or Settings.from_env()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    directory = Directory(settings)
    service = directory.service(directory.environment({"platform_admin": True}, DEFAULT_ENV))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        directory.close()

    app = FastAPI(title="Verdant · Carbon-Aware Batch Scheduler", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.service = service
    app.state.directory = directory
    app.include_router(access_router(directory))
    app.mount("/static", StaticFiles(directory=UI), name="static")

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        if request.url.path.startswith("/api/") and request.url.path not in ("/api/health", "/api/auth/login"):
            try:
                request.state.user = directory.user(request.cookies.get("verdant_session"))
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        if request.url.path.startswith("/api/") or request.url.path in ("/", "/login", "/admin"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path in ("/", "/docs", "/login", "/admin") or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Validation responses must not echo passwords or other submitted secrets.
        return JSONResponse({"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
                                         for e in exc.errors()]}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing_handler(request: Request, exc: KeyError):
        return JSONResponse({"detail": "Job not found"}, status_code=404)

    def workspace(request: Request, action: str = "view"):
        user = request.state.user
        eid = request.query_params.get("environment_id") or request.headers.get("X-Environment-ID")
        if not eid:
            choices = directory.environments(user)
            if len(choices) != 1:
                raise HTTPException(400, "Select an environment_id")
            eid = choices[0]["id"]
        env = directory.environment(user, eid)
        roles = set(env["roles"])
        allowed = {"platform_admin", "client_admin"}
        if action == "operate":
            allowed.add("project_operator")
        elif action == "approve":
            allowed.add("approver")
        if action != "view" and not roles.intersection(allowed):
            raise HTTPException(403, "Your role cannot perform this action")
        request.state.environment = env
        request.state.is_admin = bool(roles.intersection({"platform_admin", "client_admin"}))
        request.state.assigned_project = env["project_name"] if not request.state.is_admin else None
        service = directory.service(env)
        return service, service.store, service.settings

    @app.get("/login", include_in_schema=False)
    def login_page():
        return FileResponse(UI / "login.html")

    @app.get("/admin", include_in_schema=False)
    def admin_page(request: Request):
        try:
            directory.user(request.cookies.get("verdant_session"))
        except HTTPException:
            return RedirectResponse("/login", status_code=303)
        return FileResponse(UI / "admin.html")

    @app.get("/", include_in_schema=False)
    def index(request: Request):
        try:
            directory.user(request.cookies.get("verdant_session"))
        except HTTPException:
            return RedirectResponse("/login", status_code=303)
        return FileResponse(UI / "index.html")

    @app.get("/docs", include_in_schema=False)
    def api_docs():
        return FileResponse(UI / "api.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "demo", "version": "1.0.0"}

    @app.get("/api/state")
    def state(request: Request, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        with store.lock:
            all_jobs = store.jobs()
            jobs = [j for j in all_jobs if not project or j.project == project]
            return {"workspace": request.state.environment, "user": request.state.user, "clock": service.now, "run_id": store.get("run_id"), "zones": ZONES,
                    "projects": sorted({j.project for j in all_jobs}), "selected_project": project,
                    "jobs": jobs, "report": service.report_for(jobs), "replay": store.get("replay"),
                    "pending_approvals": sum(j.status == "needs_approval" for j in jobs),
                    "config": {"pue": settings.pue, "safety_min": settings.safety_min,
                               "threshold_pct": settings.threshold_pct, "threshold_g": settings.threshold_g,
                               "embodied_g": settings.embodied_g, "llm_enabled": settings.enable_llm}}

    @app.get("/api/jobs")
    def jobs(request: Request, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        with store.lock:
            return [j for j in store.jobs() if not project or j.project == project]

    @app.post("/api/jobs", status_code=201)
    def add_job(request: Request, data: JobInput):
        service, store, settings = workspace(request, "operate")
        if request.state.assigned_project and data.project != request.state.assigned_project:
            raise HTTPException(403, f"You can only add jobs to project: {request.state.assigned_project}")
        return service.add(data)

    @app.get("/api/jobs/{job_id}/curve")
    def curve(request: Request, job_id: str):
        service, store, settings = workspace(request, "view")
        with store.lock:
            job = service._job(job_id)
            if request.state.assigned_project and job.project != request.state.assigned_project:
                raise HTTPException(403, "Access denied to this job")
            if job.decision:
                return store.curve(job.decision)
            return service.curve_for(job)

    @app.post("/api/agent/cycle")
    def cycle(request: Request):
        service, store, settings = workspace(request, "operate")
        return service.cycle(initiated_by=request.state.user["id"])

    @app.get("/api/approvals")
    def approvals(request: Request, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        with store.lock:
            return [j for j in store.jobs() if j.status == "needs_approval" and (not project or j.project == project)]

    @app.post("/api/approvals/{job_id}")
    def review(request: Request, job_id: str, data: ApprovalInput):
        service, store, settings = workspace(request, "approve")
        with store.lock:
            job = service._job(job_id)
            if request.state.assigned_project and job.project != request.state.assigned_project:
                raise HTTPException(403, "Access denied to this job")
        return service.review(job_id, data.action, data.comment, request.state.user["display_name"], request.state.user["id"])

    @app.post("/api/clock/advance")
    def advance(request: Request, data: AdvanceInput):
        service, store, settings = workspace(request, "operate")
        return service.advance(data.minutes)

    @app.post("/api/demo/reset")
    def reset(request: Request):
        service, store, settings = workspace(request, "operate")
        return service.reset()

    @app.post("/api/demo/scale")
    def scale(request: Request, data: ScaleInput):
        service, store, settings = workspace(request, "operate")
        return service.scale(data.n)

    @app.post("/api/demo/replay")
    def replay(request: Request):
        service, store, settings = workspace(request, "operate")
        return service.replay()

    @app.get("/api/logs")
    def logs(request: Request, outcome: str | None = None, actor: str | None = None, job_id: str | None = None, all_runs: bool = False, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        with store.lock:
            entries = store.logs(None if all_runs else store.get("run_id"))
            return [e for e in entries if (not outcome or e["outcome"] == outcome)
                    and (not actor or e["actor"] == actor) and (not job_id or e["job_id"] == job_id) and (not project or e.get("project", "default") == project)]

    @app.get("/api/logs/{decision_id}/evidence")
    def evidence(request: Request, decision_id: int):
        service, store, settings = workspace(request, "view")
        with store.lock:
            ev = store.evidence(decision_id)
            if request.state.assigned_project and ev.get("project", "default") != request.state.assigned_project:
                raise HTTPException(403, "Access denied to this evidence")
            return {**ev, "scope": store.get("scope")}

    @app.get("/api/analysis/flexibility")
    def flexibility(request: Request, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        return service.sensitivity(project)

    @app.get("/api/report")
    def report(request: Request, project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        return service.report(project)

    @app.get("/api/report/export")
    def export(request: Request, format: str = "json", scope: str = "current", project: str | None = None):
        service, store, settings = workspace(request, "view")
        if request.state.assigned_project:
            project = request.state.assigned_project
        if format not in ("json", "csv") or scope not in ("current", "replay"):
            raise HTTPException(422, "Use format=json|csv and scope=current|replay")
        with store.lock:
            data = store.get("replay") if scope == "replay" else service.report(project)
        if data is None:
            raise Conflict("Run the seven-day replay first")
        if request.state.assigned_project and scope == "replay":
            data = dict(data)
            data["rows"] = [r for r in data["rows"] if r.get("project", "default") == request.state.assigned_project]
        if format == "json":
            return Response(json.dumps(data, indent=2), media_type="application/json",
                            headers={"Content-Disposition": f'attachment; filename="sci-{scope}.json"'})
        output = io.StringIO(newline="")
        fields = ["tenant_id", "project_id", "environment_id", "job_id", "name", "project", "team", "zone", "status", "source", "workload_source", "included", "energy_kwh", "embodied_g", "functional_unit",
                  "baseline_start", "scheduled_start", "baseline_g", "scheduled_g", "avoided_g", "baseline_feasible"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in data["rows"]:
            # Spreadsheet applications must not execute names/comments as formulas.
            writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for k, v in row.items()})
        return Response(output.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="sci-{scope}.csv"'})

    return app


app = create_app()
