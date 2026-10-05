"""Pure deterministic scheduling rules. No database, network, or LLM authority."""
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.models import Job
from app.providers.carbon import Curve


def energy_kwh(power_kw: float, duration_min: int, pue: float) -> float:
    return power_kw * duration_min / 60 * pue


def sci(energy: float, intensity: float, embodied: float = 0, runs: int = 1) -> float:
    if runs <= 0:
        raise ValueError("Functional unit must be positive")
    return (energy * intensity + embodied) / runs


def ceil_slot(value: datetime) -> datetime:
    value = value.astimezone(timezone.utc)
    rounded = value.replace(minute=(value.minute // 30) * 30, second=0, microsecond=0)
    return rounded if rounded == value else rounded + timedelta(minutes=30)


class JobGraph(list[Job]):
    """A per-cycle index referencing the same mutable jobs; no stale state copies."""
    def __init__(self, jobs: list[Job]):
        super().__init__(jobs)
        self.index = {j.id: j for j in jobs}
        self.children = {j.id: [] for j in jobs}
        for j in jobs:
            for parent in j.depends_on:
                self.children.setdefault(parent, []).append(j.id)
        self.order = {j.id: i for i, j in enumerate(jobs)}

    def related(self, job: Job) -> list[Job]:
        ids = set(job.depends_on) | set(self.children.get(job.id, []))
        return [self.index[k] for k in sorted(ids, key=lambda k: self.order.get(k, -1)) if k in self.index]


def has_dependents(job: Job, jobs: list[Job]) -> bool:
    return bool(jobs.children.get(job.id)) if isinstance(jobs, JobGraph) else any(job.id in j.depends_on for j in jobs)


def dependency_floor(job: Job, jobs: list[Job]) -> datetime | None:
    index = jobs.index if isinstance(jobs, JobGraph) else {j.id: j for j in jobs}
    ends = [job.earliest_start]
    for parent_id in job.depends_on:
        parent = index.get(parent_id)
        if not parent or parent.status not in ("scheduled", "approved", "completed") or not parent.scheduled_start:
            return None
        ends.append(parent.scheduled_start + parent.duration)
    return max(ends)


def is_feasible(job: Job, start: datetime, now: datetime, settings: Settings, jobs: list[Job]) -> bool:
    floor = dependency_floor(job, jobs)
    return bool(floor is not None and start >= max(floor, now)
                and start + job.duration + timedelta(minutes=settings.safety_min) <= job.sla_deadline)


def decide(job: Job, jobs: list[Job], now: datetime, curve: Curve, settings: Settings) -> dict:
    energy = energy_kwh(job.power_kw, job.est_duration_min, settings.pue)
    before_i, before_values = curve.integrate(job.baseline_start, job.baseline_start + job.duration)
    before = sci(energy, before_i, settings.embodied_g)
    floor = dependency_floor(job, jobs)
    latest = job.sla_deadline - job.duration - timedelta(minutes=settings.safety_min)
    candidates = []
    if floor is not None:
        cursor = ceil_slot(max(job.earliest_start, now, floor))
        while cursor <= latest:
            intensity, _ = curve.integrate(cursor, cursor + job.duration, evidence=False)
            candidates.append({"start": cursor.isoformat(), "mean_intensity_g_kwh": intensity,
                               "carbon_g": sci(energy, intensity, settings.embodied_g), "source": curve.source})
            cursor += timedelta(minutes=30)
    result = {"outcome": "NO_FEASIBLE_WINDOW", "source": curve.source, "provider": curve.provider,
              "source_reason": curve.reason, "baseline_start": job.baseline_start.isoformat(),
              "curve_snapshot": curve.model_dump(mode="json"),
              "chosen_start": None, "energy_kwh": energy, "pue": settings.pue,
              "embodied_g": settings.embodied_g, "functional_unit": "one job run",
              "carbon_before_g": before, "carbon_after_g": None, "avoided_g": 0.0,
              "reduction_pct": 0.0, "sla_margin_min": None,
              "intensity_values_used": {"before": before_values, "after": []},
              "candidate_window_summary": {"count": len(candidates), "step_min": 30,
                  "first_start": candidates[0]["start"] if candidates else None,
                  "runtime_min": job.est_duration_min, "latest_start": latest.isoformat(), "safety_buffer_min": settings.safety_min,
                  "candidates": sorted(candidates, key=lambda c: (c["carbon_g"], c["start"]))[:3],
                  "retained": "Best three plus chosen; all starts reproducible from frozen curve"},
              "rule_ids": ["SLA_BUFFER", "NO_PAST_START", "DEPENDENCY_ORDER"],
              "thresholds": {"minimum_g": settings.threshold_g, "minimum_pct": settings.threshold_pct},
              "explanation": "No feasible start remains within the SLA and safety buffer."}
    if not candidates:
        result["rule_ids"].append("DEPENDENCY_UNRESOLVED" if floor is None else "NO_FEASIBLE_WINDOW")
        if floor is None:
            result["explanation"] = "Blocked until every prerequisite has an applied schedule. Resolve upstream approval, then run the agent again."
        return result
    best = min(candidates, key=lambda item: (item["carbon_g"], item["start"]))
    chosen = datetime.fromisoformat(best["start"])
    after = best["carbon_g"]
    savings = before - after
    pct = 100 * savings / before if before else 0
    baseline_valid = is_feasible(job, job.baseline_start, now, settings, jobs)
    protected = job.criticality != "flexible" or bool(job.depends_on) or has_dependents(job, jobs)
    qualifies = savings + 1e-9 >= settings.threshold_g and pct + 1e-9 >= settings.threshold_pct
    if chosen == job.baseline_start or (not qualifies and baseline_valid):
        chosen, after = job.baseline_start, before
        result.update(outcome="KEEP_NOW", explanation="Keep the fixed 14:00 baseline: a move does not meet both savings thresholds.")
        result["rule_ids"].append("MIN_SAVINGS_BOTH")
    elif protected or not baseline_valid:
        result.update(outcome="NEEDS_APPROVAL", explanation="A greener feasible window is proposed. Human approval is required by the protection rules.")
        if protected:
            result["rule_ids"].append("HUMAN_FOR_CRITICAL_OR_DEPENDENCY")
        if not baseline_valid:
            result["rule_ids"].append("BASELINE_INVALID_REQUIRES_REVIEW")
            result["explanation"] = "The 14:00 baseline is no longer feasible. Review this replacement; its carbon delta is a counterfactual, not a feasible alternative."
    else:
        result.update(outcome="AUTO_RESCHEDULED", explanation="Flexible, independent job moved to the lowest-carbon feasible slot; both savings thresholds passed.")
        result["rule_ids"].extend(["FLEXIBLE_ONLY", "MIN_SAVINGS_BOTH"])
    summary = result["candidate_window_summary"]["candidates"]
    chosen_candidate = next(c for c in candidates if c["start"] == chosen.isoformat())
    if chosen_candidate not in summary:
        summary.append(chosen_candidate)
    _, after_values = curve.integrate(chosen, chosen + job.duration)
    savings = before - after
    result.update(chosen_start=chosen.isoformat(), carbon_after_g=after, avoided_g=savings,
                  reduction_pct=100 * savings / before if before else 0,
                  sla_margin_min=(job.sla_deadline - chosen - job.duration).total_seconds() / 60,
                  baseline_feasible=baseline_valid)
    result["intensity_values_used"]["after"] = after_values
    result["explanation"] += f" Estimated delta {savings:.1f} g CO2e ({result['reduction_pct']:.1f}%); source {curve.source}."
    assert is_feasible(job, chosen, now, settings, jobs), "SLA guardrail invariant"
    assert result["outcome"] != "AUTO_RESCHEDULED" or not protected, "Human approval guardrail invariant"
    return result
