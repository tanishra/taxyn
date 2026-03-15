"""
api/channels/rest_adapter.py — REST Channel Adapter
=====================================================
Adapter Pattern: Converts FastAPI HTTP request into a Context object.
The AgentLoop never sees HTTP — it only sees Context.

This means the same AgentLoop can work for:
- REST API (this file)
- WhatsApp webhook (WhatsAppAdapter)
- Email (EmailAdapter)
- etc.
"""

import structlog
import uuid # Added for generating request_id
from typing import Optional
from fastapi import UploadFile
from agent.context import Context, DocType
from agent.interfaces import ChannelInterface
from memory.stores import SchemaStore

logger = structlog.get_logger(__name__)


class RestAdapter(ChannelInterface):
    """
    Converts HTTP multipart file upload into a Context object,
    or directly processes raw_bytes for split documents.
    """

    def __init__(self, schema_store: SchemaStore):
        self._schema_store = schema_store

    async def parse_request(self, raw_input: dict) -> Context:
        tenant_id: str = raw_input["tenant_id"]
        doc_type_hint: str = raw_input.get("doc_type", "unknown")
        filename: str = raw_input.get("filename", "document.pdf")
        request_id: str = raw_input.get("request_id") or str(uuid.uuid4()) # Use existing or generate new

        raw_bytes: bytes
        if "file" in raw_input and isinstance(raw_input["file"], UploadFile):
            raw_bytes = await raw_input["file"].read()
            filename = raw_input["file"].filename or filename
        elif "file_bytes" in raw_input and isinstance(raw_input["file_bytes"], bytes):
            raw_bytes = raw_input["file_bytes"]
        else:
            raise ValueError("Either 'file' (UploadFile) or 'file_bytes' (bytes) must be provided")


        # Map string to DocType enum
        doc_type = DocType(doc_type_hint) if doc_type_hint in DocType._value2member_map_ else DocType.UNKNOWN

        # Load tenant's custom schema from memory
        schema = await self._schema_store.get_schema(tenant_id, doc_type_hint)

        metadata = {}
        # ── RECONCILIATION: Load stored portal data or use mock for demo ────
        if doc_type == DocType.RECONCILIATION:
            stored_portal = await self._schema_store.get_schema(tenant_id, "portal_data")
            if stored_portal and "records" in stored_portal:
                logger.info("rest_adapter.using_real_portal_data", count=len(stored_portal["records"]))
                metadata["portal_data"] = stored_portal["records"]
            else:
                logger.warning("rest_adapter.no_portal_data_found_using_mock")
                metadata["portal_data"] = [
                    {"invoice_number": "INV-2026-1042", "gstin": "22AAAAA0000A1Z5", "amount": 59000.0},
                    {"invoice_number": "INV-9999", "gstin": "07AAAAA0000A1Z5", "amount": 1000.0}
                ]
        # ────────────────────────────────────────────────────────────────

        context = Context(
            request_id=request_id, # Use generated or passed ID
            tenant_id=tenant_id,
            doc_type=doc_type,
            raw_bytes=raw_bytes,
            filename=filename,
            extraction_schema=schema,
            metadata=metadata
        )

        return context
