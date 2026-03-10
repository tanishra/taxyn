"""
extractor_tool.py — PDF → Structured Text (uses Docling)
==========================================================
Single Responsibility: Convert raw PDF bytes into clean,
structured text that the LLM can understand.

Uses Docling (IBM) as the extraction engine.
Docling preserves tables, headings, and reading order —
critical for invoices and financial documents.

Why Docling over plain OCR?
- Tables are preserved as Markdown tables (not mangled text)
- Reading order is correct even in multi-column layouts
- 30x faster than traditional OCR
- Handles scanned PDFs via built-in OCR
"""

import tempfile
import os
import structlog
from agent.context import Context, ToolResult
from agent.interfaces import ToolInterface
from huggingface_hub import login
from config.settings import settings

if settings.HUGGINGFACE_TOKEN:
    login(token=settings.HUGGINGFACE_TOKEN)

logger = structlog.get_logger(__name__)


class ExtractorTool(ToolInterface):
    """
    Tool 1 of 4 in the pipeline.
    Input: raw PDF bytes in Context
    Output: clean structured text stored in context.extracted_data["raw_text"]
    """

    @property
    def name(self) -> str:
        return "extractor_tool"

    async def execute(self, context: Context) -> ToolResult:
        logger.info("extractor_tool.started", filename=context.filename)

        try:
            raw_text = await self._extract_with_docling(context.raw_bytes, context.filename)

            # Store result in context for next tool in pipeline
            context.extracted_data["raw_text"] = raw_text
            context.extracted_data["char_count"] = len(raw_text)

            logger.info(
                "extractor_tool.completed",
                char_count=len(raw_text),
                filename=context.filename,
            )

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={"raw_text": raw_text[:500]},  # preview in trace
                confidence=1.0,  # extraction is deterministic
            )

        except Exception as e:
            logger.error("extractor_tool.failed", error=str(e))
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
                confidence=0.0,
            )

    async def _extract_with_docling(self, raw_bytes: bytes, filename: str) -> str:
        """
        Use Docling to extract clean text from PDF.
        Writes to temp file (Docling needs a file path).
        """
        tmp_path = None
        try:
            import os
            from config.settings import settings
            if settings.HUGGINGFACE_TOKEN:
                os.environ["HF_TOKEN"] = settings.HUGGINGFACE_TOKEN
                os.environ["HUGGINGFACE_TOKEN"] = settings.HUGGINGFACE_TOKEN
            from docling.document_converter import DocumentConverter

            # Write bytes to temp file
            suffix = os.path.splitext(filename)[-1] or ".pdf"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            converter = DocumentConverter()
            result = converter.convert(tmp_path)

            # Export as Markdown — preserves table structure
            text = result.document.export_to_markdown()

            os.unlink(tmp_path)  # Clean up temp file
            return text

        except ImportError:
            # Fallback if Docling not installed: use basic PDF reader
            logger.warning("extractor_tool.docling_not_found, using fallback")
            return await self._fallback_extract(raw_bytes)

    async def _fallback_extract(self, raw_bytes: bytes) -> str:
        """
        Fallback extractor using pypdf if Docling unavailable.
        Less accurate for tables but always available.
        """
        import io
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            raise RuntimeError(f"All extraction methods failed: {e}")