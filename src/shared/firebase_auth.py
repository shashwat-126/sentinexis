"""
Verifies Firebase Authentication ID tokens using only Google's public
signing certs -- deliberately *not* the firebase-admin SDK, so the gateway
needs no service account JSON, just the public FIREBASE_PROJECT_ID.

This is the external trust boundary: only the API Gateway calls this.
Every other service keeps trusting the existing internal JWT
(shared.auth.verify_token) or the internal API key, completely unchanged --
see mint_internal_token() in api-gateway/main.py for the translation step.
"""
import json
import os
import time
import urllib.request

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_pem_x509_certificate
from fastapi import HTTPException

from shared.logger import setup_logger

logger = setup_logger("shared.firebase_auth")

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_CERT_CACHE_SECONDS = 3600  # Google rotates these infrequently; refresh hourly

_cert_cache = {"certs": {}, "expires_at": 0.0}


def _fetch_certs(force: bool = False) -> dict:
    now = time.time()
    if not force and _cert_cache["certs"] and now < _cert_cache["expires_at"]:
        return _cert_cache["certs"]
    try:
        with urllib.request.urlopen(_CERTS_URL, timeout=5) as resp:
            certs = json.loads(resp.read().decode())
        _cert_cache["certs"] = certs
        _cert_cache["expires_at"] = now + _CERT_CACHE_SECONDS
        return certs
    except Exception as e:
        logger.error(f"Failed to fetch Firebase public certs: {e}")
        if _cert_cache["certs"]:
            return _cert_cache["certs"]  # serve stale rather than fail every request
        raise HTTPException(status_code=503, detail="Unable to reach Firebase cert endpoint")


def verify_firebase_id_token(token: str) -> dict:
    """Verify a Firebase Authentication ID token. Raises HTTPException(401)
    on any failure; returns the decoded claims (sub=uid, email, ...) on
    success."""
    if not FIREBASE_PROJECT_ID:
        logger.error("FIREBASE_PROJECT_ID is not configured on the gateway")
        raise HTTPException(status_code=500, detail="Firebase auth is not configured on the server")

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Malformed Firebase token")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Firebase token missing key id")

    certs = _fetch_certs()
    cert_pem = certs.get(kid)
    if not cert_pem:
        # Signing key may have rotated since our cache was built -- refresh once and retry.
        certs = _fetch_certs(force=True)
        cert_pem = certs.get(kid)
    if not cert_pem:
        raise HTTPException(status_code=401, detail="Unknown Firebase signing key")

    try:
        public_key = load_pem_x509_certificate(cert_pem.encode(), default_backend()).public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=FIREBASE_PROJECT_ID,
            issuer=f"https://securetoken.google.com/{FIREBASE_PROJECT_ID}",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Firebase token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    if not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Firebase token missing subject")

    return payload
