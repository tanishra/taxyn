"""
memory/stores.py — Memory Repository Implementations
======================================================
Cascading Fallback: Postgres -> SQLite -> In-Memory
"""

import json
import structlog
from typing import Any
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, JSON, DateTime, LargeBinary, select, delete
from agent.interfaces import MemoryRepositoryInterface

logger = structlog.get_logger(__name__)

Base = declarative_base()

# ── SQLAlchemy Models ───────────────────────────────────────

class StoreItem(Base):
    """Generic key-value store table for SQL databases."""
    __tablename__ = "taxyn_storage"
    key = Column(String, primary_key=True)
    value = Column(JSON)
    # Added tags for searching (e.g. searching corrections by vendor name)
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
            
    # Helper for searching by tags (Vendor Memory)
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


# ─────────────────────────────────────────────────────────────
# IN-MEMORY IMPLEMENTATION (The final fallback)
# ─────────────────────────────────────────────────────────────

class InMemoryRepository(MemoryRepositoryInterface):
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._tags: dict[str, list[dict]] = {}
        self._blobs: dict[str, bytes] = {}

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any, tags: str = None) -> None:
        self._store[key] = value
        if tags:
            if tags not in self._tags: self._tags[tags] = []
            self._tags[tags].append(value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def get_by_tag(self, tag: str) -> list[dict]:
        return self._tags.get(tag, [])

    async def save_blob(self, request_id: str, content: bytes) -> None:
        self._blobs[request_id] = content

    async def get_blob(self, request_id: str) -> bytes | None:
        return self._blobs.get(request_id)


# ─────────────────────────────────────────────────────────────
# DOMAIN STORES
# ─────────────────────────────────────────────────────────────

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

    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def get_schema(self, tenant_id: str, doc_type: str) -> dict[str, Any]:
        key = f"schema:{tenant_id}:{doc_type}"
        schema = await self._repo.get(key)
        return schema if schema else self.DEFAULT_SCHEMAS.get(doc_type, {})

    async def set_schema(self, tenant_id: str, doc_type: str, schema: dict) -> None:
        await self._repo.set(f"schema:{tenant_id}:{doc_type}", schema)


class CorrectionStore:
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def save_correction(self, tenant_id: str, request_id: str, vendor_name: str, field: str, original: Any, corrected: Any) -> None:
        # Tagging by vendor name for the learning flywheel
        tag = f"vendor:{vendor_name.lower().strip()}"
        key = f"correction:{tenant_id}:{request_id}:{field}"
        await self._repo.set(key, {
            "field": field, 
            "original": original, 
            "corrected": corrected, 
            "vendor": vendor_name,
            "tenant_id": tenant_id
        }, tags=tag)

    async def get_vendor_memory(self, vendor_name: str) -> list[dict]:
        if not vendor_name: return []
        tag = f"vendor:{vendor_name.lower().strip()}"
        # Only SQLRepo and updated InMemoryRepo support get_by_tag
        if hasattr(self._repo, 'get_by_tag'):
            return await self._repo.get_by_tag(tag)
        return []


class AuditStore:
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def record(self, tenant_id: str, request_id: str, trace: dict) -> None:
        await self._repo.set(f"audit:{tenant_id}:{request_id}", trace)

    async def get(self, tenant_id: str, request_id: str) -> dict | None:
        return await self._repo.get(f"audit:{tenant_id}:{request_id}")


class DocumentStore:
    """Store for raw PDF document bytes."""
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def save(self, request_id: str, content: bytes) -> None:
        if hasattr(self._repo, 'save_blob'):
            await self._repo.save_blob(request_id, content)

    async def get(self, request_id: str) -> bytes | None:
        if hasattr(self._repo, 'get_blob'):
            return await self._repo.get_blob(request_id)
        return None
