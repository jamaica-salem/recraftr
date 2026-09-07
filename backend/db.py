"""Database abstraction layer for Recraftr using SQLAlchemy 2.0 Async (asyncpg).

Supports PostgreSQL connection pooling (ideal for Supabase Transaction Pooler)
and provides declarative ORM models matching schema.sql.
"""
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Dict, Any, List
import uuid

from sqlalchemy import (
    Column, String, Text, Integer, Numeric, DateTime, ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/recraftr"
)

# Standardize scheme for asyncpg
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configure async engine with pooling suited for Supabase Pooler
engine_kwargs: Dict[str, Any] = {
    "echo": False,
    "pool_pre_ping": True,
}

# Only add pool size parameters if using pooled connection (not null pool)
if "pooler.supabase.com" in DATABASE_URL:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 5,
        "pool_timeout": 30,
        "pool_recycle": 1800,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    resumes = relationship("Resume", back_populates="profile", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="profile", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="profile", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="profile", cascade="all, delete-orphan")
    credit_transactions = relationship("CreditTransaction", back_populates="profile", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    storage_path = Column(String, nullable=True)
    char_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="resumes")
    analyses = relationship("Analysis", back_populates="resume")


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(PG_UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True)
    resume_filename = Column(String, nullable=True)
    job_title = Column(String, nullable=False)
    job_description = Column(Text, nullable=False)
    analysis = Column(JSONB, nullable=True)
    model = Column(String, default="gemini-3.5-flash")
    optimized_resume = Column(Text, nullable=True)
    predicted_ats_score = Column(Integer, nullable=True)
    changes_summary = Column(JSONB, default=list)
    cover_letter = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="analyses")
    resume = relationship("Resume", back_populates="analyses")


class Application(Base):
    __tablename__ = "applications"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    job_title = Column(String, nullable=False)
    company_name = Column(String, default="Target Company", nullable=False)
    location = Column(String, default="", nullable=True)
    status = Column(String, default="applied", nullable=False)
    ats_score = Column(Integer, nullable=True)
    job_description = Column(Text, default="", nullable=True)
    optimized_resume = Column(Text, default="", nullable=True)
    cover_letter = Column(Text, default="", nullable=True)
    notes = Column(Text, default="", nullable=True)
    resume_filename = Column(String, default="", nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="applications")


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    paymongo_payment_id = Column(String, unique=True, nullable=True, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, default="PHP", nullable=False)
    package_name = Column(String, nullable=False)
    credits_granted = Column(Integer, default=0, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="purchases")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    action_type = Column(String, nullable=False)
    balance_after = Column(Integer, nullable=False)
    metadata_json = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="credit_transactions")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
