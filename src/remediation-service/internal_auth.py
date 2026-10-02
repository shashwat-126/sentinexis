from typing import Optional

from fastapi import Header, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt as pyjwt

from shared.auth import JWT_ALGORITHM, JWT_SECRET
from shared.logger import setup_logger

from config import settings

logger = setup_logger("remediation-service.auth")
_bearer = HTTPBearer(auto_error=False)


def require_writer(
    x_internal_api_key: Optional[str] = Header(default=None, alias="X-Internal-Api-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
):
    if x_internal_api_key and x_internal_api_key == settings.internal_api_key:
        return {"sub": "internal-service", "role": "service"}
    if credentials:
        try:
            return pyjwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except pyjwt.PyJWTError:
            pass
    logger.warning("Rejected remediation request: missing/invalid internal key and JWT")
    raise HTTPException(status_code=401, detail="Valid internal API key or bearer token required")
