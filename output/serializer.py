"""
output/serializer.py — Response Serializer
============================================
Formats Context into clean API responses.
Single Responsibility: presentation layer only.
"""

from datetime import datetime
from agent.context import Context, ProcessingStatus


class ResponseSerializer:
    """Converts internal Context into API response dicts."""

    def success_response(self, context: Context) -> dict:
        return {
            "status": "completed",
            "request_id": context.request_id,
            "doc_type": str(context.doc_type).split(".")[-1],
            "filename": context.filename,
            "extracted_data": context.extracted_data,
            "confidence": context.overall_confidence,
            "compliance_flags": context.compliance_flags,
            "processing_time_ms": context.processing_time_ms,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def needs_review_response(self, context: Context) -> dict:
        return {
            "status": "needs_review",
            "request_id": context.request_id,
            "doc_type": str(context.doc_type).split(".")[-1],
            "filename": context.filename,
            "message": (
                f"Confidence {context.overall_confidence:.0%} is below threshold. "
                "Sent to human review queue."
            ),
            "partial_data": context.extracted_data,
            "confidence": context.overall_confidence,
            "compliance_flags": context.compliance_flags,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def queued_response(self, request_id: str, filename: str, doc_type: str) -> dict:
        return {
            "status": "queued",
            "request_id": request_id,
            "filename": filename,
            "doc_type": doc_type,
            "message": "Document accepted and queued for background processing.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def error_response(self, context: Context, error: str) -> dict:
        return {
            "status": "failed",
            "request_id": context.request_id,
            "filename": context.filename,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }
