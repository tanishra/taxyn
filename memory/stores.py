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
from sqlalchemy import Column, String, JSON, DateTime, LargeBinary, Boolean, select, delete, text
from agent.interfaces import MemoryRepositoryInterface
from storage.blob_store import BlobStore, DatabaseBlobStore, FileSystemBlobStore

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
    contact_phone = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    company_pan = Column(String, nullable=True)
    address_line1 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
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
    tenant_id = Column(String, index=True, nullable=True)
    filename = Column(String, nullable=True)
    content = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

# ─────────────────────────────────────────────────────────────
# SQL REPOSITORY (Postgres / SQLite)
# ─────────────────────────────────────────────────────────────

class SQLRepository(MemoryRepositoryInterface):
    def __init__(self, db_url: str):
        engine_kwargs = {"pool_pre_ping": True}
        if "sqlite" not in db_url:
            engine_kwargs.update(
                {
                    "pool_recycle": 300,
                    "pool_size": 10,
                    "max_overflow": 20,
                }
            )
        self.engine = create_async_engine(db_url, **engine_kwargs)
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await self._ensure_user_profile_columns(conn)
            await self._ensure_document_columns(conn)
        logger.info("sql_db.initialized")

    async def _ensure_user_profile_columns(self, conn):
        required_columns = {
            "contact_phone": "VARCHAR",
            "designation": "VARCHAR",
            "company_pan": "VARCHAR",
            "address_line1": "VARCHAR",
            "city": "VARCHAR",
            "state": "VARCHAR",
            "pincode": "VARCHAR",
            "is_admin": "BOOLEAN DEFAULT FALSE",
        }

        dialect = conn.dialect.name
        if dialect == "sqlite":
            result = await conn.execute(text("PRAGMA table_info('taxyn_users')"))
            existing = {row[1] for row in result.fetchall()}
            for column_name, column_type in required_columns.items():
                if column_name not in existing:
                    await conn.execute(text(f"ALTER TABLE taxyn_users ADD COLUMN {column_name} {column_type}"))
            return

        if dialect == "postgresql":
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'taxyn_users'
                    """
                )
            )
            existing = {row[0] for row in result.fetchall()}
            for column_name, column_type in required_columns.items():
                if column_name not in existing:
                    await conn.execute(
                        text(f"ALTER TABLE taxyn_users ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
                    )

    async def _ensure_document_columns(self, conn):
        required_columns = {
            "tenant_id": "VARCHAR",
            "filename": "VARCHAR",
        }

        dialect = conn.dialect.name
        if dialect == "sqlite":
            result = await conn.execute(text("PRAGMA table_info('taxyn_documents')"))
            existing = {row[1] for row in result.fetchall()}
            for column_name, column_type in required_columns.items():
                if column_name not in existing:
                    await conn.execute(text(f"ALTER TABLE taxyn_documents ADD COLUMN {column_name} {column_type}"))
            return

        if dialect == "postgresql":
            result = await conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'taxyn_documents'
                    """
                )
            )
            existing = {row[0] for row in result.fetchall()}
            for column_name, column_type in required_columns.items():
                if column_name not in existing:
                    await conn.execute(
                        text(f"ALTER TABLE taxyn_documents ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
                    )

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

    async def save_blob(
        self,
        request_id: str,
        content: bytes,
        tenant_id: str | None = None,
        filename: str | None = None,
    ) -> None:
        async with self.async_session() as session:
            blob = DocumentBlob(
                request_id=request_id,
                tenant_id=tenant_id,
                filename=filename,
                content=content,
            )
            await session.merge(blob)
            await session.commit()

    async def get_blob(self, request_id: str) -> bytes | None:
        async with self.async_session() as session:
            result = await session.execute(select(DocumentBlob).where(DocumentBlob.request_id == request_id))
            blob = result.scalar_one_or_none()
            return blob.content if blob else None

    async def get_blob_meta(self, request_id: str) -> dict[str, Any] | None:
        async with self.async_session() as session:
            result = await session.execute(select(DocumentBlob).where(DocumentBlob.request_id == request_id))
            blob = result.scalar_one_or_none()
            if not blob:
                return None
            return {
                "request_id": blob.request_id,
                "tenant_id": blob.tenant_id,
                "filename": blob.filename,
                "created_at": blob.created_at.isoformat() if blob.created_at else None,
            }

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
            rows = []
            for item in result.scalars().all():
                value = dict(item.value or {})
                if "created_at" not in value and item.updated_at:
                    value["created_at"] = item.updated_at.isoformat()
                if "confidence" not in value and "overall_confidence" in value:
                    value["confidence"] = value.get("overall_confidence", 0.0)
                rows.append(value)
            return rows


# ─────────────────────────────────────────────────────────────
# IN-MEMORY IMPLEMENTATION (Fallback)
# ─────────────────────────────────────────────────────────────

class InMemoryRepository(MemoryRepositoryInterface):
    def __init__(self):
        self._store: dict[str, Any] = {}
        self._tags: dict[str, dict[str, Any]] = {}
        self._blobs: dict[str, Any] = {}
        self._users: dict[str, User] = {}
        self._otps: dict[str, tuple[str, datetime]] = {}

    async def get(self, key: str) -> Any | None: return self._store.get(key)
    async def set(self, key: str, value: Any, tags: str = None) -> None:
        self._store[key] = value
        if tags:
            if tags not in self._tags:
                self._tags[tags] = {}
            self._tags[tags][key] = value
    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        for tagged_items in self._tags.values():
            tagged_items.pop(key, None)
    async def get_by_tag(self, tag: str) -> list[dict]:
        return list(self._tags.get(tag, {}).values())
    async def save_blob(
        self,
        request_id: str,
        content: bytes,
        tenant_id: str | None = None,
        filename: str | None = None,
    ) -> None:
        self._blobs[request_id] = {
            "content": content,
            "tenant_id": tenant_id,
            "filename": filename,
            "created_at": datetime.now(UTC).isoformat(),
        }
    async def get_blob(self, request_id: str) -> bytes | None:
        blob = self._blobs.get(request_id)
        if isinstance(blob, dict):
            return blob.get("content")
        return blob
    async def get_blob_meta(self, request_id: str) -> dict[str, Any] | None:
        blob = self._blobs.get(request_id)
        if not blob:
            return None
        return {
            "request_id": request_id,
            "tenant_id": blob.get("tenant_id"),
            "filename": blob.get("filename"),
            "created_at": blob.get("created_at"),
        }
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
            "supplier_gstin": "string",
            "buyer_gstin": "string",
            "amount": "number",
            "taxable_value": "number",
            "gst_amount": "number",
            "cgst": "number",
            "sgst": "number",
            "igst": "number",
            "gst_rate": "number",
            "place_of_supply": "string",
            "hsn_sac": "string",
            "invoice_type": "string",
            "date": "date",
            "due_date": "date",
            "line_items": "array",
        },
        "gst_return": {
            "return_type": "string",
            "gstin": "string",
            "period": "string",
            "filing_date": "date",
            "b2b_taxable_value": "number",
            "b2c_taxable_value": "number",
            "export_taxable_value": "number",
            "total_taxable_value": "number",
            "igst": "number",
            "cgst": "number",
            "sgst": "number",
            "tax_liability": "number",
            "tax_paid": "number",
            "interest_amount": "number",
            "late_fee": "number",
        },
        "bank_statement": {
            "bank_name": "string",
            "account_holder_name": "string",
            "account_number": "string",
            "ifsc": "string",
            "currency": "string",
            "period_start": "date",
            "period_end": "date",
            "period": "string",
            "opening_balance": "number",
            "closing_balance": "number",
            "transactions": "array",
        },
        "tds_certificate": {
            "pan": "string",
            "tan": "string",
            "deductor_name": "string",
            "section_code": "string",
            "certificate_number": "string",
            "assessment_year": "string",
            "period": "string",
            "deduction_date": "date",
            "challan_bsr": "string",
            "amount_paid": "number",
            "tds_deducted": "number",
        },
        "reconciliation": {
            "invoice_number": "string",
            "vendor_name": "string",
            "vendor_gstin": "string",
            "invoice_date": "date",
            "amount": "number",
            "taxable_value": "number",
            "igst": "number",
            "cgst": "number",
            "sgst": "number",
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


class ProcessingJobStore:
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def create_job(self, request_id: str, tenant_id: str, filename: str, doc_type: str) -> dict[str, Any]:
        payload = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "doc_type": doc_type,
            "status": "queued",
            "created_at": datetime.now(UTC).isoformat(),
        }
        await self._repo.set(f"job:{request_id}", payload, tags="processing_job")
        return payload

    async def update_job(self, request_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_job(request_id) or {"request_id": request_id}
        current.update(updates)
        await self._repo.set(f"job:{request_id}", current, tags="processing_job")
        return current

    async def get_job(self, request_id: str) -> dict[str, Any] | None:
        payload = await self._repo.get(f"job:{request_id}")
        return payload if isinstance(payload, dict) else None

    async def list_jobs(self) -> list[dict[str, Any]]:
        if hasattr(self._repo, "get_by_tag"):
            rows = await self._repo.get_by_tag("processing_job")
            return [row for row in rows if isinstance(row, dict)]
        return []

class DocumentStore:
    def __init__(
        self,
        repo: MemoryRepositoryInterface,
        storage_mode: str = "database",
        storage_path: str = "./data/documents",
    ):
        self._repo = repo
        if storage_mode == "filesystem":
            self._blob_store: BlobStore = FileSystemBlobStore(repo, storage_path)
        else:
            self._blob_store = DatabaseBlobStore(repo)
    async def save(
        self,
        request_id: str,
        content: bytes,
        tenant_id: str | None = None,
        filename: str | None = None,
    ) -> None:
        await self._blob_store.save(request_id, content, tenant_id=tenant_id, filename=filename)
    async def get(self, request_id: str) -> bytes | None:
        return await self._blob_store.get(request_id)
    async def get_meta(self, request_id: str) -> dict | None:
        return await self._blob_store.get_meta(request_id)
