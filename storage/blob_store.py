from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from agent.interfaces import MemoryRepositoryInterface


class BlobStore(ABC):
    @abstractmethod
    async def save(self, request_id: str, content: bytes, tenant_id: str | None = None, filename: str | None = None) -> None:
        ...

    @abstractmethod
    async def get(self, request_id: str) -> bytes | None:
        ...

    @abstractmethod
    async def get_meta(self, request_id: str) -> dict[str, Any] | None:
        ...


class DatabaseBlobStore(BlobStore):
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def save(self, request_id: str, content: bytes, tenant_id: str | None = None, filename: str | None = None) -> None:
        if hasattr(self._repo, "save_blob"):
            await self._repo.save_blob(request_id, content, tenant_id=tenant_id, filename=filename)
        await self._repo.set(
            f"document_meta:{request_id}",
            {"request_id": request_id, "tenant_id": tenant_id, "filename": filename},
            tags="document_meta",
        )

    async def get(self, request_id: str) -> bytes | None:
        if hasattr(self._repo, "get_blob"):
            return await self._repo.get_blob(request_id)
        return None

    async def get_meta(self, request_id: str) -> dict[str, Any] | None:
        if hasattr(self._repo, "get_blob_meta"):
            meta = await self._repo.get_blob_meta(request_id)
            if meta:
                return meta
        payload = await self._repo.get(f"document_meta:{request_id}")
        return payload if isinstance(payload, dict) else None


class FileSystemBlobStore(BlobStore):
    def __init__(self, repo: MemoryRepositoryInterface, base_path: str):
        self._repo = repo
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _blob_path(self, request_id: str) -> Path:
        return self._base_path / f"{request_id}.pdf"

    async def save(self, request_id: str, content: bytes, tenant_id: str | None = None, filename: str | None = None) -> None:
        path = self._blob_path(request_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        # Keep a DB copy when supported so deployed previews survive filesystem drift
        # and older database-backed documents remain accessible after storage-mode changes.
        if hasattr(self._repo, "save_blob"):
            await self._repo.save_blob(request_id, content, tenant_id=tenant_id, filename=filename)
        await self._repo.set(
            f"document_meta:{request_id}",
            {
                "request_id": request_id,
                "tenant_id": tenant_id,
                "filename": filename,
                "storage_mode": "filesystem",
                "path": str(path),
            },
            tags="document_meta",
        )

    async def get(self, request_id: str) -> bytes | None:
        path = self._blob_path(request_id)
        if not path.exists():
            payload = await self.get_meta(request_id)
            candidate_path = Path(str(payload.get("path", ""))) if isinstance(payload, dict) and payload.get("path") else None
            if candidate_path and candidate_path.exists():
                return candidate_path.read_bytes()
            if hasattr(self._repo, "get_blob"):
                content = await self._repo.get_blob(request_id)
                if content:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    return content
            return None
        return path.read_bytes()

    async def get_meta(self, request_id: str) -> dict[str, Any] | None:
        payload = await self._repo.get(f"document_meta:{request_id}")
        if isinstance(payload, dict):
            return payload
        if hasattr(self._repo, "get_blob_meta"):
            meta = await self._repo.get_blob_meta(request_id)
            if isinstance(meta, dict):
                meta.setdefault("storage_mode", "database")
                return meta
        return None
