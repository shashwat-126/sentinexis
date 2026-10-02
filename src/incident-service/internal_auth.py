"""
Authorization for the Incident Management Service's write endpoints.

Two classes of caller need write access:
  1. Trusted internal services (aiops-engine today; remediation-service and
     notification-service in later phases) that open/update incidents as
     part of the automated self-healing loop. These authenticate with a
     shared internal API key header rather than a per-user JWT.
  2. Logged-in operators using the dashboard, who authenticate with the
     normal JWT bearer token issued by auth-service and may want to manually
     annotate or close an incident.

`require_writer` accepts either.
"""
from typing import Optional

from fastapi import Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.auth import JWT_ALGORITHM, JWT_SECRET
from shared.logger import setup_logger
import jwt as pyjwt

from config import settings

logger = setup_logger("incident-service.auth")

_bearer = HTTPBearer(auto_error=False)


def require_writer(
    x_internal_api_key: Optional[str] = Header(default=None, alias="X-Internal-Api-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
):
    if x_internal_api_key and x_internal_api_key == settings.internal_api_key:
        return {"sub": "internal-service", "role": "service"}

    if credentials:
        try:
            payload = pyjwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except pyjwt.PyJWTError:
            pass

    logger.warning("Rejected write request: missing/invalid internal key and JWT")
    raise HTTPException(status_code=401, detail="Valid internal API key or bearer token required")
