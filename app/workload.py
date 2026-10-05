"""Seeded illustrative workload distributions, not customer telemetry."""
import random
from datetime import datetime, timedelta

from app.models import Job, JobInput, baseline_for


def generate_jobs(now: datetime, n: int = 25, seed: int = 42, zone_override: str | None = None) -> list[Job]:
    rng = random.Random(seed)
    jobs = []
    for i in range(n):
        zone = zone_override or rng.choice(["DE", "US-CAL-CISO", "IN-WE", "GB"])
        kind = rng.choices(["etl", "report", "ml_training"], [60, 25, 15])[0]
        duration = rng.choice({"etl": [30, 45, 60, 90, 120], "report": [15, 30, 45, 60],
                               "ml_training": [120, 180, 240, 360]}[kind])
        power = round(rng.uniform(*{"etl": (1, 8), "report": (.3, 3), "ml_training": (8, 40)}[kind]), 2)
        earliest = now + timedelta(hours=rng.choice([1, 2, 4, 6]))
        deadline = earliest + timedelta(hours=rng.choice([18, 24, 30]))
        bucket = i % 100
        criticality = "flexible" if bucket < 70 else "hard_deadline" if bucket < 85 else "business_critical" if bucket < 95 else "flexible"
        # Distribute small samples across the same proportions.
        if n < 100:
            bucket = i * 100 // n
            criticality = "flexible" if bucket < 70 else "hard_deadline" if bucket < 85 else "business_critical" if bucket < 95 else "flexible"
        dependencies = []
        if i % 25 in (21, 22):
            dependencies = [f"scale-{i:03}"]
            zone = jobs[-1].zone
        if bucket >= 95:
            deadline = earliest + timedelta(minutes=15)
            duration = max(duration, 60)
        data = JobInput(name=f"SIMULATED WORKLOAD / {kind} {i+1}", owner="Demo workload generator",
                        project=["analytics", "commerce", "research"][i % 3], team={"etl": "Data Platform", "report": "Insights", "ml_training": "ML Ops"}[kind],
                        zone=zone, type=kind, est_duration_min=duration, power_kw=power,
                        earliest_start=earliest, sla_deadline=deadline, criticality=criticality, depends_on=dependencies)
        jobs.append(Job(**data.model_dump(), id=f"scale-{i+1:03}", baseline_start=baseline_for(data),
                        workload_source="SIMULATED WORKLOAD"))
    return jobs
