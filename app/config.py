"""Validated environment configuration; secrets are never serialized to the UI."""
import os
import math
from dataclasses import dataclass
from zoneinfo import ZoneInfo

ZONES = {"DE": "Europe/Berlin", "US-CAL-CISO": "America/Los_Angeles", "IN-WE": "Asia/Kolkata"}


def local_zone(zone: str) -> ZoneInfo:
    return ZoneInfo(ZONES[zone])


@dataclass(frozen=True)
class Settings:
    database_path: str = "data/carbon.db"
    pue: float = 1.4
    embodied_g: float = 0.0
    threshold_pct: float = 5.0
    threshold_g: float = 5.0
    safety_min: int = 15
    seed: int = 42
    electricity_token: str = ""
    timeout: float = 3.0
    retries: int = 1
    cache_seconds: int = 300
    enable_llm: bool = False
    openai_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    def __post_init__(self) -> None:
        finite = all(math.isfinite(v) for v in (self.pue, self.embodied_g, self.threshold_pct, self.threshold_g, self.timeout))
        if not (finite and 1 <= self.pue <= 5 and self.embodied_g >= 0 and 0 <= self.threshold_pct <= 100
                and self.threshold_g >= 0 and 0 <= self.safety_min <= 240
                and 0 < self.timeout <= 30 and 0 <= self.retries <= 3 and self.cache_seconds > 0):
            raise ValueError("Invalid scheduler configuration")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(database_path=os.getenv("DATABASE_PATH", "data/carbon.db"),
                   pue=float(os.getenv("PUE", "1.4")), embodied_g=float(os.getenv("EMBODIED_G_PER_RUN", "0")),
                   threshold_pct=float(os.getenv("SAVINGS_THRESHOLD_PCT", "5")),
                   threshold_g=float(os.getenv("SAVINGS_THRESHOLD_G", "5")),
                   safety_min=int(os.getenv("SAFETY_BUFFER_MIN", "15")), seed=int(os.getenv("SYNTHETIC_SEED", "42")),
                   electricity_token=os.getenv("ELECTRICITY_MAPS_TOKEN", ""),
                   timeout=float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "3")),
                   retries=int(os.getenv("PROVIDER_RETRIES", "1")), cache_seconds=int(os.getenv("PROVIDER_CACHE_SECONDS", "300")),
                   enable_llm=os.getenv("ENABLE_LLM_EXPLANATIONS", "false").lower() == "true",
                   openai_key=os.getenv("OPENAI_API_KEY", ""), openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
