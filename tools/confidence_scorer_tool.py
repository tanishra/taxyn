"""
confidence_scorer_tool.py — Final Confidence Aggregation
==========================================================
Single Responsibility: Look at all field-level confidence scores
and compute one final overall confidence for the whole document.

If the score is below the threshold (0.85 by default),
AgentLoop will route to the HITL queue instead of auto-completing.

This is the "honesty layer" of Taxyn — instead of silently
returning wrong data, we tell the customer "we're not sure,
please check this one."

This is what separates Taxyn from dumb OCR tools.
"""

import structlog
from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface
from config.settings import settings

logger = structlog.get_logger(__name__)


class ConfidenceScorerTool(ToolInterface):
    """
    Tool 4 of 4 in the pipeline.
    Input: confidence_scores dict in context
    Output: final overall_confidence score + per-field analysis
    """

    @property
    def name(self) -> str:
        return "confidence_scorer_tool"

    async def execute(self, context: Context) -> ToolResult:
        logger.info("confidence_scorer_tool.started")

        scores = context.confidence_scores
        if not scores:
            context.overall_confidence = 0.0
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"overall_confidence": 0.0, "low_confidence_fields": []},
                confidence=0.0,
            )

        # ── Weighted scoring ────────────────────────────────
        # Critical fields (amount, date) get 2x weight
        critical_fields = {"amount", "invoice_number", "gstin", "pan", "date"}

        weighted_sum = 0.0
        total_weight = 0.0
        low_confidence_fields = []

        for field, score in scores.items():
            weight = 2.0 if field in critical_fields else 1.0
            weighted_sum += score * weight
            total_weight += weight

            if score < settings.CONFIDENCE_THRESHOLD:
                low_confidence_fields.append({
                    "field": field,
                    "confidence": score,
                    "needs_review": True,
                })

        overall = weighted_sum / total_weight if total_weight > 0 else 0.0

        extracted_fields = {
            key: value for key, value in context.extracted_data.items()
            if key not in {"raw_text", "char_count", "qr_data"} and value not in (None, "", [], {})
        }
        scored_field_count = len(scores)
        completeness_ratio = min(len(extracted_fields) / scored_field_count, 1.0) if scored_field_count else 0.0
        overall = (overall * 0.8) + (completeness_ratio * 0.2)

        if context.extracted_data.get("qr_data"):
            overall = min(1.0, overall + 0.03)

        # Penalize if there are compliance flags
        flag_count = len(context.compliance_flags)
        if flag_count > 0:
            # Each flag reduces confidence by 5%, max 20% penalty
            penalty = min(flag_count * 0.05, 0.20)
            overall = max(0.0, overall - penalty)
            logger.info(
                "confidence_scorer_tool.flags_penalty",
                flags=flag_count,
                penalty=penalty,
            )

        low_field_penalty = min(len(low_confidence_fields) * 0.015, 0.10)
        overall = max(0.0, overall - low_field_penalty)

        context.overall_confidence = round(overall, 4)

        needs_review = context.overall_confidence < settings.CONFIDENCE_THRESHOLD

        logger.info(
            "confidence_scorer_tool.completed",
            overall_confidence=context.overall_confidence,
            low_confidence_fields=len(low_confidence_fields),
            needs_review=needs_review,
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "overall_confidence": context.overall_confidence,
                "low_confidence_fields": low_confidence_fields,
                "needs_review": needs_review,
                "threshold": settings.CONFIDENCE_THRESHOLD,
                "completeness_ratio": round(completeness_ratio, 4),
            },
            confidence=context.overall_confidence,
        )
