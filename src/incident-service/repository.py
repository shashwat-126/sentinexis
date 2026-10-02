"""
Repository layer for the Incident Management Service.

Keeps SQLAlchemy query logic out of the route handlers (main.py) so the
persistence details can change without touching the API layer, and so the
routes stay easy to unit test against a fake repository.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Incident, IncidentEvent, Action, MetricSnapshot, AuditLog


class IncidentRepository:
    def __init__(self, db: Session):
        self.db = db

    # -- writes ---------------------------------------------------------
    def create(self, incident: Incident) -> Incident:
        self.db.add(incident)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def update(self, incident: Incident, fields: dict) -> Incident:
        for key, value in fields.items():
            setattr(incident, key, value)
        self.db.commit()
        self.db.refresh(incident)
        return incident

    def add_event(self, incident_id: int, stage: str, message: str) -> IncidentEvent:
        event = IncidentEvent(incident_id=incident_id, stage=stage, message=message)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    # -- reads ------------------------------------------------------------
    def get(self, incident_id: int) -> Optional[Incident]:
        return self.db.query(Incident).filter(Incident.id == incident_id).first()

    def get_by_uid(self, incident_uid: str) -> Optional[Incident]:
        return self.db.query(Incident).filter(Incident.incident_uid == incident_uid).first()

    def list(
        self,
        status: Optional[str] = None,
        service_name: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Incident]:
        query = self.db.query(Incident)
        if status:
            query = query.filter(Incident.recovery_status == status)
        if service_name:
            query = query.filter(Incident.service_name == service_name)
        if severity:
            query = query.filter(Incident.severity == severity)
        return (
            query.order_by(Incident.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def events_for(self, incident_id: int) -> list[IncidentEvent]:
        return (
            self.db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at.asc())
            .all()
        )

    def stats(self) -> dict:
        total = self.db.query(func.count(Incident.id)).scalar() or 0
        open_count = (
            self.db.query(func.count(Incident.id))
            .filter(Incident.recovery_status.notin_(["RECOVERED", "FAILED"]))
            .scalar()
            or 0
        )
        critical = (
            self.db.query(func.count(Incident.id))
            .filter(Incident.severity == "CRITICAL", Incident.recovery_status.notin_(["RECOVERED", "FAILED"]))
            .scalar()
            or 0
        )
        resolved = (
            self.db.query(func.count(Incident.id)).filter(Incident.recovery_status == "RECOVERED").scalar() or 0
        )
        since_midnight = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recovered_today = (
            self.db.query(func.count(Incident.id))
            .filter(Incident.recovery_status == "RECOVERED", Incident.resolved_time >= since_midnight)
            .scalar()
            or 0
        )
        return {
            "open": open_count,
            "critical": critical,
            "recovered_today": recovered_today,
            "resolved": resolved,
            "total": total,
        }

    # -- actions ------------------------------------------------------------
    def add_action(self, incident_id: int, **fields) -> Action:
        action = Action(incident_id=incident_id, **fields)
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action

    def actions_for(self, incident_id: int) -> list[Action]:
        return (
            self.db.query(Action)
            .filter(Action.incident_id == incident_id)
            .order_by(Action.created_at.asc())
            .all()
        )

    # -- metrics --------------------------------------------------------------
    def add_metric_snapshot(self, service_name: str, **fields) -> MetricSnapshot:
        snapshot = MetricSnapshot(service_name=service_name, **fields)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def metrics_for(self, service_name: str, limit: int = 200) -> list[MetricSnapshot]:
        return (
            self.db.query(MetricSnapshot)
            .filter(MetricSnapshot.service_name == service_name)
            .order_by(MetricSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )

    # -- audit ----------------------------------------------------------------
    def add_audit(self, actor: str, action: str, incident_id: int = None, detail: str = None) -> AuditLog:
        entry = AuditLog(actor=actor, action=action, incident_id=incident_id, detail=detail)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def recent_audit(self, limit: int = 200) -> list[AuditLog]:
        return self.db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
