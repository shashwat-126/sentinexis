"""
Notification Service
======================

Fans a single incident event out to whichever channels are configured
(Slack / Discord / Teams / Email). Channels with no webhook/SMTP config set
are skipped and reported as `not_configured` rather than erroring, so this
service works out of the box in dev and just needs env vars filled in for
real alerting.

incident-service calls this service (best-effort, fire-and-forget) whenever
an incident becomes CRITICAL severity or its status moves to ESCALATED,
FAILED, or RECOVERED.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from sqlalchemy.orm import Session

from channels import SENDERS
from models import NotificationLog
from shared.auth import verify_token
from shared.db import Base, engine, get_db
from shared.logger import setup_logger

logger = setup_logger("notification-service")
app = FastAPI(title="Notification Service")

Instrumentator().instrument(app).expose(app)

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:  # pragma: no cover
    logger.error(f"DB init error: {e}")

INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")


class NotifyRequest(BaseModel):
    incident_id: Optional[int] = None
    incident_uid: Optional[str] = None
    service_name: str
    severity: str
    status: str
    title: Optional[str] = None
    message: Optional[str] = None
    channels: Optional[list[str]] = None  # None = all configured channels


def require_internal(x_internal_api_key: Optional[str] = Header(default=None, alias="X-Internal-Api-Key")):
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Valid internal API key required")
    return True


@app.on_event("startup")
async def startup_event():
    logger.info("Notification Service starting up")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "notification-service"}


@app.post("/notify")
def notify(req: NotifyRequest, db: Session = Depends(get_db), _auth: bool = Depends(require_internal)):
    title = req.title or f"[{req.severity}] {req.service_name} — {req.status}"
    message = req.message or (
        f"Incident {req.incident_uid or req.incident_id} on {req.service_name} "
        f"is now {req.status} (severity: {req.severity})."
    )

    targets = req.channels or list(SENDERS.keys())
    results = []
    for channel in targets:
        sender = SENDERS.get(channel)
        if not sender:
            result = {"channel": channel, "sent": False, "reason": "unknown_channel"}
        else:
            result = sender(title, message)
        results.append(result)
        try:
            db.add(
                NotificationLog(
                    incident_id=req.incident_id,
                    incident_uid=req.incident_uid,
                    service_name=req.service_name,
                    severity=req.severity,
                    status=req.status,
                    channel=result["channel"],
                    sent=result.get("sent", False),
                    reason=result.get("reason"),
                    title=title,
                    message=message,
                )
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to persist notification log: {e}")
            db.rollback()

    sent_count = sum(1 for r in results if r.get("sent"))
    logger.info(f"Notification for incident {req.incident_id}: sent to {sent_count}/{len(results)} channels")
    return {"results": results}


@app.get("/notifications")
def list_notifications(
    incident_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _token: dict = Depends(verify_token),
):
    query = db.query(NotificationLog).order_by(NotificationLog.created_at.desc())
    if incident_id is not None:
        query = query.filter(NotificationLog.incident_id == incident_id)
    rows = query.limit(limit).all()
    return [
        {
            "id": r.id,
            "incident_id": r.incident_id,
            "incident_uid": r.incident_uid,
            "service_name": r.service_name,
            "severity": r.severity,
            "status": r.status,
            "channel": r.channel,
            "sent": r.sent,
            "reason": r.reason,
            "created_at": r.created_at,
        }
        for r in rows
    ]
