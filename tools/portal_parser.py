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
            
            # GSTR-2A usually has a sheet named 'B2B'
            # We use sheet_name=None to read all sheets if needed, but B2B is primary.
            df = pd.read_excel(excel_file, sheet_name=None)
            
            # Look for the B2B sheet (case insensitive)
            b2b_sheet_key = next((k for k in df.keys() if "b2b" in k.upper()), None)
            
            if not b2b_sheet_key:
                logger.error("portal_parser.missing_b2b_sheet")
                return []

            b2b_df = df[b2b_sheet_key]
            
            # Normalize column names (GST Portal Excels often have headers on row 5 or 6)
            # For robustness, we search for the row that contains 'GSTIN'
            header_row_idx = 0
            for i, row in b2b_df.head(10).iterrows():
                if any("GSTIN" in str(val).upper() for v in row.values for val in [v]):
                    header_row_idx = i
                    break
            
            # Re-read with the correct header
            excel_file.seek(0)
            b2b_df = pd.read_excel(excel_file, sheet_name=b2b_sheet_key, skiprows=header_row_idx + 1)
            
            # Map columns to our internal names
            # Typical GSTR-2A columns: 'GSTIN of supplier', 'Invoice number', 'Invoice value'
            records = []
            for _, row in b2b_df.iterrows():
                try:
                    record = {
                        "gstin": self._find_col(row, ["GSTIN", "Supplier"]),
                        "invoice_number": self._find_col(row, ["Invoice Number", "Inv No"]),
                        "amount": self._find_val(row, ["Invoice Value", "Total Value", "Amount"]),
                    }
                    if record["gstin"] and record["invoice_number"]:
                        records.append(record)
                except:
                    continue

            logger.info("portal_parser.completed", records_found=len(records))
            return records

        except Exception as e:
            logger.error("portal_parser.failed", error=str(e))
            return []

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
