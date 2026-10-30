from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app import config

engine = create_engine(
    config.DB_URL,
    connect_args={"check_same_thread": False} if config.DB_URL.startswith("sqlite") else {},
)


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Plain SQLAlchemy session context (engine/test friendly, no FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def wipe_database(db: Session | None = None):
    """Drop and recreate every table. Used only by seed.py / POST /imports/reset."""
    from app import models  # noqa: F401  (ensures tables are registered)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)