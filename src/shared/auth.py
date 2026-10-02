import os
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared.logger import setup_logger

logger = setup_logger("shared.auth")
security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-local-dev-only")
JWT_ALGORITHM = "HS256"

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        logger.warning("Invalid token provided")
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_admin(payload: dict = Security(verify_token)):
    if payload.get("role") != "admin":
        logger.warning(f"User {payload.get('sub')} attempted admin action without admin role")
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload
