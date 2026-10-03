from datetime import timedelta

import httpx
import pytest

from app.config import Settings
from app.providers.carbon import ElectricityMapsProvider, FallbackProvider, SyntheticProvider
from conftest import NOW


def test_seeded_synthetic_reproducible_diurnal():
    provider = SyntheticProvider(42)
    curve = provider.curve("DE", NOW, NOW + timedelta(hours=48))
    assert curve == provider.curve("DE", NOW, NOW + timedelta(hours=48))
    assert len(curve.points) == 96
    assert all(p.source == "SIMULATED" for p in curve.points)
    assert curve.integrate(NOW + timedelta(hours=9), NOW + timedelta(hours=10))[0] < curve.integrate(NOW + timedelta(hours=17), NOW + timedelta(hours=18))[0]
    assert curve != SyntheticProvider(43).curve("DE", NOW, NOW + timedelta(hours=48))


@pytest.mark.parametrize("failure", ["timeout", "503", "403", "invalid", "partial", "nan", "list"])
def test_api_failure_falls_back(failure):
    calls = []
    def handle(req):
        calls.append(req)
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout")
        if failure in ("503", "403"):
            return httpx.Response(int(failure))
        if failure == "invalid":
            return httpx.Response(200, text="not json")
        if failure == "list":
            return httpx.Response(200, json=[])
        if failure == "nan":
            return httpx.Response(200, json={"datetime": NOW.isoformat(), "carbonIntensity": "NaN"})
        return httpx.Response(200, json={"zone": "DE", "forecast": []})
    settings = Settings(electricity_token="test-token", retries=1)
    live = ElectricityMapsProvider(settings, httpx.MockTransport(handle))
    curve = FallbackProvider(settings, live).curve("DE", NOW, NOW + timedelta(hours=24))
    assert curve.source == "SIMULATED"
    assert curve.integrate(NOW, NOW + timedelta(hours=24))[0] > 0
    assert calls[0].headers["auth-token"] == "test-token"
    if failure in ("timeout", "503", "403", "invalid"):
        assert len(calls) == 6


def test_missing_token_never_calls_live():
    class Forbidden:
        def curve(self, *args):
            raise AssertionError("No network without a token")
    assert FallbackProvider(Settings(), Forbidden()).curve("DE", NOW, NOW + timedelta(hours=24)).source == "SIMULATED"


def test_live_full_coverage_and_cache():
    calls = []
    def handle(req):
        calls.append(req)
        endpoint = req.url.path.split("/")[-1]
        row = lambda i: {"datetime": (NOW + timedelta(hours=i)).isoformat(), "carbonIntensity": 200 + i}
        payload = {"zone": "DE", **row(0)} if endpoint == "latest" else {"zone": "DE", endpoint: [row(i) for i in range(48)] if endpoint == "forecast" else []}
        return httpx.Response(200, json=payload)
    settings = Settings(electricity_token="test", retries=0)
    provider = FallbackProvider(settings, ElectricityMapsProvider(settings, httpx.MockTransport(handle)))
    first = provider.curve("DE", NOW, NOW + timedelta(hours=24))
    assert first.source == "LIVE"
    assert first.integrate(NOW, NOW + timedelta(hours=2))[0] == 200.5
    assert provider.curve("DE", NOW, NOW + timedelta(hours=24)) == first
    assert len(calls) == 3
    assert calls[0].url.params["horizonHours"] == "48"
