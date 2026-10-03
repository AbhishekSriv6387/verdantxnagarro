from datetime import timedelta

import pytest

from app.config import Settings
from app.engine.scheduler import ceil_slot, decide, energy_kwh, sci
from app.models import JobInput, baseline_for
from app.providers.carbon import Curve
from app.seed import seed_jobs
from conftest import NOW, make_curve


def test_energy_sci_and_embodied_delta():
    energy = energy_kwh(10, 90, 1.4)
    assert energy == 21
    assert sci(energy, 400, 20) == 8420
    assert sci(energy, 400, 20) - sci(energy, 100, 20) == 6300
    assert sci(energy, 400, 20, 2) == 4210
    with pytest.raises(ValueError):
        sci(1, 1, runs=0)


def test_weighted_partial_intervals():
    curve = make_curve()
    mean, values = curve.integrate(NOW + timedelta(hours=7, minutes=45), NOW + timedelta(hours=8, minutes=45))
    assert mean == 175  # 15 minutes at 400; 45 at 100.
    assert len(values) == 3


def test_curve_rejects_gaps_and_overlap():
    curve = make_curve()
    curve.points.pop(1)
    with pytest.raises(ValueError):
        curve.integrate(NOW, NOW + timedelta(hours=2))
    curve = make_curve()
    curve.points.append(curve.points[0])
    with pytest.raises(ValueError):
        curve.integrate(NOW, NOW + timedelta(hours=2))


def test_lowest_carbon_slot_and_stable_tie(job, settings):
    d = decide(job, [job], NOW, make_curve(), settings)
    assert d["outcome"] == "AUTO_RESCHEDULED"
    assert d["chosen_start"] == (NOW + timedelta(hours=8)).isoformat()
    assert d["energy_kwh"] == pytest.approx(2.8)
    assert d["avoided_g"] == pytest.approx(840)
    assert d["sla_margin_min"] >= settings.safety_min
    assert d == decide(job, [job], NOW, make_curve(), settings)


@pytest.mark.parametrize("criticality", ["hard_deadline", "business_critical"])
def test_never_auto_moves_protected(job, settings, criticality):
    job.criticality = criticality
    d = decide(job, [job], NOW, make_curve(), settings)
    assert d["outcome"] == "NEEDS_APPROVAL"
    assert "HUMAN_FOR_CRITICAL_OR_DEPENDENCY" in d["rule_ids"]
    assert job.scheduled_start is None


def test_parent_and_child_require_human(job, settings):
    child = job.model_copy(deep=True)
    child.id = "child"
    child.depends_on = [job.id]
    assert decide(job, [job, child], NOW, make_curve(), settings)["outcome"] == "NEEDS_APPROVAL"
    assert decide(child, [job, child], NOW, make_curve(), settings)["outcome"] == "NO_FEASIBLE_WINDOW"
    job.status, job.scheduled_start = "approved", NOW + timedelta(hours=8)
    d = decide(child, [job, child], NOW, make_curve(), settings)
    assert d["outcome"] == "NEEDS_APPROVAL"
    assert d["chosen_start"] == (NOW + timedelta(hours=9)).isoformat()


@pytest.mark.parametrize("clean,threshold_g,threshold_pct,outcome", [
    (390, 5, 5, "KEEP_NOW"), (100, 1000, 5, "KEEP_NOW"), (100, 5, 80, "KEEP_NOW"),
    (380, 56, 5, "AUTO_RESCHEDULED"), (400, 5, 5, "KEEP_NOW")])
def test_both_savings_thresholds(job, clean, threshold_g, threshold_pct, outcome):
    d = decide(job, [job], NOW, make_curve(clean), Settings(threshold_g=threshold_g, threshold_pct=threshold_pct))
    assert d["outcome"] == outcome
    if outcome == "KEEP_NOW":
        assert d["chosen_start"] == job.baseline_start.isoformat()
        assert d["avoided_g"] == 0


@pytest.mark.parametrize("duration", [1, 29, 30, 45, 60, 90, 180, 720])
@pytest.mark.parametrize("hours", [1, 3, 12, 20])
def test_sla_invariant_over_many_windows(job, settings, duration, hours):
    job.est_duration_min = duration
    job.sla_deadline = job.earliest_start + timedelta(hours=hours)
    d = decide(job, [job], NOW, make_curve(), settings)
    if d["chosen_start"]:
        from datetime import datetime
        chosen = datetime.fromisoformat(d["chosen_start"])
        assert chosen >= job.earliest_start
        assert chosen + job.duration + timedelta(minutes=settings.safety_min) <= job.sla_deadline
    else:
        assert d["outcome"] == "NO_FEASIBLE_WINDOW"


def test_impossible_job_and_expired_baseline(job, settings):
    job.sla_deadline = job.earliest_start + timedelta(minutes=30)
    assert decide(job, [job], NOW, make_curve(), settings)["chosen_start"] is None
    job.sla_deadline = NOW + timedelta(hours=22)
    d = decide(job, [job], NOW + timedelta(hours=13), make_curve(), settings)
    assert d["outcome"] == "NEEDS_APPROVAL"
    assert "BASELINE_INVALID_REQUIRES_REVIEW" in d["rule_ids"]


def test_rounds_up_and_preserves_seconds_guardrail():
    assert ceil_slot(NOW + timedelta(minutes=30)) == NOW + timedelta(minutes=30)
    assert ceil_slot(NOW + timedelta(minutes=30, seconds=1)) == NOW + timedelta(hours=1)


@pytest.mark.parametrize("zone", ["DE", "US-CAL-CISO", "IN-WE"])
def test_baseline_is_zone_local_14(zone):
    from app.config import local_zone
    data = JobInput(name="Test", owner="Test", zone=zone, est_duration_min=60, power_kw=1,
                    earliest_start=NOW, sla_deadline=NOW + timedelta(hours=24))
    assert baseline_for(data).astimezone(local_zone(zone)).hour == 14


def test_seed_variety():
    jobs = seed_jobs()
    assert len(jobs) == 25
    assert len({j.zone for j in jobs}) == 3
    assert len({j.criticality for j in jobs}) == 3
    assert sum(bool(j.depends_on) for j in jobs) == 2
