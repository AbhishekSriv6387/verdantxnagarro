from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import Settings
from app.models import Job, JobInput, baseline_for
from app.providers.carbon import Curve, Point

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@pytest.fixture
def settings():
    return Settings(database_path=":memory:")


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setenv("VERDANT_ADMIN_PASSWORD", "offline-test-password")
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/auth/login", json={"username": "admin", "password": "offline-test-password"}).status_code == 200
        yield client


@pytest.fixture
def job():
    data = JobInput(name="Example ETL", owner="Platform", zone="DE", est_duration_min=60,
                    power_kw=2, earliest_start=NOW + timedelta(hours=6), sla_deadline=NOW + timedelta(hours=22))
    return Job(**data.model_dump(), id="test-job", baseline_start=baseline_for(data))


def make_curve(clean: float = 100, dirty: float = 400) -> Curve:
    points = []
    for i in range(96):
        ts = NOW + timedelta(minutes=i * 30)
        points.append(Point(start=ts, end=ts + timedelta(minutes=30),
                            intensity=clean if 8 <= ts.hour < 10 else dirty,
                            source="SIMULATED", kind="test"))
    return Curve(zone="DE", source="SIMULATED", provider="Test curve", reason="Known test fixture", points=points)
