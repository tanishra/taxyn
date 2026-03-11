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

logger = structlog.get_logger(__name__)

class ReconciliationSkill(BaseSkill):
    def __init__(self):
        self._extractor = ExtractorTool()
        self._parser = ParserTool()

    @property
    def skill_name(self) -> str:
        return "reconciliation"

    async def run(self, context: Context) -> dict[str, Any]:
        logger.info("recon_skill.started", request_id=context.request_id)
        
        # 1. Update status to Reconciling
        context.status = ProcessingStatus.RECONCILING

        # 2. Extract internal data from PDF
        await self._extractor.execute(context)
        await self._parser.execute(context)

        # 3. Matchmaker logic - Sourcing from metadata
        internal_invoice = context.extracted_data
        portal_records = context.metadata.get("portal_data", [])

        match_result = self._perform_matching(internal_invoice, portal_records)
        
        context.extracted_data["recon_results"] = match_result
        
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
        inv_no = self._get_field(internal, ["invoice_number", "invoice_no", "bill_no", "reference_number"]).strip().lower()
        vendor_gst = self._get_field(internal, ["vendor_gstin", "seller_gstin", "gstin", "vendor_gst"]).strip().lower()
        
        # Try to parse amount safely
        try:
            amount_str = str(internal.get("amount", internal.get("grand_total", 0))).replace(",", "").replace("n", "").strip()
            amount = float(amount_str)
        except:
            amount = 0.0

        for record in portal_list:
            p_inv = str(record.get("invoice_number", "")).strip().lower()
            p_gst = str(record.get("gstin", "")).strip().lower()
            p_amount = float(record.get("amount", 0))

            # Match criteria
            if (inv_no == p_inv or p_inv in inv_no or inv_no in p_inv) and (vendor_gst == p_gst or p_gst in vendor_gst):
                amount_diff = abs(amount - p_amount)
                if amount_diff < 5.0: # Match within 5 Rupees (rounding diffs)
                    return {"is_matched": True, "status": "MATCHED", "diff": 0}
                else:
                    return {
                        "is_matched": False, 
                        "status": "MISMATCHED_AMOUNT", 
                        "diff": amount_diff,
                        "portal_amount": p_amount,
                        "extracted_amount": amount
                    }

        return {"is_matched": False, "status": "MISSING_IN_PORTAL", "diff": amount}
