"""
parser_tool.py — Raw Text → Structured Fields (uses Instructor + GPT-4o)
==========================================================================
Single Responsibility: Take raw extracted text and use an LLM
to pull out specific fields. 

UPDATED: Now supports nested transaction tables for Bank Statements.
"""

import structlog
import openai
import instructor
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface
from config.settings import settings
from memory.stores import CorrectionStore

logger = structlog.get_logger(__name__)


# ── Pydantic models for structured extraction ──────────────────

class ExtractedField(BaseModel):
    """One extracted field with its confidence score."""
    field_name: str
    value: Any # Changed from str to Any to support lists/objects
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ExtractionResult(BaseModel):
    """Full structured extraction result from LLM."""
    fields: List[ExtractedField]
    document_summary: str
    extraction_notes: str


# ── Tool ──────────────────────────────────────────────────────

class ParserTool(ToolInterface):
    """
    Tool 2 of 4 in the pipeline.
    """

    def __init__(self, correction_store: Optional[CorrectionStore] = None):
        raw_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self._client = instructor.from_openai(raw_client)
        self._correction_store = correction_store

    @property
    def name(self) -> str:
        return "parser_tool"

    async def execute(self, context: Context) -> ToolResult:
        logger.info("parser_tool.started", doc_type=context.doc_type)

        raw_text = context.extracted_data.get("raw_text", "")
        if not raw_text:
            return ToolResult(tool_name=self.name, success=False, error="No raw text found.", confidence=0.0)

        schema = context.extraction_schema
        fields_to_extract = list(schema.keys()) if schema else self._default_fields(context.doc_type)

        # ── VENDOR MEMORY LAYER ───────────────────────────────────────
        vendor_name = self._heuristic_vendor_detection(raw_text)
        previous_fixes = []
        if self._correction_store is not None:
            previous_fixes = await self._correction_store.get_vendor_memory(vendor_name)
        # ─────────────────────────────────────────────────────────────

        try:
            result: ExtractionResult = self._client.messages.create(
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
                response_model=ExtractionResult,
                messages=[
                    {
                        "role": "user",
                        "content": self._build_prompt(
                            raw_text, 
                            fields_to_extract, 
                            context.doc_type,
                            memory=previous_fixes
                        ),
                    }
                ],
            )

            # Store results
            extracted = {f.field_name: f.value for f in result.fields}
            context.extracted_data.update(extracted)
            
            confidence_scores = {f.field_name: f.confidence for f in result.fields}
            context.confidence_scores.update(confidence_scores)

            if confidence_scores:
                context.overall_confidence = sum(confidence_scores.values()) / len(confidence_scores)

            logger.info("parser_tool.completed", fields=len(result.fields), confidence=context.overall_confidence)

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"fields": extracted, "summary": result.document_summary},
                confidence=context.overall_confidence,
            )

        except Exception as e:
            logger.error("parser_tool.llm_failed", error=str(e))
            context.overall_confidence = 0.0
            context.compliance_flags.append(f"SYSTEM_ERROR: LLM Parser failure ({str(e)[:50]}...)")
            return ToolResult(tool_name=self.name, success=True, error=str(e), confidence=0.0)

    def _heuristic_vendor_detection(self, text: str) -> str:
        lines = text.split('\n')
        for line in lines[:10]:
            if any(k in line.lower() for k in ["pvt", "ltd", "corp", "inc", "bank", "hdfc", "icici", "sbi"]):
                return line.strip()
        return "unknown"

    def _build_prompt(self, raw_text: str, fields: list[str], doc_type: str, memory: list[dict] = None) -> str:
        memory_str = ""
        if memory:
            memory_str = "\nLEARNED KNOWLEDGE FROM PREVIOUS HUMAN CORRECTIONS:\n"
            for fix in memory[:5]:
                memory_str += f"- For field '{fix['field']}', human corrected it to '{fix['corrected']}'.\n"

        special_instructions = ""
        if "bank_statement" in str(doc_type).lower():
            special_instructions = "\nFor the 'transactions' field, extract a list of objects each containing: date, description, debit, credit, balance."

        return f"""You are a document extraction expert specializing in Indian financial documents.

Document Type: {doc_type}
Fields to extract: {', '.join(fields)}
{special_instructions}
{memory_str}

Document Text:
{raw_text[:6000]}

Extract each field precisely. For tables or lists, return them as a structured list of objects.
If a field is not found, set value to null.
Be conservative with confidence scores."""

    def _default_fields(self, doc_type) -> list[str]:
        defaults = {
            "invoice": [
                "invoice_number", "vendor_name", "supplier_gstin", "buyer_gstin",
                "amount", "taxable_value", "gst_amount", "cgst", "sgst", "igst",
                "gst_rate", "place_of_supply", "hsn_sac", "invoice_type",
                "date", "due_date", "line_items"
            ],
            "gst_return": [
                "return_type", "gstin", "period", "filing_date",
                "b2b_taxable_value", "b2c_taxable_value", "export_taxable_value",
                "total_taxable_value", "igst", "cgst", "sgst",
                "tax_liability", "tax_paid", "interest_amount", "late_fee"
            ],
            "bank_statement": [
                "bank_name", "account_holder_name", "account_number", "ifsc", "currency",
                "period_start", "period_end", "period", "opening_balance", "closing_balance",
                "transactions"
            ],
            "tds_certificate": [
                "pan", "tan", "deductor_name", "section_code", "certificate_number",
                "assessment_year", "period", "deduction_date", "challan_bsr",
                "amount_paid", "tds_deducted"
            ],
            "reconciliation": [
                "invoice_number", "vendor_name", "vendor_gstin", "invoice_date",
                "amount", "taxable_value", "igst", "cgst", "sgst"
            ]
        }
        key = str(doc_type).split(".")[-1].lower()
        return defaults.get(key, ["amount", "date", "reference_number"])
