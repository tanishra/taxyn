"""
splitter_tool.py — Automatic PDF Document Splitter
==================================================
Single Responsibility: Takes a multi-page PDF and intelligently
splits it into individual document PDFs based on content heuristics.
"""

import io
import structlog
from typing import List, Dict, Any
from pypdf import PdfReader, PdfWriter
from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface

logger = structlog.get_logger(__name__)

class SplitterTool(ToolInterface):
    """
    Tool to split a multi-page PDF into individual documents.
    Heuristics:
    1. Look for 'Tax Invoice' or 'Invoice No.' on a page.
    2. A new document starts if these keywords are found on a page,
       and it's not the first page of the original PDF OR if the page is the first of the original PDF
       and other documents have already been split from it.
    """

    @property
    def name(self) -> str:
        return "splitter_tool"

    def split_document(self, raw_bytes: bytes, filename: str = "document.pdf") -> List[Dict[str, Any]]:
        context = Context(raw_bytes=raw_bytes, filename=filename)
        result = self._split(context)
        return result["split_documents"]

    async def execute(self, context: Context) -> ToolResult:
        logger.info("splitter_tool.started", filename=context.filename)
        split_payload = self._split(context)
        split_count = len(split_payload["split_documents"])

        if split_count > 1:
            logger.info("splitter_tool.completed", original_filename=context.filename, num_splits=split_count)
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=split_payload,
                confidence=1.0 # Splitting is deterministic
            )
        else:
            logger.info("splitter_tool.no_split_needed", original_filename=context.filename)
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=split_payload,
                confidence=1.0
            )

    def _split(self, context: Context) -> Dict[str, Any]:
        input_pdf_stream = io.BytesIO(context.raw_bytes)
        reader = PdfReader(input_pdf_stream)

        split_documents: List[Dict[str, Any]] = []
        current_writer = None
        doc_counter = 0

        keywords_for_new_doc = ["TAX INVOICE", "INVOICE NO", "BILL OF SUPPLY", "ORIGINAL FOR RECIPIENT"]

        for i, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").upper()

            is_new_document_start = i == 0
            if i > 0 and any(keyword in page_text for keyword in keywords_for_new_doc):
                is_new_document_start = True

            if is_new_document_start and current_writer is not None:
                output_pdf_stream = io.BytesIO()
                current_writer.write(output_pdf_stream)
                output_pdf_stream.seek(0)

                doc_counter += 1
                split_documents.append({
                    "raw_bytes": output_pdf_stream.read(),
                    "filename": f"{context.filename.replace('.pdf', '')}_part_{doc_counter}.pdf"
                })

                current_writer = PdfWriter()

            if current_writer is None:
                current_writer = PdfWriter()

            current_writer.add_page(page)

        if current_writer is not None:
            output_pdf_stream = io.BytesIO()
            current_writer.write(output_pdf_stream)
            output_pdf_stream.seek(0)

            doc_counter += 1
            split_documents.append({
                "raw_bytes": output_pdf_stream.read(),
                "filename": f"{context.filename.replace('.pdf', '')}_part_{doc_counter}.pdf"
            })

        return {
            "split_documents": split_documents or [{"raw_bytes": context.raw_bytes, "filename": context.filename}]
        }
