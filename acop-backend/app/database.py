"""
SQLAlchemy engine, session, and declarative base.
Works with either PostgreSQL or SQLite (set via DATABASE_URL).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call on startup (dev) or use Alembic migrations (prod)."""
    from app.models import cluster, incident, remediation, metrics  # noqa: F401 ensure models registered
    Base.metadata.create_all(bind=engine)
