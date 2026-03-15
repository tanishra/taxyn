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

    async def execute(self, context: Context) -> ToolResult:
        logger.info("splitter_tool.started", filename=context.filename)
        
        input_pdf_stream = io.BytesIO(context.raw_bytes)
        reader = PdfReader(input_pdf_stream)
        
        split_documents: List[Dict[str, Any]] = []
        current_writer = None
        current_doc_start_page = 0
        doc_counter = 0

        keywords_for_new_doc = ["TAX INVOICE", "INVOICE NO", "GSTIN", "BILL OF SUPPLY"]

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text().upper() if page.extract_text() else ""
            
            is_new_document_start = False
            if i == 0: # Always start a new document with the first page
                is_new_document_start = True
            else:
                # Check for keywords on subsequent pages
                if any(keyword in page_text for keyword in keywords_for_new_doc):
                    is_new_document_start = True
            
            if is_new_document_start and current_writer is not None:
                # Save the completed document
                output_pdf_stream = io.BytesIO()
                current_writer.write(output_pdf_stream)
                output_pdf_stream.seek(0)
                
                doc_counter += 1
                split_documents.append({
                    "raw_bytes": output_pdf_stream.read(),
                    "filename": f"{context.filename.replace('.pdf', '')}_part_{doc_counter}.pdf"
                })
                
                # Start a new writer for the new document
                current_writer = PdfWriter()
                current_doc_start_page = i

            if current_writer is None: # Initialize for the very first document or after a split
                current_writer = PdfWriter()

            current_writer.add_page(page)

        # Save the last document after the loop
        if current_writer is not None:
            output_pdf_stream = io.BytesIO()
            current_writer.write(output_pdf_stream)
            output_pdf_stream.seek(0)

            doc_counter += 1
            split_documents.append({
                "raw_bytes": output_pdf_stream.read(),
                "filename": f"{context.filename.replace('.pdf', '')}_part_{doc_counter}.pdf"
            })
        
        if len(split_documents) > 1:
            logger.info("splitter_tool.completed", original_filename=context.filename, num_splits=len(split_documents))
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"split_documents": split_documents},
                confidence=1.0 # Splitting is deterministic
            )
        else:
            logger.info("splitter_tool.no_split_needed", original_filename=context.filename)
            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"split_documents": [{"raw_bytes": context.raw_bytes, "filename": context.filename}]},
                confidence=1.0
            )

