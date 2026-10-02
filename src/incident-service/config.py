import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "incident-service"
    host: str = os.getenv("INCIDENT_HOST", "0.0.0.0")
    port: int = int(os.getenv("INCIDENT_PORT", "8003"))
    # Shared secret used by trusted internal services (aiops-engine,
    # remediation-service, notification-service) to write/update incidents
    # without requiring a full user JWT. Rotate via env in production.
    internal_api_key: str = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")
    default_page_size: int = int(os.getenv("INCIDENT_DEFAULT_PAGE_SIZE", "50"))
    max_page_size: int = int(os.getenv("INCIDENT_MAX_PAGE_SIZE", "500"))


settings = Settings()
