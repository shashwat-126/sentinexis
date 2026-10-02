"""
SQLAlchemy models for the Incident Management Service.

Two tables are introduced here:

- incidents        The core incident record, one row per detected anomaly /
                    self-healing episode. This is the row the rest of the
                    platform (RCA, decision engine, remediation, verification,
                    notifications, dashboard) will read and progressively
                    enrich as the incident moves through its lifecycle.
- incident_events   An append-only timeline of what happened to an incident
                    (detected -> root cause identified -> action decided ->
                    remediation executed -> verification -> resolved). This
                    backs the "Incident Timeline" feature in the dashboard.
"""
import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from shared.db import Base


def _uid() -> str:
    return uuid.uuid4().hex


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_uid = Column(String(32), unique=True, index=True, default=_uid, nullable=False)

    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    service_name = Column(String(128), index=True, nullable=False)
    severity = Column(String(16), default="MEDIUM", index=True, nullable=False)

    anomaly_score = Column(Float, nullable=True)
    metrics = Column(JSONB, nullable=True)

    root_cause = Column(String(64), nullable=True, index=True)
    recommended_action = Column(String(128), nullable=True)
    executed_action = Column(String(128), nullable=True)

    recovery_status = Column(String(16), default="OPEN", index=True, nullable=False)
    resolved_time = Column(DateTime, nullable=True)

    source = Column(String(64), nullable=True)
    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    events = relationship(
        "IncidentEvent", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentEvent.created_at"
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    stage = Column(String(32), nullable=False)  # DETECTED, RCA, DECISION, REMEDIATION, VERIFICATION, RESOLVED, ESCALATED
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="events")


class Action(Base):
    """One row per remediation action attempted against an incident --
    the `Actions` table from the platform DB spec. remediation-service
    reports back here (via PATCH /incidents/{id}/actions) after executing
    a Docker/Kubernetes action, independent of the incident's own
    executed_action summary field."""

    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    action_type = Column(String(64), nullable=False)
    target = Column(String(128), nullable=False)
    backend = Column(String(16), nullable=False)  # docker | kubernetes
    mode = Column(String(16), nullable=True)  # live | mock
    result = Column(String(32), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MetricSnapshot(Base):
    """Periodic metric readings collected by aiops-engine's RCA sweep, kept
    here so the dashboard can chart CPU/memory/latency/error-rate history
    without querying Prometheus directly from the browser. This is the
    `Metrics` table from the platform DB spec."""

    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(128), index=True, nullable=False)
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    error_rate_percent = Column(Float, nullable=True)
    http_requests_per_sec = Column(Float, nullable=True)
    queue_length = Column(Float, nullable=True)
    container_restarts = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)


class AuditLog(Base):
    """Who/what/when for every write against the incident lifecycle -- the
    `Audit Logs` table from the platform DB spec. Covers both automated
    writers (aiops-engine, remediation-service, notification-service, all
    identified via their internal API key) and human operators (identified
    via their JWT `sub` claim) acting through the dashboard."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String(64), nullable=False)  # "internal-service" or a user's `sub`
    action = Column(String(64), nullable=False)  # e.g. "incident.create", "incident.update"
    incident_id = Column(Integer, nullable=True, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
