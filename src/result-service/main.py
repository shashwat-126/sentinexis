import os
import json
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy import text
import datetime
from shared.logger import setup_logger
from shared.auth import verify_token
from shared.db import get_db, Base, engine
from prometheus_fastapi_instrumentator import Instrumentator
import redis

app = FastAPI(title="Result Service")
logger = setup_logger("result-service")

# Define our DB model here
class InferenceResult(Base):
    __tablename__ = "inference_results"
    id = Column(Integer, primary_key=True, index=True)
    req_id = Column(String, unique=True, index=True)
    status = Column(String)
    score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = None

Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
async def startup_event():
    logger.info("Result Service starting up")
    global redis_client
    try:
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # Test connection
        redis_client.ping()
        # Start background task to consume redis queue
        asyncio.create_task(consume_results())
        logger.info("Started Redis consumer loop for inference_results")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")

async def consume_results():
    if not redis_client:
        return
    
    # We use a simple while loop here, but in production consider a robust retry/dead-letter-queue pattern
    while True:
        try:
            # Short blocking pop
            res = redis_client.blpop("inference_results", timeout=5)
            if res:
                _, data_str = res
                data = json.loads(data_str)
                save_result(data)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error consuming result: {e}")
            await asyncio.sleep(5)

def save_result(data: dict):
    from shared.db import SessionLocal
    db = SessionLocal()
    try:
        req_id = data.get("req_id")
        status = data.get("status")
        score = data.get("score")
        
        # Avoid duplicate inserts
        existing = db.query(InferenceResult).filter(InferenceResult.req_id == req_id).first()
        if not existing:
            result_record = InferenceResult(req_id=req_id, status=status, score=score)
            db.add(result_record)
            db.commit()
            logger.info(f"Saved result for {req_id} to database")
        else:
            existing.status = status
            existing.score = score
            db.commit()
            logger.info(f"Updated result for {req_id} in database")
    except Exception as e:
        logger.error(f"Database save error: {e}")
        db.rollback()
    finally:
        db.close()

@app.get("/health")
def health_check():
    db_status = "ok"
    try:
        from shared.db import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    finally:
        if 'db' in locals():
            db.close()

    redis_status = "connected" if redis_client and redis_client.ping() else "disconnected"
    return {"status": "ok", "service": "result-service", "redis": redis_status, "db": db_status}

@app.get("/")
def list_results(db: Session = Depends(get_db), token: dict = Depends(verify_token), limit: int = 50):
    records = db.query(InferenceResult).order_by(InferenceResult.created_at.desc()).limit(limit).all()
    return [{"req_id": r.req_id, "status": r.status, "score": r.score} for r in records]

@app.get("/{req_id}")
def get_result(req_id: str, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    record = db.query(InferenceResult).filter(InferenceResult.req_id == req_id).first()
    if not record:
        return {"status": "not_found"}
    return {
        "req_id": record.req_id,
        "status": record.status,
        "score": record.score,
        "created_at": record.created_at
    }

