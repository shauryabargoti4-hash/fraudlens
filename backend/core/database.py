import datetime
from typing import Generator
from sqlalchemy import create_engine, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from backend.core.config import get_settings
from backend.core.logging_config import logger

settings = get_settings()

# Engine configuration: SQLite requires check_same_thread=False for multi-threaded FastAPI workers
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

# Declarative base class
Base = declarative_base()


class TimestampMixin:
    """Provides created_at and updated_at timestamps for models."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initializes all database tables registered with the Base metadata."""
    logger.info("Initializing ClauseGuard database tables...")
    # Import all models so metadata knows about them before create_all
    import backend.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
