"""
reconciliation_skill.py — GSTR-2A Reconciliation Skill
======================================================
The specialist for matching internal invoices vs portal records.
"""

from typing import Any
import structlog
from agent.context import Context, ToolResult, ProcessingStatus
from agent.interfaces import BaseSkill
from tools.extractor_tool import ExtractorTool
from tools.parser_tool import ParserTool
from tools.validator_tool import ValidatorTool
from tools.confidence_scorer_tool import ConfidenceScorerTool
from memory.stores import CorrectionStore

logger = structlog.get_logger(__name__)

class ReconciliationSkill(BaseSkill):
    def __init__(self, correction_store: CorrectionStore | None = None):
        self._extractor = ExtractorTool()
        self._parser = ParserTool(correction_store=correction_store)
        self._validator = ValidatorTool()
        self._scorer = ConfidenceScorerTool()

    @property
    def skill_name(self) -> str:
        return "reconciliation"

    async def run(self, context: Context) -> dict[str, Any]:
        logger.info("recon_skill.started", request_id=context.request_id)
        
        # 1. Update status to Reconciling
        context.status = ProcessingStatus.RECONCILING

        # 2. Extract internal data from PDF
        extract_result = await self._extractor.execute(context)
        context.add_tool_result(extract_result)
        if not extract_result.success:
            raise RuntimeError(f"Extraction failed: {extract_result.error}")

        parse_result = await self._parser.execute(context)
        context.add_tool_result(parse_result)
        if not parse_result.success:
            raise RuntimeError(f"Parsing failed: {parse_result.error}")

        # 3. Matchmaker logic - Sourcing from metadata
        internal_invoice = context.extracted_data
        portal_records = context.metadata.get("portal_data", [])

        match_result = self._perform_matching(internal_invoice, portal_records)
        
        context.extracted_data["recon_results"] = match_result
        context.compliance_flags.extend(match_result.get("flags", []))

        validator_result = await self._validator.execute(context)
        context.add_tool_result(validator_result)

        scorer_result = await self._scorer.execute(context)
        context.add_tool_result(scorer_result)
        
        logger.info("recon_skill.completed", status=match_result["status"])

        return {
            "status": "reconciled",
            "results": match_result
        }

    def _get_field(self, data: dict, keys: list[str]) -> str:
        for k in keys:
            if k in data and data[k]:
                return str(data[k])
        return ""

    def _perform_matching(self, internal: dict, portal_list: list) -> dict:
        """
        Deterministic matching logic.
        Matches based on GSTIN + Invoice Number.
        """
        # AI might extract keys differently, so we check multiple common keys
        inv_no = self._normalize_invoice_number(
            self._get_field(internal, ["invoice_number", "invoice_no", "bill_no", "reference_number"])
        )
        vendor_gst = self._normalize_identifier(
            self._get_field(internal, ["vendor_gstin", "seller_gstin", "gstin", "vendor_gst"])
        )
        
        # Try to parse amount safely
        try:
            amount_str = str(internal.get("amount", internal.get("grand_total", 0))).replace(",", "").replace("n", "").strip()
            amount = float(amount_str)
        except:
            amount = 0.0

        best_partial_match = None
        for record in portal_list:
            p_inv = self._normalize_invoice_number(record.get("invoice_number", ""))
            p_gst = self._normalize_identifier(record.get("gstin", ""))
            p_amount = float(record.get("amount", 0))

            # Match criteria
            invoice_match = inv_no and p_inv and (inv_no == p_inv or p_inv in inv_no or inv_no in p_inv)
            gst_match = vendor_gst and p_gst and (vendor_gst == p_gst or p_gst in vendor_gst)
            if invoice_match and gst_match:
                amount_diff = abs(amount - p_amount)
                if amount_diff < 5.0: # Match within 5 Rupees (rounding diffs)
                    return {"is_matched": True, "status": "MATCHED", "diff": 0, "flags": []}
                else:
                    return {
                        "is_matched": False, 
                        "status": "MISMATCHED_AMOUNT", 
                        "diff": amount_diff,
                        "portal_amount": p_amount,
                        "extracted_amount": amount,
                        "flags": [f"RECON_MISMATCH: Portal amount {p_amount} does not match extracted amount {amount}"],
                    }
            if invoice_match or gst_match:
                best_partial_match = {
                    "invoice_match": invoice_match,
                    "gst_match": gst_match,
                    "portal_amount": p_amount,
                }

        if best_partial_match:
            return {
                "is_matched": False,
                "status": "PARTIAL_MATCH_REVIEW",
                "diff": abs(amount - best_partial_match["portal_amount"]),
                "portal_amount": best_partial_match["portal_amount"],
                "extracted_amount": amount,
                "flags": ["RECON_PARTIAL_MATCH: Portal data partially matches extracted invoice and needs review"],
            }
        return {
            "is_matched": False,
            "status": "MISSING_IN_PORTAL",
            "diff": amount,
            "flags": ["RECON_MISSING: No matching invoice found in uploaded portal data"],
        }

    def _normalize_identifier(self, value: str) -> str:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum())

    def _normalize_invoice_number(self, value: str) -> str:
        return self._normalize_identifier(value)
