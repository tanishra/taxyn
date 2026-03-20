from __future__ import annotations

import csv
import io
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring


class ERPExporter:
    def export(self, doc_type: str, extracted_data: dict, export_format: str) -> tuple[bytes, str, str]:
        normalized_doc_type = (doc_type or "unknown").lower()
        if export_format == "tally_xml":
            content = self._build_tally_xml(normalized_doc_type, extracted_data)
            return content, "application/xml", "xml"
        if export_format == "zoho_csv":
            content = self._build_csv(normalized_doc_type, extracted_data, target="zoho")
            return content, "text/csv", "csv"
        if export_format == "quickbooks_csv":
            content = self._build_csv(normalized_doc_type, extracted_data, target="quickbooks")
            return content, "text/csv", "csv"
        raise ValueError("Unsupported export format")

    def _build_tally_xml(self, doc_type: str, data: dict) -> bytes:
        envelope = Element("ENVELOPE")
        header = SubElement(envelope, "HEADER")
        SubElement(header, "TALLYREQUEST").text = "Import Data"

        body = SubElement(envelope, "BODY")
        import_data = SubElement(body, "IMPORTDATA")
        request_desc = SubElement(import_data, "REQUESTDESC")
        SubElement(request_desc, "REPORTNAME").text = "Vouchers"
        request_data = SubElement(import_data, "REQUESTDATA")

        message = SubElement(request_data, "TALLYMESSAGE")
        voucher = SubElement(message, "VOUCHER", VCHTYPE="Purchase", ACTION="Create")

        SubElement(voucher, "DATE").text = self._tally_date(data.get("date"))
        SubElement(voucher, "VOUCHERNUMBER").text = str(data.get("invoice_number") or data.get("reference_number") or "")
        SubElement(voucher, "PARTYNAME").text = str(data.get("vendor_name") or data.get("deductor_name") or "Unknown Party")
        SubElement(voucher, "NARRATION").text = self._narration(doc_type, data)
        SubElement(voucher, "VOUCHERTYPENAME").text = "Purchase"

        amount = self._to_float(data.get("amount"))
        taxable_value = self._to_float(data.get("taxable_value"))
        gst_amount = self._to_float(data.get("gst_amount")) or (
            self._to_float(data.get("cgst")) + self._to_float(data.get("sgst")) + self._to_float(data.get("igst"))
        )

        inventory_entry = SubElement(voucher, "ALLINVENTORYENTRIES.LIST")
        SubElement(inventory_entry, "STOCKITEMNAME").text = str(data.get("hsn_sac") or "Services")
        SubElement(inventory_entry, "ISDEEMEDPOSITIVE").text = "No"
        SubElement(inventory_entry, "RATE").text = str(amount or taxable_value or 0)
        SubElement(inventory_entry, "AMOUNT").text = str(amount or taxable_value or 0)

        ledger_party = SubElement(voucher, "LEDGERENTRIES.LIST")
        SubElement(ledger_party, "LEDGERNAME").text = str(data.get("vendor_name") or "Sundry Creditors")
        SubElement(ledger_party, "ISDEEMEDPOSITIVE").text = "Yes"
        SubElement(ledger_party, "AMOUNT").text = str(-(amount or taxable_value or 0))

        if gst_amount:
            ledger_tax = SubElement(voucher, "LEDGERENTRIES.LIST")
            SubElement(ledger_tax, "LEDGERNAME").text = "Input GST"
            SubElement(ledger_tax, "ISDEEMEDPOSITIVE").text = "No"
            SubElement(ledger_tax, "AMOUNT").text = str(gst_amount)

        return tostring(envelope, encoding="utf-8", xml_declaration=True)

    def _build_csv(self, doc_type: str, data: dict, target: str) -> bytes:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self._csv_headers(target))
        writer.writeheader()
        for row in self._csv_rows(doc_type, data, target):
            writer.writerow(row)
        return output.getvalue().encode("utf-8")

    def _csv_headers(self, target: str) -> list[str]:
        if target == "zoho":
            return [
                "Vendor Name",
                "Bill Number",
                "Bill Date",
                "Due Date",
                "GSTIN",
                "Place Of Supply",
                "Item Description",
                "Quantity",
                "Rate",
                "Taxable Value",
                "GST Amount",
                "Total Amount",
            ]
        return [
            "Vendor",
            "Reference No",
            "Txn Date",
            "Due Date",
            "GST Registration No",
            "Item",
            "Qty",
            "Rate",
            "Taxable Amount",
            "Tax Amount",
            "Gross Total",
        ]

    def _csv_rows(self, doc_type: str, data: dict, target: str) -> list[dict]:
        line_items = data.get("line_items")
        if not isinstance(line_items, list) or not line_items:
            line_items = [{}]

        rows = []
        for item in line_items:
            line = item if isinstance(item, dict) else {}
            qty = line.get("quantity") or line.get("qty") or 1
            rate = line.get("rate") or line.get("unit_price") or data.get("amount") or ""
            description = line.get("description") or line.get("item") or line.get("name") or doc_type.replace("_", " ").title()
            taxable_value = line.get("taxable_value") or data.get("taxable_value") or data.get("amount") or ""
            gst_amount = (
                line.get("gst_amount")
                or data.get("gst_amount")
                or self._to_float(data.get("cgst")) + self._to_float(data.get("sgst")) + self._to_float(data.get("igst"))
            )

            if target == "zoho":
                rows.append(
                    {
                        "Vendor Name": data.get("vendor_name") or data.get("deductor_name") or "",
                        "Bill Number": data.get("invoice_number") or data.get("reference_number") or "",
                        "Bill Date": data.get("date") or "",
                        "Due Date": data.get("due_date") or "",
                        "GSTIN": data.get("supplier_gstin") or data.get("vendor_gstin") or "",
                        "Place Of Supply": data.get("place_of_supply") or "",
                        "Item Description": description,
                        "Quantity": qty,
                        "Rate": rate,
                        "Taxable Value": taxable_value,
                        "GST Amount": gst_amount,
                        "Total Amount": data.get("amount") or taxable_value,
                    }
                )
            else:
                rows.append(
                    {
                        "Vendor": data.get("vendor_name") or data.get("deductor_name") or "",
                        "Reference No": data.get("invoice_number") or data.get("reference_number") or "",
                        "Txn Date": data.get("date") or "",
                        "Due Date": data.get("due_date") or "",
                        "GST Registration No": data.get("supplier_gstin") or data.get("vendor_gstin") or "",
                        "Item": description,
                        "Qty": qty,
                        "Rate": rate,
                        "Taxable Amount": taxable_value,
                        "Tax Amount": gst_amount,
                        "Gross Total": data.get("amount") or taxable_value,
                    }
                )
        return rows

    def _narration(self, doc_type: str, data: dict) -> str:
        reference = data.get("invoice_number") or data.get("reference_number") or ""
        party = data.get("vendor_name") or data.get("deductor_name") or ""
        return f"{doc_type.replace('_', ' ').title()} import for {party} {reference}".strip()

    def _tally_date(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return datetime.utcnow().strftime("%Y%m%d")
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y%m%d")
            except ValueError:
                continue
        return datetime.utcnow().strftime("%Y%m%d")

    def _to_float(self, value: object) -> float:
        try:
            return float(str(value).replace(",", "").replace("₹", "").strip())
        except (TypeError, ValueError):
            return 0.0
