"""
Incident Management Service
============================

Owns the lifecycle record for every self-healing episode on the platform:

    detected -> root cause identified -> action decided -> remediation
    executed -> recovery verified -> resolved (or escalated)

Every other new service in the AIOps platform (RCA engine, decision engine,
remediation-service, notification-service, dashboard) reads and writes
through this service rather than touching the `incidents` table directly.
That keeps the schema and business rules ("what counts as OPEN vs
RECOVERED", "when is resolved_time set") in one place.

Phase 1 of the platform build: this service exists, is wired into
docker-compose, and aiops-engine now opens a real Incident (with a timeline
event) for every anomaly it detects, in addition to its existing
IncidentLog entry. Root cause / recommended action / executed action fields
are present in the schema now so later phases (RCA engine, decision engine,
remediation-service) can PATCH them in without another migration.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings
from internal_auth import require_writer
from models import Incident
from notifications import notify_if_needed
from repository import IncidentRepository
from schemas import (
    ActionReport,
    IncidentCreate,
    IncidentEventOut,
    IncidentOut,
    IncidentStats,
    IncidentUpdate,
    MetricSnapshotIn,
)
from ws_manager import manager

from shared.auth import verify_token
from shared.db import Base, engine, get_db
from shared.logger import setup_logger

logger = setup_logger("incident-service")
app = FastAPI(title="Incident Management Service")

Instrumentator().instrument(app).expose(app)

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:  # pragma: no cover - startup diagnostics only
    logger.error(f"DB init error: {e}")


@app.on_event("startup")
async def startup_event():
    logger.info("Incident Management Service starting up")


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    return {"status": "ok", "service": "incident-service", "db": db_status}


@app.post("/incidents", response_model=IncidentOut, status_code=201)
async def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    _caller: dict = Depends(require_writer),
):
    repo = IncidentRepository(db)
    incident = Incident(
        service_name=payload.service_name,
        severity=payload.severity.value,
        anomaly_score=payload.anomaly_score,
        metrics=payload.metrics,
        root_cause=payload.root_cause,
        recommended_action=payload.recommended_action,
        executed_action=payload.executed_action,
        recovery_status=payload.recovery_status.value,
        source=payload.source,
        details=payload.details,
    )
    incident = repo.create(incident)
    repo.add_event(
        incident.id,
        stage="DETECTED",
        message=payload.details or f"Anomaly detected on {payload.service_name}",
    )
    repo.add_audit(_caller.get("sub", "unknown"), "incident.create", incident_id=incident.id, detail=payload.service_name)
    logger.info(f"Incident {incident.incident_uid} opened for {incident.service_name}")

    out = IncidentOut.model_validate(incident)
    await manager.broadcast("incident_created", out.model_dump())
    notify_if_needed(incident)
    return incident


@app.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[str] = None,
    service_name: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=settings.default_page_size, le=settings.max_page_size),
    offset: int = 0,
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
):
    repo = IncidentRepository(db)
    return repo.list(status=status, service_name=service_name, severity=severity, limit=limit, offset=offset)


@app.get("/incidents/stats", response_model=IncidentStats)
def incident_stats(db: Session = Depends(get_db), _token: dict = Depends(verify_token)):
    repo = IncidentRepository(db)
    return repo.stats()


@app.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db), _token: dict = Depends(verify_token)):
    repo = IncidentRepository(db)
    incident = repo.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/incidents/{incident_id}/timeline", response_model=list[IncidentEventOut])
def get_incident_timeline(incident_id: int, db: Session = Depends(get_db), _token: dict = Depends(verify_token)):
    repo = IncidentRepository(db)
    if not repo.get(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    return repo.events_for(incident_id)


@app.patch("/incidents/{incident_id}", response_model=IncidentOut)
async def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    _caller: dict = Depends(require_writer),
):
    repo = IncidentRepository(db)
    incident = repo.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    fields = payload.model_dump(exclude_unset=True)
    for enum_field in ("severity", "recovery_status"):
        if enum_field in fields and fields[enum_field] is not None:
            fields[enum_field] = fields[enum_field].value if hasattr(fields[enum_field], "value") else fields[enum_field]

    incident = repo.update(incident, fields)

    if "recovery_status" in fields:
        stage_map = {
            "DIAGNOSING": "RCA",
            "REMEDIATING": "REMEDIATION",
            "VERIFYING": "VERIFICATION",
            "RECOVERED": "RESOLVED",
            "ESCALATED": "ESCALATED",
            "FAILED": "FAILED",
        }
        stage = stage_map.get(fields["recovery_status"], fields["recovery_status"])
        repo.add_event(incident.id, stage=stage, message=f"Status changed to {fields['recovery_status']}")

    logger.info(f"Incident {incident.incident_uid} updated: {list(fields.keys())}")
    repo.add_audit(_caller.get("sub", "unknown"), "incident.update", incident_id=incident.id, detail=str(list(fields.keys())))

    out = IncidentOut.model_validate(incident)
    await manager.broadcast("incident_updated", out.model_dump())
    notify_if_needed(incident)
    return incident


@app.post("/incidents/{incident_id}/actions", status_code=201)
def report_action(
    incident_id: int,
    payload: ActionReport,
    db: Session = Depends(get_db),
    _caller: dict = Depends(require_writer),
):
    """remediation-service reports each concrete Docker/K8s action it takes
    here, independent of the incident's summary `executed_action` field --
    this is the durable `Actions` audit trail (one incident can accumulate
    several actions across escalation levels)."""
    repo = IncidentRepository(db)
    if not repo.get(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    action = repo.add_action(incident_id, **payload.model_dump())
    return {
        "id": action.id,
        "incident_id": action.incident_id,
        "action_type": action.action_type,
        "target": action.target,
        "backend": action.backend,
        "mode": action.mode,
        "result": action.result,
        "created_at": action.created_at,
    }


@app.get("/incidents/{incident_id}/actions")
def list_actions(incident_id: int, db: Session = Depends(get_db), _token: dict = Depends(verify_token)):
    repo = IncidentRepository(db)
    if not repo.get(incident_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    return [
        {
            "id": a.id,
            "action_type": a.action_type,
            "target": a.target,
            "backend": a.backend,
            "mode": a.mode,
            "result": a.result,
            "error": a.error,
            "created_at": a.created_at,
        }
        for a in repo.actions_for(incident_id)
    ]


@app.post("/metrics", status_code=201)
def report_metrics(payload: MetricSnapshotIn, db: Session = Depends(get_db), _caller: dict = Depends(require_writer)):
    """aiops-engine POSTs a metric snapshot here after every RCA sweep of a
    monitored service, so the dashboard can chart history without talking
    to Prometheus directly."""
    repo = IncidentRepository(db)
    fields = payload.model_dump(exclude={"service_name"})
    repo.add_metric_snapshot(payload.service_name, **fields)
    return {"status": "recorded"}


@app.get("/metrics/{service_name}")
def get_metrics(
    service_name: str,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
):
    repo = IncidentRepository(db)
    rows = repo.metrics_for(service_name, limit=limit)
    return [
        {
            "service_name": r.service_name,
            "cpu_percent": r.cpu_percent,
            "memory_percent": r.memory_percent,
            "disk_percent": r.disk_percent,
            "latency_ms": r.latency_ms,
            "error_rate_percent": r.error_rate_percent,
            "http_requests_per_sec": r.http_requests_per_sec,
            "queue_length": r.queue_length,
            "container_restarts": r.container_restarts,
            "created_at": r.created_at,
        }
        for r in reversed(rows)
    ]


@app.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
):
    repo = IncidentRepository(db)
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "action": a.action,
            "incident_id": a.incident_id,
            "detail": a.detail,
            "created_at": a.created_at,
        }
        for a in repo.recent_audit(limit=limit)
    ]


@app.websocket("/ws/incidents")
async def incidents_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Dashboard doesn't need to send anything -- just keep the
            # connection open and drain any client pings/keepalives.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
