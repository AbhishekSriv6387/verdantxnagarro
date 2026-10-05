from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import ZONES, local_zone

Source = Literal["LIVE", "SIMULATED", "REAL (RECORDED)"]
Status = Literal["pending", "scheduled", "needs_approval", "approved", "rejected", "completed"]
Outcome = Literal["AUTO_RESCHEDULED", "KEEP_NOW", "NEEDS_APPROVAL", "NO_FEASIBLE_WINDOW", "APPROVED", "REJECTED", "COMPLETED"]


class JobInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=120)
    type: Literal["etl", "ml_training", "report"] = "etl"
    owner: str = Field(min_length=1, max_length=100)
    project: str = Field(default="default", min_length=1, max_length=100)
    team: str = Field(default="default", min_length=1, max_length=100)
    zone: str = "DE"
    est_duration_min: int = Field(ge=1, le=720)
    power_kw: float = Field(gt=0, le=10000)
    earliest_start: datetime
    sla_deadline: datetime
    criticality: Literal["flexible", "hard_deadline", "business_critical"] = "flexible"
    depends_on: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name", "owner", "project", "team")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @field_validator("zone")
    @classmethod
    def supported_zone(cls, value: str) -> str:
        if value not in ZONES:
            raise ValueError(f"Choose a supported zone: {', '.join(ZONES)}")
        return value

    @field_validator("earliest_start", "sla_deadline")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include an explicit timezone offset")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def window(self) -> "JobInput":
        if not timedelta(0) < self.sla_deadline - self.earliest_start <= timedelta(hours=48):
            raise ValueError("Deadline must be after earliest start, within 48 hours")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Duplicate dependencies")
        return self


class Job(JobInput):
    id: str
    workload_source: str = "SIMULATED WORKLOAD"
    status: Status = "pending"
    baseline_start: datetime
    scheduled_start: datetime | None = None
    proposal_start: datetime | None = None
    decision: dict | None = None
    fingerprint: str | None = None

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.est_duration_min)


def baseline_for(job: JobInput) -> datetime:
    return job.earliest_start.astimezone(local_zone(job.zone)).replace(
        hour=14, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "reject"]
    approver_name: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=1000)

    @field_validator("comment", "approver_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A review comment is required")
        return value.strip()


class AdvanceInput(BaseModel):
    minutes: int = Field(default=60, ge=1, le=10080)


class ScaleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(default=25, ge=1, le=500)
