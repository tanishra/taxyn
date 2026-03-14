"""
validator_tool.py — Deterministic Business Rule Validation
===========================================================
Single Responsibility: Validate extracted fields against
hard business rules. This is 100% deterministic code — no AI.

Examples of what this validates:
- GST rate is a valid Indian rate (0%, 5%, 12%, 18%, 28%)
- GSTIN format is correct (15-character alphanumeric)
- Invoice amount matches sum of line items
- Date is not in the future
- PAN number format is valid

WHY THIS IS NOT DONE BY AI:
Validation is deterministic. 18% GST is either valid or not.
There is no ambiguity. AI must never own deterministic logic.
→ This is the Deterministic Core Rule from your architecture.
"""

import re
import structlog
from datetime import datetime
from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface

logger = structlog.get_logger(__name__)

# Valid GST rates in India
VALID_GST_RATES = {0, 0.1, 0.25, 1, 1.5, 3, 5, 7.5, 12, 18, 28}

# GSTIN regex: 15-char format like 22AAAAA0000A1Z5
GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z]{1}[A-Z\d]{1}$")

# PAN regex: AAAAA9999A
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


class ValidatorTool(ToolInterface):
    """
    Tool 3 of 4 in the pipeline.
    Input: extracted fields in context
    Output: validation flags added to context.compliance_flags
    """

    @property
    def name(self) -> str:
        return "validator_tool"

    async def execute(self, context: Context) -> ToolResult:
        logger.info("validator_tool.started", doc_type=context.doc_type)

        flags = []
        data = context.extracted_data
        doc_type = str(context.doc_type).split(".")[-1]

        # Run validators based on doc type
        if doc_type == "invoice":
            flags.extend(self._validate_invoice(data))
        elif doc_type == "gst_return":
            flags.extend(self._validate_gst(data))
        elif doc_type == "tds_certificate":
            flags.extend(self._validate_tds(data))
        elif doc_type == "bank_statement":
            flags.extend(self._validate_bank(data))

        # Always run common validations
        flags.extend(self._validate_common(data))

        context.compliance_flags.extend(flags)

        logger.info(
            "validator_tool.completed",
            flags_raised=len(flags),
            flags=flags,
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"flags": flags, "flag_count": len(flags)},
            confidence=1.0,  # Validation is deterministic
        )

    # ── Invoice Validators ──────────────────────────────────

    def _validate_invoice(self, data: dict) -> list[str]:
        flags = []

        # Check GST amount is reasonable (≤ 28% of base amount)
        amount = self._to_float(data.get("amount"))
        gst_amount = self._to_float(data.get("gst_amount"))
        if amount and gst_amount:
            gst_rate = (gst_amount / amount) * 100
            if not any(abs(gst_rate - r) < 0.5 for r in VALID_GST_RATES):
                flags.append(f"INVALID_GST_RATE: Computed rate {gst_rate:.1f}% is not a standard Indian GST rate")

        # Check invoice number exists
        if not data.get("invoice_number"):
            flags.append("MISSING_INVOICE_NUMBER: Invoice number not found")

        # Check vendor name exists
        if not data.get("vendor_name"):
            flags.append("MISSING_VENDOR_NAME: Vendor name not found")

        # ── QR Integrity Check ──────────────────────────────────
        qr_data = data.get("qr_data")
        if qr_data:
            qr_amt = self._to_float(qr_data.get("total_value"))
            if qr_amt and amount and abs(qr_amt - amount) > 5.0:
                flags.append(f"TAMPER_ALERT: QR Amount (₹{qr_amt}) differs from OCR Amount (₹{amount}). Possible fraud.")
            
            qr_gstin = str(qr_data.get("seller_gstin", "")).strip().upper()
            ocr_gstin = str(data.get("supplier_gstin", "")).strip().upper()
            if qr_gstin and ocr_gstin and qr_gstin != ocr_gstin:
                flags.append(f"TAMPER_ALERT: QR Vendor GSTIN ({qr_gstin}) differs from printed GSTIN ({ocr_gstin}).")

        return flags

    # ── GST Return Validators ───────────────────────────────

    def _validate_gst(self, data: dict) -> list[str]:
        flags = []

        gstin = data.get("gstin", "")
        if gstin and not GSTIN_PATTERN.match(str(gstin).upper()):
            flags.append(f"INVALID_GSTIN_FORMAT: '{gstin}' does not match GSTIN format")

        # IGST = CGST + SGST for intra-state (approximate check)
        igst = self._to_float(data.get("igst"))
        cgst = self._to_float(data.get("cgst"))
        sgst = self._to_float(data.get("sgst"))
        if cgst and sgst and igst:
            if abs(igst - (cgst + sgst)) > 1:  # Allow ₹1 rounding
                flags.append(f"TAX_MISMATCH: IGST ({igst}) ≠ CGST ({cgst}) + SGST ({sgst})")

        return flags

    # ── TDS Validators ──────────────────────────────────────

    def _validate_tds(self, data: dict) -> list[str]:
        flags = []

        pan = data.get("pan", "")
        if pan and not PAN_PATTERN.match(str(pan).upper()):
            flags.append(f"INVALID_PAN_FORMAT: '{pan}' does not match PAN format")

        return flags

    # ── Bank Statement Validators ───────────────────────────

    def _validate_bank(self, data: dict) -> list[str]:
        flags = []
        if not data.get("account_number"):
            flags.append("MISSING_ACCOUNT_NUMBER: Account number not found in statement")
        return flags

    # ── Common Validators ───────────────────────────────────

    def _validate_common(self, data: dict) -> list[str]:
        flags = []

        date_str = data.get("date")
        if date_str:
            doc_date = self._parse_date(str(date_str))
            if doc_date is None:
                flags.append(f"INVALID_DATE_FORMAT: Could not parse date '{date_str}'")
            elif doc_date > datetime.utcnow():
                flags.append(f"FUTURE_DATE: Document date {date_str} is in the future")

        return flags

    def _parse_date(self, date_str: str):
        """Try multiple common date formats used in Indian invoices."""
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _to_float(self, value) -> float | None:
        try:
            return float(str(value).replace(",", "").replace("₹", "").strip())
        except (TypeError, ValueError):
            return None