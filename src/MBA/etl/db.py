"""
Database connection utilities for MBA system.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..core.settings import settings
from ..core.logging_config import get_logger

logger = get_logger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.get_database_url(),
    pool_size=settings.rds_pool_size,
    max_overflow=settings.rds_pool_max_overflow,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def connect():
    """
    Get database connection context manager.
    
    Yields:
        Connection object for executing queries
    """
    connection = engine.connect()
    try:
        yield connection
    finally:
        connection.close()

@contextmanager
def get_session():
    """
    Get database session context manager.
    
    Yields:
        SQLAlchemy session for ORM operations
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()