import os

import requests

from shared.logger import setup_logger

logger = setup_logger("incident-service.notifications")

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8005")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")

# Statuses/severities worth paging someone about. Routine OPEN/REMEDIATING
# transitions stay silent -- only the states an operator actually needs to
# know about trigger an outbound notification.
NOTIFY_STATUSES = {"ESCALATED", "FAILED", "RECOVERED"}


def notify_if_needed(incident) -> None:
    should_notify = incident.severity == "CRITICAL" or incident.recovery_status in NOTIFY_STATUSES
    if not should_notify:
        return
    try:
        requests.post(
            f"{NOTIFICATION_SERVICE_URL}/notify",
            json={
                "incident_id": incident.id,
                "incident_uid": incident.incident_uid,
                "service_name": incident.service_name,
                "severity": incident.severity,
                "status": incident.recovery_status,
            },
            headers={"X-Internal-Api-Key": INTERNAL_API_KEY},
            timeout=3,
        )
    except Exception as e:
        # Notifications are best-effort -- never let a notification-service
        # outage block incident lifecycle updates.
        logger.warning(f"Notification dispatch failed for incident {incident.id}: {e}")
