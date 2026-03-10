"""
observability/tracer.py — Request Tracer
==========================================
Records every request's full pipeline trace.
Without this, you cannot debug production issues.

"AI systems without observability are not production systems."
"""

import structlog
from agent.context import Context
from memory.stores import AuditStore

logger = structlog.get_logger(__name__)


class Tracer:
    """Records full pipeline traces to AuditStore."""

    def __init__(self, audit_store: AuditStore):
        self._audit = audit_store

    async def record(self, context: Context) -> None:
        trace = context.to_trace()
        await self._audit.record(
            tenant_id=context.tenant_id,
            request_id=context.request_id,
            trace=trace,
        )
        logger.info(
            "tracer.recorded",
            request_id=context.request_id,
            status=context.status,
            confidence=context.overall_confidence,
        )