from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import jwt
import datetime
import os
from shared.logger import setup_logger
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Auth Service")
logger = setup_logger("auth-service")

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-local-dev-only")
JWT_ALGORITHM = "HS256"

# Prometheus Metrics
Instrumentator().instrument(app).expose(app)

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

@app.on_event("startup")
async def startup_event():
    logger.info("Auth Service starting up")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "auth-service"}

@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    # Mock backend - in a real system we would verify against a users table in Postgres
    if req.username == "admin" and req.password == "admin":
        role = "admin"
    elif req.username == "operator" and req.password == "operator":
        role = "operator"
    else:
        logger.warning(f"Failed login attempt for user: {req.username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    payload = {
        "sub": req.username,
        "role": role,
        "exp": expiration
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.info(f"Successful login for user: {req.username}, role: {role}")
    return {"access_token": token, "token_type": "bearer"}
