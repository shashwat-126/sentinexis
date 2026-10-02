"""
Remediation Service
=====================

Owns actually *doing* something about an incident: executing the action the
decision engine picked (via Docker SDK or Kubernetes client -- never shell
scripts), then verifying the target recovered, then reporting the outcome
back to incident-service. aiops-engine no longer touches Docker/K8s
directly; it calls this service instead.
"""
from __future__ import annotations

import datetime
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

import docker_executor
import k8s_executor
from config import settings
from incident_client import update_incident, report_action
from internal_auth import require_writer
from verification import VerificationConfig, verify_recovery

from shared.logger import setup_logger

logger = setup_logger("remediation-service")
app = FastAPI(title="Remediation Service")

Instrumentator().instrument(app).expose(app)


DOCKER_ACTIONS = {
    "restart_container": docker_executor.restart_container,
    "stop_container": docker_executor.stop_container,
    "start_container": docker_executor.start_container,
    "inspect_container": docker_executor.inspect_container,
}

K8S_ACTIONS = {
    "restart_deployment": k8s_executor.restart_deployment,
    "scale_deployment": k8s_executor.scale_deployment,
    "rollback_deployment": k8s_executor.rollback_deployment,
    "delete_pod": k8s_executor.delete_pod,
    "restart_pod": k8s_executor.restart_pod,
}

# Maps decision-engine action names to a concrete executor action, so
# aiops-engine can request a logical action ("restart_container",
# "scale_service", "alert_operator", "human_approval") without knowing the
# underlying SDK call.
ACTION_ALIASES = {
    "scale_service": "scale_deployment",
}


class RemediateRequest(BaseModel):
    incident_id: int
    service_name: str
    action: str
    target_type: str = "docker"  # "docker" or "kubernetes"
    replicas: Optional[int] = None
    namespace: Optional[str] = "default"


class RemediateAck(BaseModel):
    incident_id: int
    status: str
    action: str


@app.on_event("startup")
async def startup_event():
    logger.info("Remediation Service starting up")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "remediation-service", "docker_available": docker_executor.get_client() is not None}


@app.post("/remediate", response_model=RemediateAck)
def remediate(req: RemediateRequest, background_tasks: BackgroundTasks, _caller: dict = Depends(require_writer)):
    action = ACTION_ALIASES.get(req.action, req.action)

    if action in ("alert_operator", "human_approval"):
        # No automated action to take -- just make sure the incident reflects
        # that a human needs to look at it, and notify (notification-service
        # handles the actual paging in Phase 6, triggered off this status).
        update_incident(req.incident_id, {"recovery_status": "ESCALATED", "executed_action": action})
        return RemediateAck(incident_id=req.incident_id, status="escalated", action=action)

    if action not in DOCKER_ACTIONS and action not in K8S_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown remediation action: {req.action}")

    if action in K8S_ACTIONS and not settings.enable_kubernetes_remediation:
        raise HTTPException(
            status_code=403,
            detail=f"Kubernetes remediation ({action}) is disabled until validated against a real cluster. "
                   "Set ENABLE_KUBERNETES_REMEDIATION=true once infra/kubernetes has been tested. "
                   "The Docker-only path (detect -> incident -> decision -> restart -> verify -> recovered) "
                   "is the supported demo for now.",
        )

    update_incident(req.incident_id, {"recovery_status": "REMEDIATING", "executed_action": action})

    background_tasks.add_task(_execute_and_verify, req, action)
    return RemediateAck(incident_id=req.incident_id, status="in_progress", action=action)


def _execute_and_verify(req: RemediateRequest, action: str):
    logger.info(f"Executing {action} for incident {req.incident_id} on {req.service_name}")

    if action in DOCKER_ACTIONS:
        result = DOCKER_ACTIONS[action](req.service_name)
    else:
        fn = K8S_ACTIONS[action]
        if action == "scale_deployment":
            result = fn(req.service_name, req.replicas or 2, req.namespace or "default")
        else:
            result = fn(req.service_name, req.namespace or "default")

    logger.info(f"Remediation result for incident {req.incident_id}: {result}")

    backend = "kubernetes" if action in K8S_ACTIONS else "docker"
    report_action(
        req.incident_id,
        action_type=action,
        target=req.service_name,
        backend=backend,
        mode=result.get("mode"),
        result=result.get("result"),
        error=result.get("error") if isinstance(result.get("error"), str) else None,
    )

    health_url = settings.health_urls.get(req.service_name)
    if not health_url:
        logger.warning(f"No known health URL for {req.service_name}; skipping verification, marking recovered.")
        update_incident(
            req.incident_id,
            {"recovery_status": "RECOVERED", "resolved_time": datetime.datetime.utcnow().isoformat()},
        )
        return

    update_incident(req.incident_id, {"recovery_status": "VERIFYING"})
    verification = verify_recovery(
        health_url,
        VerificationConfig(
            wait_seconds=settings.verification_wait_seconds,
            max_retries=settings.verification_max_retries,
            retry_interval_seconds=settings.verification_retry_interval_seconds,
        ),
    )

    if verification["recovered"]:
        update_incident(
            req.incident_id,
            {"recovery_status": "RECOVERED", "resolved_time": datetime.datetime.utcnow().isoformat()},
        )
    else:
        update_incident(req.incident_id, {"recovery_status": "ESCALATED"})


# ---------------------------------------------------------------------------
# Phase 8: Chaos Engineering endpoints that need real infrastructure control
# (stopping a container to simulate a failure). CPU/memory/latency chaos
# lives in inference-service since it can shape its own metrics; this
# service owns anything that requires actually touching Docker.
# ---------------------------------------------------------------------------
class ChaosContainerRequest(BaseModel):
    container_name: str
    confirm: bool = False


@app.post("/chaos/container-failure")
def chaos_container_failure(req: ChaosContainerRequest, _caller: dict = Depends(require_writer)):
    if not req.confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to acknowledge this will stop a real container")
    result = docker_executor.stop_container(req.container_name)
    logger.warning(f"[CHAOS] Simulated container failure: {result}")
    return {"chaos": "container-failure", "result": result}


@app.post("/chaos/database-failure")
def chaos_database_failure(confirm: bool = False, _caller: dict = Depends(require_writer)):
    if not settings.enable_db_chaos:
        raise HTTPException(
            status_code=403,
            detail="Database chaos is disabled by default (Postgres is a shared dependency of nearly every "
                   "service -- stopping it makes the whole control plane look broken). Set "
                   "ENABLE_DB_CHAOS=true for an isolated staging experiment only, not the normal demo.",
        )
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to acknowledge this will stop the database container")
    result = docker_executor.stop_container("postgres")
    logger.warning(f"[CHAOS] Simulated database failure: {result}")
    return {"chaos": "database-failure", "result": result}
