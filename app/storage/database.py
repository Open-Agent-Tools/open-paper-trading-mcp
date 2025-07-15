from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from typing import Generator

# Convert asyncpg URL to sync psycopg2 URL for synchronous operations
database_url = settings.DATABASE_URL
if "+asyncpg" in database_url:
    database_url = database_url.replace("+asyncpg", "")

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
