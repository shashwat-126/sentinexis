import time
import random
import os
import json
from fastapi import FastAPI, Depends, BackgroundTasks
from pydantic import BaseModel
from shared.logger import setup_logger
from shared.auth import verify_token
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Summary, Gauge, Counter
import redis

app = FastAPI(title="Inference Service")
logger = setup_logger("inference-service")

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

# Custom metrics
INFERENCE_LATENCY = Summary("inference_latency_seconds", "Time spent processing inference request")
QUEUE_DEPTH = Gauge("queue_depth", "Number of inference requests currently queued")
INFERENCE_ERRORS = Counter("inference_errors_total", "Total inference processing errors")
ANOMALY_SCORE = Gauge("anomaly_score", "Simulated anomaly score output from inference")
CHAOS_ACTIVE = Gauge("chaos_scenario_active", "1 if a chaos scenario is currently injecting faults, else 0", ["scenario"])

Instrumentator().instrument(app).expose(app)

# ---------------------------------------------------------------------------
# Phase 8: Chaos Engineering
# ---------------------------------------------------------------------------
# In-memory fault injection state: {"cpu_spike": expiry_ts, ...}. Kept
# intentionally simple (single-process, in-memory) since this drives a demo
# self-healing loop, not a distributed chaos platform.
_CHAOS_STATE = {}


class ChaosRequest(BaseModel):
    duration_seconds: int = 60


def _chaos_active(scenario: str) -> bool:
    expiry = _CHAOS_STATE.get(scenario)
    if expiry and time.time() < expiry:
        return True
    if expiry and time.time() >= expiry:
        _CHAOS_STATE.pop(scenario, None)
        CHAOS_ACTIVE.labels(scenario=scenario).set(0)
    return False


def _start_chaos(scenario: str, duration_seconds: int):
    _CHAOS_STATE[scenario] = time.time() + duration_seconds
    CHAOS_ACTIVE.labels(scenario=scenario).set(1)
    logger.warning(f"[CHAOS] {scenario} injected for {duration_seconds}s")


@app.post("/chaos/cpu-spike")
def chaos_cpu_spike(req: ChaosRequest, token_payload: dict = Depends(verify_token)):
    # Simulated by making every inference call CPU/latency-bound for the
    # duration -- this is what an actual CPU spike would look like from the
    # outside (requests take much longer), which is exactly what the RCA
    # engine's HIGH_LATENCY rule and the existing ML detector watch for.
    _start_chaos("cpu_spike", req.duration_seconds)
    return {"chaos": "cpu-spike", "active_for_seconds": req.duration_seconds}


@app.post("/chaos/memory-leak")
def chaos_memory_leak(req: ChaosRequest, token_payload: dict = Depends(verify_token)):
    # Simulated as a rising error rate over the window (representative of a
    # process degrading toward OOM-kill), which the HIGH_ERRORS rule catches.
    _start_chaos("memory_leak", req.duration_seconds)
    return {"chaos": "memory-leak", "active_for_seconds": req.duration_seconds}


@app.post("/chaos/high-latency")
def chaos_high_latency(req: ChaosRequest, token_payload: dict = Depends(verify_token)):
    _start_chaos("high_latency", req.duration_seconds)
    return {"chaos": "high-latency", "active_for_seconds": req.duration_seconds}


@app.get("/chaos/status")
def chaos_status():
    return {scenario: _chaos_active(scenario) for scenario in ("cpu_spike", "memory_leak", "high_latency")}


class InferenceRequest(BaseModel):
    data_payload: str
    complexity: int = 1  # 1 to 10

class InferenceResponse(BaseModel):
    id: str
    status: str

@app.on_event("startup")
async def startup_event():
    logger.info("Inference Service starting up")

@app.get("/health")
def health_check():
    redis_status = "connected" if redis_client and redis_client.ping() else "disconnected"
    return {"status": "ok", "service": "inference-service", "redis": redis_status}

def process_inference(req: InferenceRequest, req_id: str):
    logger.info(f"Starting inference job: {req_id}")
    QUEUE_DEPTH.inc()
    start_time = time.time()
    try:
        # Simulate processing time based on complexity
        sleep_time = req.complexity * 0.1 * random.uniform(0.8, 1.2)

        error_probability = 0.05  # baseline 5% failure rate

        if _chaos_active("cpu_spike") or _chaos_active("high_latency"):
            sleep_time *= random.uniform(15, 30)
        if _chaos_active("memory_leak"):
            error_probability = 0.35

        time.sleep(sleep_time)

        # Simulate arbitrary errors for alerting
        if random.random() < error_probability:
            raise ValueError("Simulated model prediction error")

        score = random.uniform(0, 100)
        ANOMALY_SCORE.set(score)
        
        result_payload = {
            "req_id": req_id,
            "status": "completed",
            "score": score,
            "data": req.data_payload
        }
        
        # Publish result to Redis
        if redis_client:
            redis_client.rpush("inference_results", json.dumps(result_payload))
            logger.info(f"Published result to queue for job: {req_id}")

        logger.info(f"Processed inference job {req_id} in {sleep_time:.2f}s")
    except Exception as e:
        INFERENCE_ERRORS.inc()
        logger.error(f"Inference error on job {req_id}: {str(e)}")
        if redis_client:
             redis_client.rpush("inference_results", json.dumps({"req_id": req_id, "status": "failed", "error": str(e)}))
    finally:
        QUEUE_DEPTH.dec()
        INFERENCE_LATENCY.observe(time.time() - start_time)


@app.post("/infer", response_model=InferenceResponse)
def infer(req: InferenceRequest, background_tasks: BackgroundTasks, token_payload: dict = Depends(verify_token)):
    req_id = f"inf-{random.randint(1000, 99999)}"
    background_tasks.add_task(process_inference, req, req_id)
    return {
        "id": req_id,
        "status": "queued"
    }
