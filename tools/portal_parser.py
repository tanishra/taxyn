"""
portal_parser.py — GST Portal Excel Parser
===========================================
Single Responsibility: Take a bytes object (Excel file) and return
a list of structured portal records.
"""

import io
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

class PortalExcelParser:
    """
    Parses Government GSTR-2A/2B Excel files.
    """

    def parse(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            # Load the Excel file from memory
            excel_file = io.BytesIO(file_bytes)
            
            records = []
            sheet_map = pd.read_excel(excel_file, sheet_name=None, header=None)
            for sheet_name, raw_df in sheet_map.items():
                if "b2b" not in str(sheet_name).upper() and "CDNR" not in str(sheet_name).upper():
                    continue

                header_row_idx = self._find_header_row(raw_df)
                if header_row_idx is None:
                    continue

                normalized_df = raw_df.iloc[header_row_idx + 1 :].copy()
                normalized_df.columns = [str(value).strip() for value in raw_df.iloc[header_row_idx].tolist()]
                normalized_df = normalized_df.dropna(how="all")

                for _, row in normalized_df.iterrows():
                    record = self._build_record(row, sheet_name)
                    if record["gstin"] and record["invoice_number"]:
                        records.append(record)

            logger.info("portal_parser.completed", records_found=len(records))
            return records

        except Exception as e:
            logger.error("portal_parser.failed", error=str(e))
            return []

    def _build_record(self, row, sheet_name: str) -> Dict[str, Any]:
        igst = self._find_val(row, ["IGST"])
        cgst = self._find_val(row, ["CGST", "Central Tax"])
        sgst = self._find_val(row, ["SGST", "UTGST", "State Tax"])
        cess = self._find_val(row, ["Cess"])
        taxable_value = self._find_val(row, ["Taxable Value", "Taxable Amount"])
        invoice_value = self._find_val(row, ["Invoice Value", "Total Value", "Amount"])
        total_tax = sum(value for value in [igst, cgst, sgst, cess] if value)

        return {
            "sheet_name": str(sheet_name),
            "supplier_name": self._find_col(row, ["Trade/Legal name", "Supplier Name", "Party Name", "Supplier"]),
            "gstin": self._find_col(row, ["GSTIN", "GSTIN/UIN", "Supplier GSTIN"]),
            "invoice_number": self._find_col(row, ["Invoice Number", "Inv No", "Invoice No", "Document Number"]),
            "invoice_date": self._find_date(row, ["Invoice Date", "Inv Date", "Document Date"]),
            "invoice_type": self._find_col(row, ["Invoice Type", "Inv Type", "Document Type"]),
            "place_of_supply": self._find_col(row, ["Place Of Supply", "POS"]),
            "amount": invoice_value,
            "taxable_value": taxable_value,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst,
            "cess": cess,
            "tax_amount": total_tax,
        }

    def _find_header_row(self, dataframe: pd.DataFrame) -> int | None:
        for idx, row in dataframe.head(15).iterrows():
            values = [str(value).upper() for value in row.values if pd.notna(value)]
            has_gstin = any("GSTIN" in value for value in values)
            has_invoice = any("INVOICE" in value for value in values)
            if has_gstin and has_invoice:
                return int(idx)
        return None

    def _find_col(self, row, keywords: List[str]) -> str:
        for col in row.index:
            if any(k.upper() in str(col).upper() for k in keywords):
                value = row[col]
                if pd.isna(value):
                    return ""
                return str(value).strip()
        return ""

    def _find_val(self, row, keywords: List[str]) -> float:
        for col in row.index:
            if any(k.upper() in str(col).upper() for k in keywords):
                try:
                    raw_value = row[col]
                    if pd.isna(raw_value):
                        continue
                    cleaned = (
                        str(raw_value)
                        .replace(",", "")
                        .replace("₹", "")
                        .replace("Rs.", "")
                        .replace("INR", "")
                        .strip()
                    )
                    if not cleaned:
                        continue
                    return float(cleaned)
                except Exception:
                    continue
        return 0.0

    def _find_date(self, row, keywords: List[str]) -> str:
        for col in row.index:
            if any(k.upper() in str(col).upper() for k in keywords):
                return self._normalize_date(row[col])
        return ""

    def _normalize_date(self, value: Any) -> str:
        if value is None or (hasattr(pd, "isna") and pd.isna(value)):
            return ""
        if isinstance(value, pd.Timestamp):
            return value.date().isoformat()
        if isinstance(value, datetime):
            return value.date().isoformat()

        text = str(value).strip()
        if not text:
            return ""

        known_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d %Y",
            "%B %d %Y",
        ]
        for fmt in known_formats:
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        return text
