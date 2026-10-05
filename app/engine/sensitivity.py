"""Read-only flexibility scenarios, separate from applied savings accounting."""
from datetime import datetime, timedelta

from app.config import Settings
from app.engine.scheduler import JobGraph, decide, has_dependents, is_feasible
from app.models import Job
from app.providers.carbon import Curve


def sensitivity(jobs: list[Job], now: datetime, curves: dict[str, Curve], settings: Settings, project: str | None = None) -> dict:
    graph = JobGraph(jobs)
    points = []
    for hours in (1, 2, 4, 8):
        rows = []
        for job in jobs:
            if project and job.project != project:
                continue
            source = curves[job.id].source
            row = {"job_id": job.id, "source": source, "workload_source": job.workload_source,
                   "baseline_start": job.baseline_start.isoformat(), "modeled_saving_g": 0.0, "included": False}
            if job.criticality != "flexible" or job.depends_on or has_dependents(job, graph):
                row["excluded_reason"] = "Protected or dependency-linked; no hypothetical approvals"
            elif job.status == "rejected":
                row["excluded_reason"] = "Rejected workload"
            elif not is_feasible(job, job.baseline_start, now, settings, graph):
                row["excluded_reason"] = "Original baseline is not currently feasible"
            else:
                scenario = job.model_copy(deep=True)
                scenario.earliest_start = max(job.earliest_start, job.baseline_start - timedelta(hours=hours))
                scenario.sla_deadline = min(job.sla_deadline, job.baseline_start + timedelta(hours=hours)
                                            + job.duration + timedelta(minutes=settings.safety_min))
                # baseline_start stays the original 14:00 counterfactual, even across midnight.
                decision = decide(scenario, graph, now, curves[job.id], settings)
                row.update(included=decision["outcome"] in ("AUTO_RESCHEDULED", "KEEP_NOW"),
                           modeled_saving_g=decision["avoided_g"], outcome=decision["outcome"],
                           baseline_g=decision["carbon_before_g"], chosen_start=decision["chosen_start"])
            rows.append(row)
        included = [r for r in rows if r["included"]]
        before = sum(r["baseline_g"] for r in included)
        saving = sum(r["modeled_saving_g"] for r in included)
        points.append({"flexibility_hours": hours, "modeled_saving_g": saving,
                       "reduction_pct": saving * 100 / before if before else 0,
                       "included_jobs": len(included), "excluded_jobs": len(rows)-len(included), "rows": rows})
    return {"analysis": "HYPOTHETICAL FLEXIBILITY SENSITIVITY; not applied savings",
            "workload_source": "SIMULATED WORKLOAD", "source": " + ".join(sorted({curves[j.id].source for j in jobs if not project or j.project == project})),
            "baseline": "Original 14:00 local on each job's earliest-start date",
            "assumptions": "Symmetric start windows clipped to original earliest start, current clock and SLA including buffer. "
                           "Only independent flexible jobs with feasible baselines; rejected jobs excluded. "
                           "Unchanged dual thresholds. No approvals or schedules are applied.",
            "points": points}
