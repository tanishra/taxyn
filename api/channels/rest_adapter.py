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

from fastapi import UploadFile
from agent.context import Context, DocType
from agent.interfaces import ChannelInterface
from memory.stores import SchemaStore


class RestAdapter(ChannelInterface):
    """
    Converts HTTP multipart file upload into a Context object.
    """

    def __init__(self, schema_store: SchemaStore):
        self._schema_store = schema_store

    async def parse_request(self, raw_input: dict) -> Context:
        file: UploadFile = raw_input["file"]
        tenant_id: str = raw_input["tenant_id"]
        doc_type_hint: str = raw_input.get("doc_type", "unknown")

        raw_bytes = await file.read()

        # Map string to DocType enum
        doc_type = DocType(doc_type_hint) if doc_type_hint in DocType._value2member_map_ else DocType.UNKNOWN

        # Load tenant's custom schema from memory
        schema = await self._schema_store.get_schema(tenant_id, doc_type_hint)

        context = Context(
            tenant_id=tenant_id,
            doc_type=doc_type,
            raw_bytes=raw_bytes,
            filename=file.filename or "document.pdf",
            extraction_schema=schema,
        )

        return context