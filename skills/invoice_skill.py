"""
invoice_skill.py — Invoice Processing Skill
=============================================
This skill knows HOW to process an invoice.
It composes the tools in the correct order.
Think of it as a specialist who knows the invoice workflow:
1. Read the document (Extractor)
2. Pull out the fields (Parser)
3. Check the rules (Validator)
4. Score the confidence (Confidence Scorer)

Adding a new document type never touches this file.
This file only ever changes if invoice processing logic changes.
→ Single Responsibility Principle
"""

import structlog
from typing import Any
from agent.context import Context
from agent.interfaces import BaseSkill
from tools.extractor_tool import ExtractorTool
from tools.parser_tool import ParserTool
from tools.validator_tool import ValidatorTool
from tools.confidence_scorer_tool import ConfidenceScorerTool
from tools.qr_tool import QRTool

logger = structlog.get_logger(__name__)


class InvoiceSkill(BaseSkill):
    """
    Skill for processing invoice PDFs.
    Extends BaseSkill (Template Method Pattern).
    """

    def __init__(self):
        # Tools are injected as dependencies
        self._qr = QRTool()
        self._extractor = ExtractorTool()
        self._parser = ParserTool()
        self._validator = ValidatorTool()
        self._scorer = ConfidenceScorerTool()

    @property
    def skill_name(self) -> str:
        return "invoice"

    async def run(self, context: Context) -> dict[str, Any]:
        """
        Execute invoice processing pipeline.
        Each tool result is appended to context for full traceability.
        """
        logger.info("invoice_skill.started", request_id=context.request_id)

        # ── Step 0: Scan for e-Invoice QR Code ────────────
        result = await self._qr.execute(context)
        context.add_tool_result(result)

        # ── Step 1: Extract raw text from PDF ─────────────
        result = await self._extractor.execute(context)
        context.add_tool_result(result)
        if not result.success:
            raise RuntimeError(f"Extraction failed: {result.error}")

        # ── Step 2: Parse structured fields using LLM ─────
        result = await self._parser.execute(context)
        context.add_tool_result(result)
        if not result.success:
            raise RuntimeError(f"Parsing failed: {result.error}")

        # ── Step 3: Validate business rules (deterministic) 
        result = await self._validator.execute(context)
        context.add_tool_result(result)
        # Validator doesn't fail — it just adds flags

        # ── Step 4: Score overall confidence ──────────────
        result = await self._scorer.execute(context)
        context.add_tool_result(result)

        logger.info(
            "invoice_skill.completed",
            confidence=context.overall_confidence,
            flags=len(context.compliance_flags),
        )

        return {
            "skill": self.skill_name,
            "extracted_data": context.extracted_data,
            "confidence": context.overall_confidence,
            "flags": context.compliance_flags,
        }