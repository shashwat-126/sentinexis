import datetime
import os
import httpx
import jwt
import websockets
from fastapi import Depends, FastAPI, Header, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from shared.firebase_auth import verify_firebase_id_token
from shared.logger import setup_logger
from prometheus_fastapi_instrumentator import Instrumentator

from fastapi.middleware.cors import CORSMiddleware

logger = setup_logger("api-gateway")
app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs from Environment mapping
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://inference-service:8001")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:8002")
INCIDENT_SERVICE_URL = os.getenv("INCIDENT_SERVICE_URL", "http://incident-service:8003")
REMEDIATION_SERVICE_URL = os.getenv("REMEDIATION_SERVICE_URL", "http://remediation-service:8004")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8005")
INCIDENT_SERVICE_WS_URL = os.getenv("INCIDENT_SERVICE_WS_URL", "ws://incident-service:8003/ws/incidents")

# Same secret shared/auth.py's verify_token() checks -- the gateway mints a
# short-lived internal JWT here after verifying a Firebase ID token, so
# every downstream service keeps working completely unchanged.
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-local-dev-only")
JWT_ALGORITHM = "HS256"

Instrumentator().instrument(app).expose(app)

http_client = httpx.AsyncClient()


def mint_internal_token(firebase_claims: dict) -> str:
    """Translate a verified Firebase identity into the internal JWT format
    every backend service already trusts via shared.auth.verify_token."""
    payload = {
        "sub": firebase_claims.get("email") or firebase_claims["sub"],
        "uid": firebase_claims["sub"],
        "role": "operator",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_firebase_user(authorization: str = Header(default=None)) -> str:
    """Dependency for every externally-facing proxy route: verifies the
    caller's Firebase ID token and returns a freshly minted internal JWT to
    forward downstream. This is the ONE place Firebase is checked -- every
    route that depends on this gets Firebase auth for free, no per-service
    changes needed."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Firebase bearer token")
    firebase_token = authorization.split(" ", 1)[1]
    claims = verify_firebase_id_token(firebase_token)
    return mint_internal_token(claims)

@app.on_event("startup")
async def startup_event():
    logger.info("API Gateway starting up")

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api-gateway"}

async def proxy_request(service_url: str, request: Request, path: str, internal_token: str = None):
    url = f"{service_url}/{path}"
    try:
        # Extract relevant fields from original request
        body = await request.body()
        headers = dict(request.headers)
        # Prevent forwarding host header explicitly which causes issues
        headers.pop("host", None)
        headers.pop("content-length", None)
        if internal_token:
            # Replace whatever the browser sent (a Firebase ID token) with
            # the internal JWT every downstream service already trusts.
            headers["authorization"] = f"Bearer {internal_token}"

        response = await http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        return JSONResponse(content=response.json(), status_code=response.status_code, headers=dict(response.headers))
    except httpx.RequestError as e:
        logger.error(f"Proxy request error to {url}: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        logger.error(f"Unknown proxy error: {e}")
        raise HTTPException(status_code=500, detail="Internal gateway error")

@app.api_route("/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_auth(request: Request, path: str):
    return await proxy_request(AUTH_SERVICE_URL, request, path)

@app.api_route("/infer/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_infer(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    return await proxy_request(INFERENCE_SERVICE_URL, request, path, internal_token)

@app.api_route("/results/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_results(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    return await proxy_request(RESULT_SERVICE_URL, request, path, internal_token)

@app.get("/incidents/health")
async def route_incidents_health(request: Request, internal_token: str = Depends(require_firebase_user)):
    # incident-service's health check lives at root /health like every
    # other service, not under its own /incidents prefix -- this has to be
    # registered before the catch-all below, or FastAPI never reaches it.
    return await proxy_request(INCIDENT_SERVICE_URL, request, "health", internal_token)

@app.api_route("/incidents/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def route_incidents(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    # incident-service's own routes are self-prefixed (/incidents,
    # /incidents/stats, /incidents/{id}, ...) -- unlike result-service or
    # remediation-service, which mount at root and rely on the gateway's
    # prefix to select them. Forwarding just the captured tail (e.g.
    # "stats") hit http://incident-service:8003/stats, which doesn't
    # exist -- a 404 on every incident/stat/timeline call from the
    # browser. Re-adding the "incidents/" prefix here fixes it; internal
    # callers (aiops-engine, remediation-service) were never affected
    # since they talk to incident-service directly, bypassing the gateway.
    target_path = f"incidents/{path}".rstrip("/")
    return await proxy_request(INCIDENT_SERVICE_URL, request, target_path, internal_token)

@app.api_route("/remediation/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def route_remediation(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    return await proxy_request(REMEDIATION_SERVICE_URL, request, path, internal_token)

@app.api_route("/notifications/{path:path}", methods=["GET", "POST"])
async def route_notifications(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    return await proxy_request(NOTIFICATION_SERVICE_URL, request, path, internal_token)

@app.api_route("/metrics-history/{path:path}", methods=["GET", "POST"])
async def route_metrics_history(request: Request, path: str, internal_token: str = Depends(require_firebase_user)):
    """incident-service exposes metric-snapshot history at /metrics/... (not
    under /incidents/...) -- this proxies it through under a distinct
    gateway path so it doesn't collide with each service's own Prometheus
    /metrics scrape endpoint."""
    return await proxy_request(INCIDENT_SERVICE_URL, request, f"metrics/{path}", internal_token)

@app.api_route("/audit-logs", methods=["GET"])
async def route_audit_logs(request: Request, internal_token: str = Depends(require_firebase_user)):
    return await proxy_request(INCIDENT_SERVICE_URL, request, "audit-logs", internal_token)

@app.websocket("/ws/incidents")
async def ws_incidents_proxy(client_ws: WebSocket):
    """Relay the dashboard's WebSocket connection through to incident-service.

    httpx can't do WebSockets, so this is a minimal bidirectional relay: two
    concurrent tasks copy frames in each direction until either side closes.
    Browsers can't set custom headers on a native WebSocket, so the Firebase
    ID token travels as ?token=... instead of an Authorization header --
    verified with the same check every REST route uses before we accept the
    connection at all.
    """
    firebase_token = client_ws.query_params.get("token")
    if not firebase_token:
        await client_ws.close(code=4401)
        return
    try:
        verify_firebase_id_token(firebase_token)
    except HTTPException:
        await client_ws.close(code=4401)
        return

    await client_ws.accept()
    try:
        async with websockets.connect(INCIDENT_SERVICE_WS_URL) as upstream:

            async def client_to_upstream():
                try:
                    while True:
                        msg = await client_ws.receive_text()
                        await upstream.send(msg)
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client():
                try:
                    async for msg in upstream:
                        await client_ws.send_text(msg)
                except Exception:
                    pass

            import asyncio
            done, pending = await asyncio.wait(
                [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
