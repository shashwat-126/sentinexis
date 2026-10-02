"""
Recovery Verification
=======================

After a remediation action executes, we don't just assume it worked. We
wait, poll the target's /health endpoint, and retry a configurable number
of times before declaring the incident RECOVERED or ESCALATED.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from shared.logger import setup_logger

logger = setup_logger("remediation-service.verification")


@dataclass(frozen=True)
class VerificationConfig:
    wait_seconds: int = 10
    max_retries: int = 3
    retry_interval_seconds: int = 5
    timeout_seconds: int = 5


def verify_recovery(health_url: str, config: VerificationConfig = VerificationConfig()) -> dict:
    """Wait, then poll `health_url` up to `max_retries` times. Returns a
    result dict with `recovered: bool` and the attempt history."""
    logger.info(f"Verification: waiting {config.wait_seconds}s before checking {health_url}")
    time.sleep(config.wait_seconds)

    attempts = []
    for attempt in range(1, config.max_retries + 1):
        healthy, detail = _check_health(health_url, config.timeout_seconds)
        attempts.append({"attempt": attempt, "healthy": healthy, "detail": detail})
        if healthy:
            logger.info(f"Verification succeeded on attempt {attempt} for {health_url}")
            return {"recovered": True, "attempts": attempts}
        if attempt < config.max_retries:
            time.sleep(config.retry_interval_seconds)

    logger.warning(f"Verification failed after {config.max_retries} attempts for {health_url}")
    return {"recovered": False, "attempts": attempts}


def _check_health(health_url: str, timeout: int) -> tuple[bool, str]:
    try:
        resp = requests.get(health_url, timeout=timeout)
        if resp.status_code == 200:
            body = resp.json()
            if body.get("status") == "ok":
                return True, "status_ok"
            return False, f"unhealthy_body:{body}"
        return False, f"http_{resp.status_code}"
    except Exception as e:
        return False, f"unreachable:{e}"
