"""
memory/stores.py — Memory Repository Implementations
======================================================
Cascading Fallback: Postgres -> SQLite -> In-Memory
"""

import json
import structlog
from typing import Any, List, Optional
from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, JSON, DateTime, LargeBinary, Boolean, select, delete
from agent.interfaces import MemoryRepositoryInterface

logger = structlog.get_logger(__name__)

Base = declarative_base()

# ── SQLAlchemy Models ───────────────────────────────────────

class User(Base):
    """User accounts table."""
    __tablename__ = "taxyn_users"
    id = Column(String, primary_key=True) # UUID
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True) # Null for OAuth
    full_name = Column(String)
    company_name = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

class OTPRecord(Base):
    """Temporary storage for email verification codes."""
    __tablename__ = "taxyn_otps"
    email = Column(String, primary_key=True)
    otp = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

class StoreItem(Base):
    """Generic key-value store table for SQL databases."""
    __tablename__ = "taxyn_storage"
    key = Column(String, primary_key=True)
    value = Column(JSON)
    tags = Column(String, index=True, nullable=True) 
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

class DocumentBlob(Base):
    """Table to store raw PDF bytes for rendering."""
    __tablename__ = "taxyn_documents"
    request_id = Column(String, primary_key=True)
    content = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

# ─────────────────────────────────────────────────────────────
# SQL REPOSITORY (Postgres / SQLite)
# ─────────────────────────────────────────────────────────────

class SQLRepository(MemoryRepositoryInterface):
    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url)
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("sql_db.initialized")

    async def get(self, key: str) -> Any | None:
        async with self.async_session() as session:
            result = await session.execute(select(StoreItem).where(StoreItem.key == key))
            item = result.scalar_one_or_none()
            return item.value if item else None

    async def set(self, key: str, value: Any, tags: str = None) -> None:
        async with self.async_session() as session:
            item = StoreItem(key=key, value=value, tags=tags)
            await session.merge(item)
            await session.commit()

    async def delete(self, key: str) -> None:
        async with self.async_session() as session:
            await session.execute(delete(StoreItem).where(StoreItem.key == key))
            await session.commit()
            
    async def get_by_tag(self, tag: str) -> list[dict]:
        async with self.async_session() as session:
            result = await session.execute(select(StoreItem).where(StoreItem.tags == tag))
            return [item.value for item in result.scalars().all()]

    async def save_blob(self, request_id: str, content: bytes) -> None:
        async with self.async_session() as session:
            blob = DocumentBlob(request_id=request_id, content=content)
            await session.merge(blob)
            await session.commit()

    async def get_blob(self, request_id: str) -> bytes | None:
        async with self.async_session() as session:
            result = await session.execute(select(DocumentBlob).where(DocumentBlob.request_id == request_id))
            blob = result.scalar_one_or_none()
            return blob.content if blob else None

    # ── User Operations ──
    async def save_user(self, user: User):
        async with self.async_session() as session:
            await session.merge(user)
            await session.commit()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self.async_session() as session:
            res = await session.execute(select(User).where(User.email == email))
            return res.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        async with self.async_session() as session:
            res = await session.execute(select(User).where(User.id == user_id))
            return res.scalar_one_or_none()

    # ── OTP Operations ──
    async def save_otp(self, email: str, otp: str):
        async with self.async_session() as session:
            expiry = datetime.now(UTC) + timedelta(minutes=10)
            record = OTPRecord(email=email, otp=otp, expires_at=expiry)
            await session.merge(record)
            await session.commit()

    async def verify_otp(self, email: str, otp: str) -> bool:
        async with self.async_session() as session:
            res = await session.execute(select(OTPRecord).where(OTPRecord.email == email))
            record = res.scalar_one_or_none()
            if record and record.otp == otp and record.expires_at > datetime.now(UTC):
                await session.execute(delete(OTPRecord).where(OTPRecord.email == email))
                await session.commit()
                return True
            return False

    # ── History Operations ──
    async def get_audit_history(self, tenant_id: str, limit: int = 20) -> List[dict]:
        async with self.async_session() as session:
            prefix = f"audit:{tenant_id}:%"
            result = await session.execute(
                select(StoreItem)
                .where(StoreItem.key.like(prefix))
                .order_by(StoreItem.updated_at.desc())
                .limit(limit)
            )
            return [item.value for item in result.scalars().all()]


# ─────────────────────────────────────────────────────────────
# IN-MEMORY IMPLEMENTATION (Fallback)
# ─────────────────────────────────────────────────────────────

class InMemoryRepository(MemoryRepositoryInterface):
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._tags: dict[str, list[dict]] = {}
        self._blobs: dict[str, bytes] = {}
        self._users: dict[str, User] = {}
        self._otps: dict[str, tuple[str, datetime]] = {}

    async def get(self, key: str) -> Any | None: return self._store.get(key)
    async def set(self, key: str, value: Any, tags: str = None) -> None:
        self._store[key] = value
        if tags:
            if tags not in self._tags: self._tags[tags] = []
            self._tags[tags].append(value)
    async def delete(self, key: str) -> None: self._store.pop(key, None)
    async def get_by_tag(self, tag: str) -> list[dict]: return self._tags.get(tag, [])
    async def save_blob(self, request_id: str, content: bytes) -> None: self._blobs[request_id] = content
    async def get_blob(self, request_id: str) -> bytes | None: return self._blobs.get(request_id)
    async def save_user(self, user: User): self._users[user.email] = user
    async def get_user_by_email(self, email: str): return self._users.get(email)
    async def get_user_by_id(self, user_id: str): 
        return next((u for u in self._users.values() if u.id == user_id), None)
    async def save_otp(self, email: str, otp: str): self._otps[email] = (otp, datetime.now(UTC) + timedelta(minutes=10))
    async def verify_otp(self, email: str, otp: str):
        record = self._otps.get(email)
        if record and record[0] == otp and record[1] > datetime.now(UTC):
            return True
        return False


# ─────────────────────────────────────────────────────────────
# DOMAIN STORES
# ─────────────────────────────────────────────────────────────

class UserStore:
    def __init__(self, repo: SQLRepository | InMemoryRepository):
        self._repo = repo
    async def create_user(self, user: User): await self._repo.save_user(user)
    async def get_by_email(self, email: str): return await self._repo.get_user_by_email(email)
    async def get_by_id(self, user_id: str): return await self._repo.get_user_by_id(user_id)
    async def initiate_otp(self, email: str, otp: str): await self._repo.save_otp(email, otp)
    async def verify_otp(self, email: str, otp: str): return await self._repo.verify_otp(email, otp)

class SchemaStore:
    DEFAULT_SCHEMAS = {
        "invoice": {
            "invoice_number": "string",
            "vendor_name": "string",
            "amount": "number",
            "gst_amount": "number",
            "date": "date",
        }
    }
    def __init__(self, repo: MemoryRepositoryInterface): self._repo = repo
    async def get_schema(self, tenant_id: str, doc_type: str) -> dict[str, Any]:
        key = f"schema:{tenant_id}:{doc_type}"
        schema = await self._repo.get(key)
        return schema if schema else self.DEFAULT_SCHEMAS.get(doc_type, {})
    async def set_schema(self, tenant_id: str, doc_type: str, schema: dict) -> None:
        await self._repo.set(f"schema:{tenant_id}:{doc_type}", schema)

class CorrectionStore:
    def __init__(self, repo: MemoryRepositoryInterface): self._repo = repo
    async def save_correction(self, tenant_id: str, request_id: str, vendor_name: str, field: str, original: Any, corrected: Any) -> None:
        tag = f"vendor:{vendor_name.lower().strip()}"
        key = f"correction:{tenant_id}:{request_id}:{field}"
        await self._repo.set(key, {
            "field": field, "original": original, "corrected": corrected, 
            "vendor": vendor_name, "tenant_id": tenant_id
        }, tags=tag)
    async def get_vendor_memory(self, vendor_name: str) -> list[dict]:
        if not vendor_name: return []
        tag = f"vendor:{vendor_name.lower().strip()}"
        if hasattr(self._repo, 'get_by_tag'): return await self._repo.get_by_tag(tag)
        return []

class AuditStore:
    def __init__(self, repo: MemoryRepositoryInterface): self._repo = repo
    async def record(self, tenant_id: str, request_id: str, trace: dict) -> None:
        await self._repo.set(f"audit:{tenant_id}:{request_id}", trace)
    async def get(self, tenant_id: str, request_id: str) -> dict | None:
        return await self._repo.get(f"audit:{tenant_id}:{request_id}")
    async def get_history(self, tenant_id: str, limit: int = 20):
        if hasattr(self._repo, 'get_audit_history'):
            return await self._repo.get_audit_history(tenant_id, limit)
        return []

class DocumentStore:
    def __init__(self, repo: MemoryRepositoryInterface): self._repo = repo
    async def save(self, request_id: str, content: bytes) -> None:
        if hasattr(self._repo, 'save_blob'): await self._repo.save_blob(request_id, content)
    async def get(self, request_id: str) -> bytes | None:
        if hasattr(self._repo, 'get_blob'): return await self._repo.get_blob(request_id)
        return None
