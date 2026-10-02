import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from shared.logger import setup_logger

logger = setup_logger("shared.db")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/aiops")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    logger.error(f"Failed to initialize database engine: {e}")
    # Still define Base to avoid import errors, app will crash on DB connect anyway
    Base = declarative_base()
    SessionLocal = None

def get_db():
    if not SessionLocal:
        raise Exception("Database session factory is not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
