import os
from dataclasses import dataclass, field


def _default_health_urls() -> dict:
    return {
        "api-gateway": "http://api-gateway:8080/health",
        "auth-service": "http://auth-service:8000/health",
        "inference-service": "http://inference-service:8001/health",
        "result-service": "http://result-service:8002/health",
        "incident-service": "http://incident-service:8003/health",
    }


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("REMEDIATION_HOST", "0.0.0.0")
    port: int = int(os.getenv("REMEDIATION_PORT", "8004"))
    internal_api_key: str = os.getenv("INTERNAL_API_KEY", "change-this-internal-key")
    verification_wait_seconds: int = int(os.getenv("VERIFICATION_WAIT_SECONDS", "10"))
    verification_max_retries: int = int(os.getenv("VERIFICATION_MAX_RETRIES", "3"))
    verification_retry_interval_seconds: int = int(os.getenv("VERIFICATION_RETRY_INTERVAL_SECONDS", "5"))
    health_urls: dict = field(default_factory=_default_health_urls)

    # Both default OFF. Postgres is a shared dependency of nearly every
    # service -- killing it makes the whole control plane look broken, not
    # just one service, so it's opt-in for isolated staging experiments
    # only, never the default demo path. Kubernetes remediation is opt-in
    # until it's been validated against a real cluster (the Docker-only
    # path is what's actually been exercised end-to-end so far).
    enable_db_chaos: bool = os.getenv("ENABLE_DB_CHAOS", "false").lower() == "true"
    enable_kubernetes_remediation: bool = os.getenv("ENABLE_KUBERNETES_REMEDIATION", "false").lower() == "true"


settings = Settings()
