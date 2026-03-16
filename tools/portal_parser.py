"""
portal_parser.py — GST Portal Excel Parser
===========================================
Single Responsibility: Take a bytes object (Excel file) and return
a list of structured portal records.
"""

import pandas as pd
import io
from typing import List, Dict, Any
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
                    record = {
                        "gstin": self._find_col(row, ["GSTIN", "Supplier"]),
                        "invoice_number": self._find_col(row, ["Invoice Number", "Inv No", "Invoice No"]),
                        "amount": self._find_val(row, ["Invoice Value", "Total Value", "Amount"]),
                    }
                    if record["gstin"] and record["invoice_number"]:
                        records.append(record)

            logger.info("portal_parser.completed", records_found=len(records))
            return records

        except Exception as e:
            logger.error("portal_parser.failed", error=str(e))
            return []

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
                return str(row[col]).strip()
        return ""

    def _find_val(self, row, keywords: List[str]) -> float:
        for col in row.index:
            if any(k.upper() in str(col).upper() for k in keywords):
                try:
                    return float(str(row[col]).replace(",", ""))
                except:
                    continue
        return 0.0
