import os

import requests

from shared.logger import setup_logger

logger = setup_logger("remediation-service.incident_client")

INCIDENT_SERVICE_URL = os.getenv("INCIDENT_SERVICE_URL", "http://incident-service:8003")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")

_HEADERS = {"X-Internal-Api-Key": INTERNAL_API_KEY}


def update_incident(incident_id: int, fields: dict) -> bool:
    try:
        resp = requests.patch(
            f"{INCIDENT_SERVICE_URL}/incidents/{incident_id}", json=fields, headers=_HEADERS, timeout=5
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to update incident {incident_id}: {e}")
        return False


def report_action(incident_id: int, action_type: str, target: str, backend: str, mode: str = None, result: str = None, error: str = None) -> bool:
    try:
        resp = requests.post(
            f"{INCIDENT_SERVICE_URL}/incidents/{incident_id}/actions",
            json={
                "action_type": action_type,
                "target": target,
                "backend": backend,
                "mode": mode,
                "result": result,
                "error": error,
            },
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to report action for incident {incident_id}: {e}")
        return False
