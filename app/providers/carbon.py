"""Complete, labeled carbon curves with time-weighted integration."""
import hashlib
import logging
import math
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, local_zone
from app.models import Source

logger = logging.getLogger(__name__)


class Point(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    start: datetime
    end: datetime
    intensity: float = Field(ge=0, le=3000)
    source: Source
    kind: str


class Curve(BaseModel):
    zone: str
    source: Source
    provider: str
    reason: str
    points: list[Point]

    def integrate(self, start: datetime, end: datetime, evidence: bool = True) -> tuple[float, list[dict]]:
        """Piecewise constant intensity, weighted by exact overlap seconds."""
        cursor = start
        weighted = 0.0
        used = []
        for p in sorted(self.points, key=lambda p: p.start):
            left, right = max(start, p.start), min(end, p.end)
            if right <= left:
                continue
            if left != cursor:
                raise ValueError("Carbon curve has gaps or overlapping intervals")
            seconds = (right - left).total_seconds()
            weighted += seconds * p.intensity
            if evidence:
                used.append({"start": left.isoformat(), "end": right.isoformat(),
                         "intensity_g_kwh": p.intensity, "source": p.source, "kind": p.kind})
            cursor = right
        if cursor != end or end <= start:
            raise ValueError("Carbon curve does not cover the full run")
        return weighted / (end - start).total_seconds(), used


class CarbonProvider(Protocol):
    def curve(self, zone: str, start: datetime, end: datetime) -> Curve: ...


class SyntheticProvider:
    def __init__(self, seed: int = 42):
        self.seed = seed

    def curve(self, zone: str, start: datetime, end: datetime) -> Curve:
        cursor = start.replace(minute=(start.minute // 30) * 30, second=0, microsecond=0)
        end = max(end, cursor + timedelta(hours=48))
        points = []
        base = {"DE": 350, "US-CAL-CISO": 260, "IN-WE": 620, "GB": 200}[zone]
        while cursor < end:
            local = cursor.astimezone(local_zone(zone))
            hour = local.hour + local.minute / 60
            salt = f"{self.seed}|{zone}|{cursor.astimezone(timezone.utc).isoformat()}"
            rng = random.Random(int(hashlib.sha256(salt.encode()).hexdigest()[:16], 16))
            solar = -0.46 * base * math.exp(-((hour - 11.5) / 2.5) ** 2)
            evening = 0.38 * base * math.exp(-((hour - 19) / 2.8) ** 2)
            night = -0.12 * base * math.exp(-((hour - 3) / 2.7) ** 2)
            intensity = round(max(30, base + solar + evening + night + rng.uniform(-12, 12)), 2)
            points.append(Point(start=cursor, end=cursor + timedelta(minutes=30),
                                intensity=intensity, source="SIMULATED", kind="synthetic"))
            cursor += timedelta(minutes=30)
        return Curve(zone=zone, source="SIMULATED", provider="Seeded diurnal model",
                     reason="Synthetic scenario; not a grid measurement", points=points)


class ElectricityMapsProvider:
    """V4 hourly history/latest/48h forecast; bounded retries and TTL cache."""
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self.cache: dict[str, tuple[float, list[Point]]] = {}

    def _request(self, client: httpx.Client, endpoint: str, zone: str) -> dict:
        params: dict = {"zone": zone, "temporalGranularity": "hourly"}
        if endpoint == "forecast":
            params["horizonHours"] = 48
        for attempt in range(self.settings.retries + 1):
            try:
                response = client.get(f"https://api.electricitymaps.com/v4/carbon-intensity/{endpoint}", params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Provider payload must be an object")
                return payload
            except (httpx.HTTPError, ValueError):
                if attempt == self.settings.retries:
                    raise
                time.sleep(0.1 * (2 ** attempt))
        raise RuntimeError("Unreachable")

    def curve(self, zone: str, start: datetime, end: datetime) -> Curve:
        cached = self.cache.get(zone)
        if cached and time.monotonic() - cached[0] < self.settings.cache_seconds:
            points = cached[1]
        else:
            indexed: dict[datetime, Point] = {}
            with httpx.Client(headers={"auth-token": self.settings.electricity_token},
                              timeout=self.settings.timeout, transport=self.transport) as client:
                for endpoint in ("forecast", "history", "latest"):
                    try:
                        payload = self._request(client, endpoint, zone)
                        if payload.get("zone", zone) != zone:
                            raise ValueError("Provider returned a different zone")
                        rows = [payload] if endpoint == "latest" else payload.get(endpoint, [])
                        for row in rows:
                            ts = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
                            if ts.utcoffset() is None:
                                raise ValueError("Provider timestamp has no timezone")
                            ts = ts.astimezone(timezone.utc)
                            # Latest is usable only at the hourly boundary; no inferred backward coverage.
                            if endpoint == "latest" and (ts.minute or ts.second or ts.microsecond):
                                continue
                            indexed[ts] = Point(start=ts, end=ts + timedelta(hours=1),
                                                intensity=row["carbonIntensity"], source="LIVE", kind=endpoint)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError):
                        logger.info("provider_endpoint_unavailable", extra={"endpoint": endpoint, "zone": zone})
            points = sorted(indexed.values(), key=lambda p: p.start)
            self.cache[zone] = (time.monotonic(), points)
        result = Curve(zone=zone, source="LIVE", provider="Electricity Maps v4",
                       reason="API-sourced estimates and forecasts, not measured job emissions", points=points)
        result.integrate(start, end)  # Do not extrapolate stale/latest readings into future hours.
        return result


class FallbackProvider:
    def __init__(self, settings: Settings, live: CarbonProvider | None = None):
        self.settings = settings
        from app.providers.additional import RecordedProvider, UKCarbonProvider
        self.live = live or (UKCarbonProvider(settings) if settings.carbon_provider == "uk" else
                             RecordedProvider(settings.recorded_path) if settings.carbon_provider == "recorded" else
                             ElectricityMapsProvider(settings))
        self.synthetic = SyntheticProvider(settings.seed)

    def curve(self, zone: str, start: datetime, end: datetime) -> Curve:
        reason = "Synthetic provider selected" if self.settings.carbon_provider == "synthetic" else "No Electricity Maps token configured"
        if self.settings.carbon_provider in ("uk", "recorded") or (self.settings.electricity_token and self.settings.carbon_provider != "synthetic"):
            try:
                curve = self.live.curve(zone, start, end)
                curve.integrate(start, end)
                return curve
            except (httpx.HTTPError, ValueError, KeyError, TypeError, OSError):
                reason = "Selected provider unavailable or full-window coverage missing"
                logger.info("provider_fallback", extra={"zone": zone})
        result = self.synthetic.curve(zone, start, end)
        result.reason = reason
        return result
