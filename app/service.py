"""Transactional orchestration. Only this layer applies an engine decision."""
import copy
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config import Settings
from app.engine.explanations import Explainer, OpenAIExplainer
from app.engine.scheduler import decide, is_feasible
from app.models import Job, JobInput, baseline_for
from app.providers.carbon import CarbonProvider, Curve, FallbackProvider, SyntheticProvider
from app.seed import DEMO_START, seed_jobs
from app.store.sqlite import Store

logger = logging.getLogger(__name__)


class Conflict(ValueError):
    pass


class SchedulerService:
    def __init__(self, settings: Settings, store: Store, provider: CarbonProvider | None = None,
                 explainer: Explainer | None = None):
        self.settings, self.store = settings, store
        self.provider = provider or FallbackProvider(settings)
        self.explainer = explainer or OpenAIExplainer(settings)
        with store.lock:
            if not store.get("clock"):
                self.reset()

    @property
    def now(self) -> datetime:
        return datetime.fromisoformat(self.store.get("clock"))

    def reset(self) -> dict:
        with self.store.transaction():
            self.store.db.execute("DELETE FROM jobs")
            self.store.set("clock", DEMO_START.isoformat())
            self.store.set("run_id", str(uuid4()))
            self.store.set("replay", None)
            for job in seed_jobs():
                self.store.save(job)
        return {"clock": DEMO_START.isoformat(), "jobs": 25, "audit_history_preserved": True}

    def _job(self, job_id: str) -> Job:
        job = next((j for j in self.store.jobs() if j.id == job_id), None)
        if not job:
            raise KeyError("Job not found")
        return job

    def curve_for(self, job: Job) -> Curve:
        start = min(job.earliest_start, job.baseline_start)
        end = max(job.sla_deadline, job.baseline_start + job.duration)
        return self.provider.curve(job.zone, start, end)

    def _log(self, job: Job, decision: dict, actor: str, comment: str | None = None) -> None:
        entry = {**decision, "timestamp": self.now.isoformat(),
                 "recorded_at": datetime.now(timezone.utc).isoformat(), "run_id": self.store.get("run_id"),
                 "job_id": job.id, "job_name": job.name, "actor": actor, "comment": comment}
        self.store.append(entry)
        logger.info("scheduling_decision", extra={"job_id": job.id, "outcome": decision["outcome"], "actor": actor})

    def cycle(self) -> dict:
        changed = []
        with self.store.transaction():
            jobs = self.store.jobs()
            now = self.now
            for job in jobs:
                if job.status != "pending":
                    continue
                related = [(j.id, j.status, str(j.scheduled_start)) for j in jobs
                           if j.id in job.depends_on or job.id in j.depends_on]
                fingerprint = hashlib.sha256(json.dumps([now.isoformat(), related]).encode()).hexdigest()
                if job.fingerprint == fingerprint:
                    continue
                decision = decide(job, jobs, now, self.curve_for(job), self.settings)
                # A plug-in receives a detached copy and can only add optional prose.
                try:
                    narrative = self.explainer.explain(copy.deepcopy(decision))
                except Exception:
                    narrative = None
                if narrative and isinstance(narrative, str):
                    decision["llm_explanation"] = narrative[:1500]
                outcome = decision["outcome"]
                chosen = datetime.fromisoformat(decision["chosen_start"]) if decision["chosen_start"] else None
                if outcome in ("AUTO_RESCHEDULED", "KEEP_NOW"):
                    if chosen is None or not is_feasible(job, chosen, now, self.settings, jobs):
                        raise Conflict("Refusing an infeasible schedule")
                    if outcome == "AUTO_RESCHEDULED" and (job.criticality != "flexible" or job.depends_on
                            or any(job.id in j.depends_on for j in jobs)):
                        raise Conflict("Protected job requires human approval")
                    job.scheduled_start, job.status = chosen, "scheduled"
                elif outcome == "NEEDS_APPROVAL":
                    job.proposal_start, job.status = chosen, "needs_approval"
                job.decision, job.fingerprint = decision, fingerprint
                self.store.save(job)
                self._log(job, decision, "agent")
                changed.append({"job_id": job.id, "outcome": outcome, "source": decision["source"]})
        return {"processed": len(changed), "decisions": changed}

    def review(self, job_id: str, action: str, comment: str) -> Job:
        with self.store.transaction():
            job = self._job(job_id)
            if job.status != "needs_approval" or not job.decision or not job.proposal_start:
                raise Conflict("This proposal is no longer pending")
            decision = copy.deepcopy(job.decision)
            if action == "approve":
                if not is_feasible(job, job.proposal_start, self.now, self.settings, self.store.jobs()):
                    raise Conflict("Proposal expired or dependencies changed. Reject it and submit a new job/window.")
                job.scheduled_start, job.status = job.proposal_start, "approved"
                decision["outcome"] = "APPROVED"
                decision["rule_ids"].append("HUMAN_APPROVAL_REVALIDATED")
                decision["explanation"] = "Human approved the frozen proposal after deadline, current-time and dependency validation."
            else:
                job.status = "rejected"
                job.scheduled_start = None
                decision["outcome"] = "REJECTED"
                decision["rule_ids"].append("HUMAN_REJECTION_NO_DISPATCH")
                decision["explanation"] = "Human rejected this proposal; no job is dispatched and no savings are credited."
            job.decision = decision
            self.store.save(job)
            self._log(job, decision, "human", comment)
        return job

    def add(self, data: JobInput) -> Job:
        with self.store.transaction():
            if data.sla_deadline <= self.now or data.earliest_start > self.now + timedelta(days=7):
                raise Conflict("Use a future deadline and an earliest start within 7 days of the simulated clock")
            existing = {j.id: j for j in self.store.jobs()}
            if any(parent not in existing for parent in data.depends_on):
                raise Conflict("Every dependency must reference an existing job")
            # The API only creates new IDs and dependencies point backward, so cycles cannot be introduced.
            job = Job(**data.model_dump(), id=str(uuid4()), baseline_start=baseline_for(data))
            self.store.save(job)
        return job

    def advance(self, minutes: int) -> dict:
        completed = 0
        with self.store.transaction():
            now = self.now + timedelta(minutes=minutes)
            self.store.set("clock", now.isoformat())
            for job in self.store.jobs():
                if job.status in ("scheduled", "approved") and job.scheduled_start and job.scheduled_start + job.duration <= now:
                    job.status = "completed"
                    self.store.save(job)
                    self._log(job, {**(job.decision or {}), "outcome": "COMPLETED",
                                   "explanation": "Simulated run completed; carbon remains an estimate, not measured telemetry."}, "agent")
                    completed += 1
        return {"clock": now.isoformat(), "completed": completed, "mode": "SIMULATED"}

    @staticmethod
    def report_for(jobs: list[Job]) -> dict:
        rows = []
        for job in jobs:
            d = job.decision
            if not d:
                continue
            applied = job.status in ("scheduled", "approved", "completed") and job.scheduled_start is not None
            rows.append({"job_id": job.id, "name": job.name, "zone": job.zone, "status": job.status,
                         "source": d["source"], "included": applied, "energy_kwh": d["energy_kwh"],
                         "embodied_g": d["embodied_g"], "functional_unit": "one job run",
                         "baseline_start": job.baseline_start.isoformat(),
                         "scheduled_start": job.scheduled_start.isoformat() if job.scheduled_start else None,
                         "baseline_g": d["carbon_before_g"],
                         "scheduled_g": d["carbon_after_g"] if applied else None,
                         "avoided_g": d["avoided_g"] if applied else 0.0,
                         "baseline_feasible": d.get("baseline_feasible", False)})
        included = [r for r in rows if r["included"]]
        baseline = sum(r["baseline_g"] for r in included)
        after = sum(r["scheduled_g"] for r in included)
        labels = sorted({r["source"] for r in rows})
        return {"source": " + ".join(labels) if labels else "SIMULATED", "sources": labels,
                "accounting": "Modeled SCI estimates for applied schedules; not verified avoided emissions",
                "functional_unit": "one job run", "baseline_g": baseline, "scheduled_g": after,
                "avoided_g": baseline - after, "reduction_pct": (baseline - after) * 100 / baseline if baseline else 0,
                "projected_weekly_g": (baseline - after) * 7, "projection_assumption": "Repeat this applied workload once daily for seven days",
                "included_jobs": len(included), "total_jobs": len(jobs),
                "excluded_jobs": len(jobs) - len(included), "rows": rows}

    def report(self) -> dict:
        with self.store.lock:
            return self.report_for(self.store.jobs())

    def replay(self) -> dict:
        """Separate seeded experiment: never changes the active clock, jobs, or approvals."""
        days = []
        rows = []
        synthetic = SyntheticProvider(self.settings.seed)
        for day in range(7):
            now = DEMO_START + timedelta(days=day)
            jobs = seed_jobs(now, prefix=f"week-{day + 1}", day=day)
            for job in jobs:
                curve = synthetic.curve(job.zone, min(job.earliest_start, job.baseline_start),
                                        max(job.sla_deadline, job.baseline_start + job.duration))
                decision = decide(job, jobs, now, curve, self.settings)
                job.decision = decision
                if decision["outcome"] in ("AUTO_RESCHEDULED", "KEEP_NOW"):
                    job.scheduled_start = datetime.fromisoformat(decision["chosen_start"])
                    job.status = "completed"
                elif decision["outcome"] == "NEEDS_APPROVAL":
                    job.status = "needs_approval"
            report = self.report_for(jobs)
            days.append({"date": now.date().isoformat(), "source": "SIMULATED",
                         **{key: report[key] for key in ("avoided_g", "baseline_g", "scheduled_g", "included_jobs", "excluded_jobs")}})
            rows.extend(report["rows"])
        before, after = sum(d["baseline_g"] for d in days), sum(d["scheduled_g"] for d in days)
        result = {"source": "SIMULATED", "seed": self.settings.seed, "total_jobs": 175, "days": days,
                  "baseline_g": before, "scheduled_g": after, "avoided_g": before - after,
                  "reduction_pct": (before - after) * 100 / before if before else 0,
                  "included_jobs": sum(d["included_jobs"] for d in days),
                  "assumption": "Seven seeded daily workloads; only automatically applied schedules count. No simulated human approvals.",
                  "rows": rows}
        with self.store.transaction():
            self.store.set("replay", result)
        return result
