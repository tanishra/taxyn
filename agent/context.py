"""
context.py — The Explicit Context Object
==========================================
This is the single data container that flows through the entire
AgentLoop pipeline. It is passed EXPLICITLY to every component.

Why? Because hidden state causes bugs that are impossible to debug.
With an explicit context, you can log/trace/reproduce any request.

Think of it like a tray a waiter carries — everything needed for
one order is on that tray, visible and trackable.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


class DocType(str, Enum):
    INVOICE = "invoice"
    GST_RETURN = "gst_return"
    BANK_STATEMENT = "bank_statement"
    TDS_CERTIFICATE = "tds_certificate"
    RECONCILIATION = "reconciliation"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"   # Confidence below threshold → HITL
    FAILED = "failed"


@dataclass
class ToolResult:
    """
    What every Tool returns. Typed and structured.
    Never return raw strings from tools — always use this.
    """
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    confidence: float = 1.0                     # 0.0 → 1.0


@dataclass
class Context:
    """
    Immutable-by-convention context object.
    Created once per request. Passed everywhere explicitly.

    DO NOT mutate after creation — append to tool_results instead.
    """
    # ── Identity ───────────────────────────────────────────
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""                          # Which CA firm / client

    # ── Document ───────────────────────────────────────────
    doc_type: DocType = DocType.UNKNOWN
    raw_bytes: bytes = b""                       # Original uploaded file
    filename: str = ""

    # ── Schema (loaded from SchemaStore per tenant) ────────
    extraction_schema: dict[str, Any] = field(default_factory=dict)

    # ── Results (tools append here as pipeline executes) ───
    tool_results: list[ToolResult] = field(default_factory=list)
    extracted_data: dict[str, Any] = field(default_factory=dict)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    compliance_flags: list[str] = field(default_factory=list)

    # ── Status ─────────────────────────────────────────────
    status: ProcessingStatus = ProcessingStatus.PENDING
    overall_confidence: float = 0.0

    # ── Metadata ───────────────────────────────────────────
    created_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict) # For portal_data etc.

    def add_tool_result(self, result: ToolResult) -> None:
        """Append a tool result to the pipeline trace."""
        self.tool_results.append(result)

    def get_last_result(self) -> ToolResult | None:
        """Get the most recent tool result."""
        return self.tool_results[-1] if self.tool_results else None

    def to_trace(self) -> dict[str, Any]:
        """Full pipeline trace for observability/debugging."""
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "doc_type": self.doc_type,
            "filename": self.filename,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "confidence": self.overall_confidence,
            "overall_confidence": self.overall_confidence,
            "extracted_data": self.extracted_data,
            "compliance_flags": self.compliance_flags,
            "tool_results": [
                {
                    "tool": r.tool_name,
                    "success": r.success,
                    "confidence": r.confidence,
                    "error": r.error,
                }
                for r in self.tool_results
            ],
            "processing_time_ms": self.processing_time_ms,
        }