from datetime import datetime, timedelta, timezone

from app.config import local_zone
from app.models import Job, JobInput, baseline_for

DEMO_START = datetime(2026, 10, 9, 0, 0, tzinfo=timezone.utc)
NAMES = ["Warehouse refresh", "Feature store sync", "Demand forecast training", "Daily revenue report",
         "Customer segmentation", "Inventory reconciliation", "Clickstream aggregation", "Fraud model retraining",
         "Partner usage report", "Search index rebuild", "Churn model training", "Billing reconciliation",
         "Product analytics rollup", "Document embeddings", "Executive scorecard", "Data quality scan",
         "Recommendation training", "Regional sales report", "Event lake compaction", "Compliance export",
         "Orders · extract", "Orders · transform", "Orders · publish", "Archive compression", "Urgent oversized backfill"]


def seed_jobs(now: datetime = DEMO_START, prefix: str = "demo", day: int = 0, zone_override: str | None = None) -> list[Job]:
    jobs = []
    zones = ["DE", "US-CAL-CISO", "IN-WE"]
    for i, name in enumerate(NAMES):
        zone = zone_override or ("DE" if 20 <= i <= 22 else zones[i % 3])
        local = now.astimezone(local_zone(zone)).replace(hour=6 + i % 3, minute=0, second=0, microsecond=0)
        if local < now:
            local += timedelta(days=1)
        start = local.astimezone(timezone.utc)
        duration = [45, 60, 90, 120, 180][(i + day) % 5]
        deadline = (local.replace(hour=23) + timedelta(hours=5)).astimezone(timezone.utc)
        if i == 24:
            deadline = start + timedelta(minutes=30)
            duration = 180
        criticality = "business_critical" if i in (3, 11, 19) else "hard_deadline" if i in (8, 14, 17) else "flexible"
        job_type = ("ml_training" if any(word in name.lower() for word in ("training", "forecast", "embeddings", "segmentation"))
                    else "report" if any(word in name.lower() for word in ("report", "scorecard", "export")) else "etl")
        data = JobInput(name=name, type=job_type,
                        owner={"etl": "Data Platform", "ml_training": "ML Ops", "report": "Business Insights"}[job_type], zone=zone,
                        est_duration_min=duration, power_kw=round([1.8, 12, 0.7, 4.5, 8][i % 5] * (1 + day * .03), 2),
                        earliest_start=start, sla_deadline=deadline, criticality=criticality,
                        depends_on=[f"{prefix}-{i:02}"] if i in (21, 22) else [])
        jobs.append(Job(**data.model_dump(), id=f"{prefix}-{i + 1:02}", baseline_start=baseline_for(data)))
    return jobs
