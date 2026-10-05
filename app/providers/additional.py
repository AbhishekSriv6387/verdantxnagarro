"""Public GB forecasts and timestamp-preserving recorded grid estimates."""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.config import Settings
from app.providers.carbon import Curve, Point


class UKCarbonProvider:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings, self.transport = settings, transport
        self.cache: dict[str, tuple[float, Curve]] = {}

    def curve(self, zone: str, start: datetime, end: datetime) -> Curve:
        if zone != "GB":
            raise ValueError("UK provider supports GB only")
        anchor = start.astimezone(timezone.utc).replace(minute=start.minute // 30 * 30, second=0, microsecond=0)
        key = anchor.strftime("%Y-%m-%dT%H:%MZ")
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < self.settings.cache_seconds:
            result = cached[1]
        else:
            with httpx.Client(timeout=self.settings.timeout, transport=self.transport) as client:
                for attempt in range(self.settings.retries + 1):
                    try:
                        response = client.get(f"https://api.carbonintensity.org.uk/intensity/{key}/fw48h")
                        response.raise_for_status()
                        rows = response.json()["data"]
                        points = []
                        for row in rows:
                            left = datetime.fromisoformat(row["from"].replace("Z", "+00:00"))
                            right = datetime.fromisoformat(row["to"].replace("Z", "+00:00"))
                            if left.utcoffset() is None or right.utcoffset() is None or right-left != timedelta(minutes=30):
                                raise ValueError("Expected aware half-hour intervals")
                            points.append(Point(start=left, end=right, intensity=row["intensity"]["forecast"],
                                                source="LIVE", kind="forecast"))
                        result = Curve(zone=zone, source="LIVE", provider="UK Carbon Intensity API / NESO",
                                       reason="API forecast estimates; not measured job emissions", points=points)
                        result.integrate(start, end)
                        self.cache[key] = (time.monotonic(), result)
                        break
                    except (httpx.HTTPError, ValueError, KeyError, TypeError):
                        if attempt == self.settings.retries:
                            raise
                        time.sleep(0.1 * 2 ** attempt)
        result.integrate(start, end)
        return result


class RecordedProvider:
    def __init__(self, path: str):
        self.path = Path(path)

    def curve(self, zone: str, start: datetime, end: datetime) -> Curve:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (data.get("format_version") != 1 or data.get("source") != "REAL (RECORDED)"
                or data.get("sample", False) or data.get("zone") != zone
                or not data.get("source_url") or not data.get("retrieved_at")):
            raise ValueError("Not a documented real recording for this zone")
        points = [Point.model_validate(p) for p in data["points"]]
        if any(p.source != "REAL (RECORDED)" or p.kind not in ("recorded_actual", "recorded_forecast")
               or p.start.utcoffset() is None or p.end.utcoffset() is None for p in points):
            raise ValueError("Invalid recorded provenance")
        result = Curve(zone=zone, source="REAL (RECORDED)", provider=data["provider"],
                       reason=f"Recorded grid estimates; original timestamps. {data['source_url']} (retrieved {data['retrieved_at']})",
                       points=points)
        result.integrate(start, end)
        return result
