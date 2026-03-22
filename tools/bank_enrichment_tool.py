"""
bank_enrichment_tool.py — Bank Transaction Categorization
=========================================================
Adds practical bookkeeping intelligence on top of extracted bank rows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import re
from typing import Any

import structlog

from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface

logger = structlog.get_logger(__name__)


class BankEnrichmentTool(ToolInterface):
    @property
    def name(self) -> str:
        return "bank_enrichment_tool"

    async def execute(self, context: Context) -> ToolResult:
        transactions = context.extracted_data.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"categorized_transactions": 0, "summary": {}},
                confidence=0.0,
            )

        categorized_transactions: list[dict[str, Any]] = []
        category_totals: defaultdict[str, float] = defaultdict(float)
        type_totals: defaultdict[str, float] = defaultdict(float)
        counterparties: Counter[str] = Counter()
        anomaly_flags: list[str] = []
        uncategorized_count = 0
        duplicate_candidates = 0
        last_seen_keys: Counter[tuple[str, str, float]] = Counter()

        for raw_entry in transactions:
            if not isinstance(raw_entry, dict):
                continue

            description = self._clean_text(raw_entry.get("description"))
            debit = self._to_float(raw_entry.get("debit")) or 0.0
            credit = self._to_float(raw_entry.get("credit")) or 0.0
            amount = credit if credit > 0 else debit
            transaction_type = self._transaction_type(description, debit, credit)
            category, category_confidence = self._categorize(description, transaction_type)
            counterparty = self._extract_counterparty(description)
            entry_flags = self._entry_flags(description, amount, debit, credit, category)

            if category == "uncategorized":
                uncategorized_count += 1
            if counterparty:
                counterparties[counterparty] += 1

            category_totals[category] += amount
            type_totals[transaction_type] += amount

            duplicate_key = (
                str(raw_entry.get("date", "")).strip(),
                description,
                round(amount, 2),
            )
            last_seen_keys[duplicate_key] += 1
            if description and amount and last_seen_keys[duplicate_key] > 1:
                duplicate_candidates += 1
                entry_flags.append("duplicate_candidate")

            if entry_flags:
                anomaly_flags.extend(entry_flags)

            categorized_transactions.append({
                **raw_entry,
                "amount": round(amount, 2),
                "transaction_type": transaction_type,
                "category": category,
                "category_confidence": round(category_confidence, 4),
                "counterparty": counterparty,
                "anomaly_flags": entry_flags,
            })

        total_transactions = len(categorized_transactions)
        categorized_count = total_transactions - uncategorized_count
        category_coverage = categorized_count / total_transactions if total_transactions else 0.0
        summary = {
            "transaction_count": total_transactions,
            "categorized_transactions": categorized_count,
            "uncategorized_transactions": uncategorized_count,
            "category_coverage": round(category_coverage, 4),
            "total_inflow": round(type_totals.get("income", 0.0), 2),
            "total_outflow": round(type_totals.get("expense", 0.0), 2),
            "total_transfers": round(type_totals.get("internal_transfer", 0.0), 2),
            "total_unknown": round(type_totals.get("unknown", 0.0), 2),
            "category_totals": dict(sorted(category_totals.items(), key=lambda item: item[0])),
            "top_counterparties": [
                {"name": name, "count": count}
                for name, count in counterparties.most_common(5)
            ],
            "duplicate_candidates": duplicate_candidates,
            "high_value_transactions": sum(
                1 for item in categorized_transactions if item["amount"] >= 100000
            ),
        }

        if category_coverage < 0.6:
            context.compliance_flags.append(
                "BANK_REVIEW: More than 40% of transactions could not be confidently categorized"
            )
        if duplicate_candidates > 0:
            context.compliance_flags.append(
                f"BANK_DUPLICATE_REVIEW: {duplicate_candidates} duplicate-looking transaction(s) detected"
            )

        context.extracted_data["transactions"] = categorized_transactions
        context.extracted_data["statement_summary"] = summary
        context.extracted_data["category_totals"] = summary["category_totals"]
        context.confidence_scores["transaction_categorization"] = round(category_coverage, 4)
        context.confidence_scores["transaction_structure"] = round(
            min(total_transactions / max(total_transactions + uncategorized_count, 1), 1.0), 4
        )

        logger.info(
            "bank_enrichment_tool.completed",
            transactions=total_transactions,
            categorized=categorized_count,
            uncategorized=uncategorized_count,
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "categorized_transactions": categorized_count,
                "uncategorized_transactions": uncategorized_count,
                "summary": summary,
            },
            confidence=round(category_coverage, 4),
        )

    def _categorize(self, description: str, transaction_type: str) -> tuple[str, float]:
        normalized = description.upper()
        rules: list[tuple[str, tuple[str, ...], float]] = [
            ("salary", ("SALARY", "PAYROLL", "WAGES"), 0.96),
            ("rent", ("RENT", "LEASE"), 0.95),
            ("utilities", ("ELECTRIC", "WATER", "BILLDESK", "BESCOM", "UTILITY"), 0.9),
            ("tax_payment", ("GST", "TDS", "INCOME TAX", "ADVANCE TAX", "CHALLAN"), 0.94),
            ("loan_interest", ("INTEREST", "EMI", "LOAN"), 0.9),
            ("travel_fuel", ("UBER", "OLA", "FUEL", "PETROL", "DIESEL", "FASTAG"), 0.88),
            ("staff_welfare", ("ZOMATO", "SWIGGY", "FOOD", "RESTAURANT", "HOTEL"), 0.84),
            ("software_saas", ("AWS", "AZURE", "GOOGLE CLOUD", "OPENAI", "ANTHROPIC", "NOTION", "SLACK"), 0.9),
            ("bank_charges", ("CHARGES", "FEE", "COMMISSION", "AMC"), 0.9),
            ("cash_withdrawal", ("ATM", "CASH WDL", "CASH WITHDRAWAL"), 0.95),
            ("cash_deposit", ("CASH DEP", "CASH DEPOSIT"), 0.95),
            ("internal_transfer", ("TRANSFER", "NEFT", "RTGS", "IMPS", "UPI", "TO SELF", "SELF"), 0.75),
            ("vendor_payment", ("VENDOR", "SUPPLIER", "PURCHASE"), 0.82),
            ("sales_receipt", ("RECEIVED", "COLLECTION", "SALE", "CUSTOMER"), 0.8),
        ]
        for category, keywords, confidence in rules:
            if any(keyword in normalized for keyword in keywords):
                if category == "internal_transfer" and transaction_type not in {"income", "expense", "internal_transfer"}:
                    return category, 0.7
                return category, confidence

        if transaction_type == "internal_transfer":
            return "internal_transfer", 0.72
        return "uncategorized", 0.35

    def _transaction_type(self, description: str, debit: float, credit: float) -> str:
        normalized = description.upper()
        if any(keyword in normalized for keyword in ["TRANSFER", "TO SELF", "OWN ACCOUNT", "SWEEP"]):
            return "internal_transfer"
        if credit > 0 and debit == 0:
            return "income"
        if debit > 0 and credit == 0:
            return "expense"
        if credit > 0 and debit > 0:
            return "unknown"
        return "unknown"

    def _extract_counterparty(self, description: str) -> str:
        if not description:
            return ""
        cleaned = re.sub(r"\b(UPI|NEFT|RTGS|IMPS|ATM|POS|ACH|MBK|MB|REF|UTR|TXN)\b", " ", description.upper())
        cleaned = re.sub(r"[^A-Z0-9 ]+", " ", cleaned)
        tokens = [token for token in cleaned.split() if len(token) > 2 and not token.isdigit()]
        if not tokens:
            return ""
        return " ".join(tokens[:3]).title()

    def _entry_flags(self, description: str, amount: float, debit: float, credit: float, category: str) -> list[str]:
        flags: list[str] = []
        normalized = description.upper()
        if amount >= 100000:
            flags.append("high_value_transaction")
        if category == "cash_withdrawal" and debit >= 50000:
            flags.append("high_value_cash_withdrawal")
        if category == "uncategorized" and amount >= 25000:
            flags.append("high_value_uncategorized")
        if any(keyword in normalized for keyword in ["REVERSAL", "CHARGEBACK", "BOUNCE", "RETURN"]):
            flags.append("reversal_or_bounce_indicator")
        if debit > 0 and credit > 0:
            flags.append("mixed_debit_credit_entry")
        return flags

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = re.sub(r"\s+", " ", text)
        return text

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
