import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import Settings, ZONES
from app.models import AdvanceInput, ApprovalInput, JobInput, ScaleInput
from app.service import Conflict, SchedulerService
from app.store.sqlite import Store

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
    store = Store(settings.database_path)
    service = SchedulerService(settings, store)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        store.db.close()

    app = FastAPI(title="Verdant · Carbon-Aware Batch Scheduler", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.service = service
    app.mount("/static", StaticFiles(directory=UI), name="static")

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path in ("/", "/docs") or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request: Request, exc: Conflict):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing_handler(request: Request, exc: KeyError):
        return JSONResponse({"detail": "Job not found"}, status_code=404)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(UI / "index.html")

    @app.get("/docs", include_in_schema=False)
    def api_docs():
        return FileResponse(UI / "api.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "demo", "version": "1.0.0"}

    @app.get("/api/state")
    def state(project: str | None = None):
        with store.lock:
            all_jobs = store.jobs()
            jobs = [j for j in all_jobs if not project or j.project == project]
            return {"clock": service.now, "run_id": store.get("run_id"), "zones": ZONES,
                    "projects": sorted({j.project for j in all_jobs}), "selected_project": project,
                    "jobs": jobs, "report": service.report_for(jobs), "replay": store.get("replay"),
                    "pending_approvals": sum(j.status == "needs_approval" for j in jobs),
                    "config": {"pue": settings.pue, "safety_min": settings.safety_min,
                               "threshold_pct": settings.threshold_pct, "threshold_g": settings.threshold_g,
                               "embodied_g": settings.embodied_g, "llm_enabled": settings.enable_llm}}

    @app.get("/api/jobs")
    def jobs(project: str | None = None):
        with store.lock:
            return [j for j in store.jobs() if not project or j.project == project]

    @app.post("/api/jobs", status_code=201)
    def add_job(data: JobInput):
        return service.add(data)

    @app.get("/api/jobs/{job_id}/curve")
    def curve(job_id: str):
        with store.lock:
            job = service._job(job_id)
            if job.decision:
                return store.curve(job.decision)
            return service.curve_for(job)

    @app.post("/api/agent/cycle")
    def cycle():
        return service.cycle()

    @app.get("/api/approvals")
    def approvals(project: str | None = None):
        with store.lock:
            return [j for j in store.jobs() if j.status == "needs_approval" and (not project or j.project == project)]

    @app.post("/api/approvals/{job_id}")
    def review(job_id: str, data: ApprovalInput):
        return service.review(job_id, data.action, data.comment, data.approver_name)

    @app.post("/api/clock/advance")
    def advance(data: AdvanceInput):
        return service.advance(data.minutes)

    @app.post("/api/demo/reset")
    def reset():
        return service.reset()

    @app.post("/api/demo/scale")
    def scale(data: ScaleInput):
        return service.scale(data.n)

    @app.post("/api/demo/replay")
    def replay():
        return service.replay()

    @app.get("/api/logs")
    def logs(outcome: str | None = None, actor: str | None = None, job_id: str | None = None, all_runs: bool = False, project: str | None = None):
        with store.lock:
            entries = store.logs(None if all_runs else store.get("run_id"))
            return [e for e in entries if (not outcome or e["outcome"] == outcome)
                    and (not actor or e["actor"] == actor) and (not job_id or e["job_id"] == job_id) and (not project or e.get("project", "default") == project)]

    @app.get("/api/logs/{decision_id}/evidence")
    def evidence(decision_id: int):
        with store.lock:
            return store.evidence(decision_id)

    @app.get("/api/analysis/flexibility")
    def flexibility(project: str | None = None):
        return service.sensitivity(project)

    @app.get("/api/report")
    def report(project: str | None = None):
        return service.report(project)

    @app.get("/api/report/export")
    def export(format: str = "json", scope: str = "current", project: str | None = None):
        if format not in ("json", "csv") or scope not in ("current", "replay"):
            raise HTTPException(422, "Use format=json|csv and scope=current|replay")
        with store.lock:
            data = store.get("replay") if scope == "replay" else service.report(project)
        if data is None:
            raise Conflict("Run the seven-day replay first")
        if format == "json":
            return Response(json.dumps(data, indent=2), media_type="application/json",
                            headers={"Content-Disposition": f'attachment; filename="sci-{scope}.json"'})
        output = io.StringIO(newline="")
        fields = ["job_id", "name", "project", "team", "zone", "status", "source", "workload_source", "included", "energy_kwh", "embodied_g", "functional_unit",
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
