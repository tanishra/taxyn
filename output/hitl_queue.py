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

logger = structlog.get_logger(__name__)


class HITLQueue:
    """
    Routes low-confidence extraction results to human review.
    Simple in-memory queue for development.
    Production: replace with Redis list or Postgres table.
    """

    def __init__(self):
        self._queue: list[dict] = []

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
        }
        self._queue.append(item)
        logger.info(
            "hitl_queue.enqueued",
            request_id=context.request_id,
            confidence=context.overall_confidence,
            queue_size=len(self._queue),
        )

    async def get_pending(self) -> list[dict]:
        """Get all pending review items."""
        return self._queue.copy()

    async def resolve(self, request_id: str, corrected_data: dict) -> bool:
        """Mark a review item as resolved with corrected data."""
        self._queue = [item for item in self._queue if item["request_id"] != request_id]
        logger.info("hitl_queue.resolved", request_id=request_id)
        return True