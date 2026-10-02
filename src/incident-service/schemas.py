"""
Pydantic schemas for the Incident Management Service.

These define the request/response contracts for the API and are kept
separate from the SQLAlchemy models (models.py) so the persistence layer
can evolve independently of the public API shape.
"""
from __future__ import annotations

import datetime
import enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryStatus(str, enum.Enum):
    OPEN = "OPEN"
    DETECTING = "DETECTING"
    DIAGNOSING = "DIAGNOSING"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RECOVERED = "RECOVERED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"


class IncidentCreate(BaseModel):
    """Payload used by upstream services (e.g. aiops-engine) to open an incident."""

    service_name: str = Field(..., min_length=1, max_length=128)
    severity: Severity = Severity.MEDIUM
    anomaly_score: Optional[float] = None
    metrics: Optional[dict[str, Any]] = None
    root_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    executed_action: Optional[str] = None
    recovery_status: RecoveryStatus = RecoveryStatus.OPEN
    source: Optional[str] = Field(default="aiops-engine", max_length=64)
    details: Optional[str] = None


class IncidentUpdate(BaseModel):
    """Partial update payload — every field optional so callers can PATCH just
    the fields relevant to the lifecycle stage they own (RCA, decision engine,
    remediation, verification, etc.)."""

    severity: Optional[Severity] = None
    metrics: Optional[dict[str, Any]] = None
    root_cause: Optional[str] = None
    recommended_action: Optional[str] = None
    executed_action: Optional[str] = None
    recovery_status: Optional[RecoveryStatus] = None
    details: Optional[str] = None
    resolved_time: Optional[datetime.datetime] = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_uid: str
    timestamp: datetime.datetime
    service_name: str
    severity: Severity
    anomaly_score: Optional[float]
    metrics: Optional[dict[str, Any]]
    root_cause: Optional[str]
    recommended_action: Optional[str]
    executed_action: Optional[str]
    recovery_status: RecoveryStatus
    resolved_time: Optional[datetime.datetime]
    source: Optional[str]
    details: Optional[str]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class IncidentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    stage: str
    message: str
    created_at: datetime.datetime


class ActionReport(BaseModel):
    action_type: str
    target: str
    backend: str
    mode: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class MetricSnapshotIn(BaseModel):
    service_name: str
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    latency_ms: Optional[float] = None
    error_rate_percent: Optional[float] = None
    http_requests_per_sec: Optional[float] = None
    queue_length: Optional[float] = None
    container_restarts: Optional[float] = None


class IncidentStats(BaseModel):
    open: int
    critical: int
    recovered_today: int
    resolved: int
    total: int
