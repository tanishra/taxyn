"""
output/hitl_queue.py — Human-in-the-Loop Queue
================================================
When confidence < threshold, documents go here.
A human reviewer can inspect, correct, and approve.

In production: backed by Redis queue or a DB table
with a simple review dashboard.

Observer Pattern: HITLQueue is an observer on AgentLoop output.
"""

import structlog
from agent.context import Context
from agent.context import ProcessingStatus
from agent.interfaces import MemoryRepositoryInterface

logger = structlog.get_logger(__name__)


class HITLQueue:
    """
    Routes low-confidence extraction results to human review.
    Simple in-memory queue for development.
    Production: replace with Redis list or Postgres table.
    """

    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo
        self._tag = "hitl_pending"
        self._prefix = "hitl:"

    async def enqueue(self, context: Context) -> None:
        """Add a document to the human review queue."""
        item = {
            "request_id": context.request_id,
            "tenant_id": context.tenant_id,
            "filename": context.filename,
            "doc_type": str(context.doc_type),
            "partial_data": context.extracted_data,
            "confidence": context.overall_confidence,
            "confidence_scores": context.confidence_scores,
            "compliance_flags": context.compliance_flags,
            "status": ProcessingStatus.NEEDS_REVIEW.value,
        }
        await self._repo.set(f"{self._prefix}{context.request_id}", item, tags=self._tag)
        logger.info(
            "hitl_queue.enqueued",
            request_id=context.request_id,
            confidence=context.overall_confidence,
        )

    async def get_pending(self) -> list[dict]:
        """Get all pending review items."""
        items = await self._repo.get_by_tag(self._tag) if hasattr(self._repo, "get_by_tag") else []
        return [item for item in items if isinstance(item, dict)]

    async def resolve(self, request_id: str, corrected_data: dict) -> bool:
        """Mark a review item as resolved with corrected data."""
        payload = await self._repo.get(f"{self._prefix}{request_id}")
        if isinstance(payload, dict):
            payload["status"] = ProcessingStatus.COMPLETED.value
            payload["resolved_data"] = corrected_data
            await self._repo.set(f"{self._prefix}{request_id}:resolved", payload, tags="hitl_resolved")
        await self._repo.delete(f"{self._prefix}{request_id}")
        logger.info("hitl_queue.resolved", request_id=request_id)
        return True
