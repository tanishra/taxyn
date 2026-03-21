"""
reconciliation_skill.py — GSTR-2A Reconciliation Skill
======================================================
The specialist for matching internal invoices vs portal records.
"""

from datetime import datetime
from difflib import SequenceMatcher
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
        internal_record = self._normalize_internal_record(internal)
        normalized_portal_records = [self._normalize_portal_record(record) for record in portal_list]

        if not normalized_portal_records:
            return {
                "is_matched": False,
                "status": "MISSING_IN_PORTAL",
                "diff": internal_record["amount"],
                "flags": ["RECON_MISSING: No portal data available for reconciliation"],
                "mismatch_reasons": ["portal_data_missing"],
                "matched_record": None,
            }

        candidates = []
        for index, record in enumerate(normalized_portal_records):
            candidate = self._score_candidate(internal_record, record, index)
            if candidate["score"] > 0:
                candidates.append(candidate)

        if not candidates:
            return {
                "is_matched": False,
                "status": "MISSING_IN_PORTAL",
                "diff": internal_record["amount"],
                "flags": ["RECON_MISSING: No matching invoice found in uploaded portal data"],
                "mismatch_reasons": ["no_candidate_found"],
                "matched_record": None,
                "candidate_count": 0,
            }

        candidates.sort(key=lambda item: item["score"], reverse=True)
        best = candidates[0]
        competing_matches = [
            item for item in candidates
            if item["score"] >= 0.82
            and abs(item["score"] - best["score"]) <= 0.03
            and item["portal_record"]["match_key"] != best["portal_record"]["match_key"]
        ]

        status, flags, mismatch_reasons = self._classify_candidate(best, competing_matches)
        matched_record = self._build_matched_record(best["portal_record"])

        return {
            "is_matched": status == "MATCHED",
            "status": status,
            "score": round(best["score"], 4),
            "match_confidence": round(best["score"], 4),
            "diff": round(best["differences"]["amount_diff"], 2),
            "portal_amount": best["portal_record"]["amount"],
            "extracted_amount": internal_record["amount"],
            "portal_taxable_value": best["portal_record"]["taxable_value"],
            "extracted_taxable_value": internal_record["taxable_value"],
            "invoice_number_similarity": round(best["comparisons"]["invoice_similarity"], 4),
            "invoice_date_gap_days": best["comparisons"]["date_gap_days"],
            "mismatch_reasons": mismatch_reasons,
            "flags": flags,
            "matched_record": matched_record,
            "candidate_count": len(candidates),
            "review_candidates": [
                {
                    "invoice_number": item["portal_record"]["invoice_number_raw"],
                    "gstin": item["portal_record"]["gstin_raw"],
                    "amount": item["portal_record"]["amount"],
                    "score": round(item["score"], 4),
                }
                for item in candidates[:3]
            ],
        }

    def _normalize_identifier(self, value: str) -> str:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum())

    def _normalize_invoice_number(self, value: str) -> str:
        return self._normalize_identifier(value)

    def _normalize_internal_record(self, internal: dict[str, Any]) -> dict[str, Any]:
        invoice_number = self._get_field(internal, ["invoice_number", "invoice_no", "bill_no", "reference_number"])
        vendor_gstin = self._get_field(internal, ["vendor_gstin", "seller_gstin", "supplier_gstin", "gstin", "vendor_gst"])
        vendor_name = self._get_field(internal, ["vendor_name", "supplier_name", "seller_name"])
        invoice_date = self._get_field(internal, ["invoice_date", "date", "bill_date"])

        return {
            "invoice_number_raw": invoice_number,
            "invoice_number": self._normalize_invoice_number(invoice_number),
            "vendor_gstin_raw": vendor_gstin,
            "vendor_gstin": self._normalize_identifier(vendor_gstin),
            "vendor_name_raw": vendor_name,
            "vendor_name": self._normalize_name(vendor_name),
            "invoice_date_raw": invoice_date,
            "invoice_date": self._parse_date(invoice_date),
            "amount": self._to_float(internal.get("amount", internal.get("grand_total"))),
            "taxable_value": self._to_float(internal.get("taxable_value")),
            "igst": self._to_float(internal.get("igst")),
            "cgst": self._to_float(internal.get("cgst")),
            "sgst": self._to_float(internal.get("sgst")),
        }

    def _normalize_portal_record(self, record: dict[str, Any]) -> dict[str, Any]:
        invoice_number = str(record.get("invoice_number", "")).strip()
        gstin = str(record.get("gstin", "")).strip()
        supplier_name = str(record.get("supplier_name", "")).strip()
        invoice_date = str(record.get("invoice_date", "")).strip()
        amount = self._to_float(record.get("amount"))
        taxable_value = self._to_float(record.get("taxable_value"))
        igst = self._to_float(record.get("igst"))
        cgst = self._to_float(record.get("cgst"))
        sgst = self._to_float(record.get("sgst"))

        return {
            "match_key": self._normalize_identifier(f"{gstin}|{invoice_number}|{amount}"),
            "invoice_number_raw": invoice_number,
            "invoice_number": self._normalize_invoice_number(invoice_number),
            "gstin_raw": gstin,
            "gstin": self._normalize_identifier(gstin),
            "supplier_name_raw": supplier_name,
            "supplier_name": self._normalize_name(supplier_name),
            "invoice_date_raw": invoice_date,
            "invoice_date": self._parse_date(invoice_date),
            "amount": amount,
            "taxable_value": taxable_value,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst,
            "sheet_name": str(record.get("sheet_name", "")).strip(),
            "invoice_type": str(record.get("invoice_type", "")).strip(),
            "place_of_supply": str(record.get("place_of_supply", "")).strip(),
        }

    def _score_candidate(self, internal: dict[str, Any], portal: dict[str, Any], index: int) -> dict[str, Any]:
        invoice_similarity = self._invoice_similarity(internal["invoice_number"], portal["invoice_number"])
        gst_match = bool(internal["vendor_gstin"] and portal["gstin"] and internal["vendor_gstin"] == portal["gstin"])
        vendor_name_similarity = self._name_similarity(internal["vendor_name"], portal["supplier_name"])

        amount_diff = self._abs_diff(internal["amount"], portal["amount"])
        taxable_diff = self._abs_diff(internal["taxable_value"], portal["taxable_value"])
        igst_diff = self._abs_diff(internal["igst"], portal["igst"])
        cgst_diff = self._abs_diff(internal["cgst"], portal["cgst"])
        sgst_diff = self._abs_diff(internal["sgst"], portal["sgst"])
        date_gap_days = self._date_gap_days(internal["invoice_date"], portal["invoice_date"])

        score = 0.0
        if invoice_similarity >= 0.98:
            score += 0.45
        elif invoice_similarity >= 0.9:
            score += 0.34
        elif invoice_similarity >= 0.75:
            score += 0.20

        if gst_match:
            score += 0.28
        elif internal["vendor_name"] and portal["supplier_name"] and vendor_name_similarity >= 0.9:
            score += 0.12

        if amount_diff is not None:
            if amount_diff <= 1:
                score += 0.15
            elif amount_diff <= 5:
                score += 0.12
            elif amount_diff <= 25:
                score += 0.06

        if taxable_diff is not None:
            if taxable_diff <= 1:
                score += 0.06
            elif taxable_diff <= 5:
                score += 0.04
            elif taxable_diff <= 25:
                score += 0.02

        if date_gap_days is not None:
            if date_gap_days == 0:
                score += 0.06
            elif date_gap_days <= 3:
                score += 0.04
            elif date_gap_days <= 31:
                score += 0.02

        tax_component_alignment = 0
        for diff in [igst_diff, cgst_diff, sgst_diff]:
            if diff is None:
                continue
            if diff <= 1:
                tax_component_alignment += 1
        score += min(tax_component_alignment * 0.02, 0.06)

        return {
            "index": index,
            "score": min(score, 1.0),
            "portal_record": portal,
            "comparisons": {
                "invoice_similarity": invoice_similarity,
                "gst_match": gst_match,
                "vendor_name_similarity": vendor_name_similarity,
                "date_gap_days": date_gap_days,
            },
            "differences": {
                "amount_diff": amount_diff or 0.0,
                "taxable_value_diff": taxable_diff,
                "igst_diff": igst_diff,
                "cgst_diff": cgst_diff,
                "sgst_diff": sgst_diff,
            },
        }

    def _classify_candidate(self, candidate: dict[str, Any], competing_matches: list[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
        reasons: list[str] = []
        flags: list[str] = []

        comparisons = candidate["comparisons"]
        differences = candidate["differences"]
        portal = candidate["portal_record"]
        score = candidate["score"]

        if comparisons["invoice_similarity"] < 0.98:
            reasons.append("invoice_number_variance")
        if not comparisons["gst_match"]:
            reasons.append("vendor_gstin_mismatch")
        if comparisons["date_gap_days"] is not None and comparisons["date_gap_days"] > 3:
            reasons.append("invoice_date_mismatch")
        if differences["amount_diff"] > 5:
            reasons.append("invoice_amount_mismatch")
        if differences["taxable_value_diff"] is not None and differences["taxable_value_diff"] > 5:
            reasons.append("taxable_value_mismatch")
        if any(
            diff is not None and diff > 2
            for diff in [differences["igst_diff"], differences["cgst_diff"], differences["sgst_diff"]]
        ):
            reasons.append("tax_component_mismatch")
        if competing_matches:
            reasons.append("duplicate_or_ambiguous_portal_match")

        if score >= 0.88 and not reasons:
            return "MATCHED", [], []

        if score >= 0.78 and not any(
            reason in reasons
            for reason in ["invoice_amount_mismatch", "taxable_value_mismatch", "tax_component_mismatch"]
        ):
            flags.append(
                "RECON_PARTIAL_MATCH: Portal record is close but has minor invoice number, vendor, or date variance"
            )
            return "PARTIAL_MATCH_REVIEW", flags, reasons

        if "duplicate_or_ambiguous_portal_match" in reasons:
            flags.append(
                f"RECON_DUPLICATE: Multiple portal records closely match invoice {portal['invoice_number_raw']} and need review"
            )
            return "AMBIGUOUS_MATCH_REVIEW", flags, reasons

        mismatch_messages = {
            "vendor_gstin_mismatch": "vendor GSTIN differs from portal data",
            "invoice_date_mismatch": "invoice date differs materially from portal data",
            "invoice_amount_mismatch": "invoice total amount differs from portal data",
            "taxable_value_mismatch": "taxable value differs from portal data",
            "tax_component_mismatch": "tax split differs from portal data",
            "invoice_number_variance": "invoice number only partially matches portal data",
        }
        for reason in reasons:
            if reason in mismatch_messages:
                flags.append(f"RECON_MISMATCH: {mismatch_messages[reason]}")

        if score < 0.55:
            flags.append("RECON_MISSING: No sufficiently reliable portal match found for the extracted invoice")
            return "MISSING_IN_PORTAL", flags, reasons or ["low_match_score"]

        if not flags:
            flags.append("RECON_MISMATCH: Extracted invoice does not reconcile cleanly with portal data")
        return "MISMATCH_REVIEW", flags, reasons or ["match_requires_review"]

    def _build_matched_record(self, portal: dict[str, Any]) -> dict[str, Any]:
        return {
            "invoice_number": portal["invoice_number_raw"],
            "gstin": portal["gstin_raw"],
            "supplier_name": portal["supplier_name_raw"],
            "invoice_date": portal["invoice_date_raw"],
            "amount": portal["amount"],
            "taxable_value": portal["taxable_value"],
            "igst": portal["igst"],
            "cgst": portal["cgst"],
            "sgst": portal["sgst"],
            "sheet_name": portal["sheet_name"],
            "invoice_type": portal["invoice_type"],
            "place_of_supply": portal["place_of_supply"],
        }

    def _normalize_name(self, value: str) -> str:
        cleaned = self._normalize_identifier(value)
        return cleaned.replace("PRIVATE", "").replace("LIMITED", "").replace("PVT", "").strip()

    def _invoice_similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        if left in right or right in left:
            return 0.96
        return SequenceMatcher(None, left, right).ratio()

    def _name_similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        return SequenceMatcher(None, left, right).ratio()

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d, %Y",
            "%B %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _to_float(self, value: Any) -> float | None:
        try:
            if value in (None, ""):
                return None
            cleaned = (
                str(value)
                .replace(",", "")
                .replace("₹", "")
                .replace("Rs.", "")
                .replace("INR", "")
                .strip()
            )
            return float(cleaned) if cleaned else None
        except (TypeError, ValueError):
            return None

    def _abs_diff(self, left: float | None, right: float | None) -> float | None:
        if left is None or right is None:
            return None
        return abs(left - right)

    def _date_gap_days(self, left: datetime | None, right: datetime | None) -> int | None:
        if left is None or right is None:
            return None
        return abs((left.date() - right.date()).days)
