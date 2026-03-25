"""
extractor_tool.py — PDF → Structured Text (hybrid extraction)
==============================================================
Single Responsibility: Convert raw PDF bytes into clean,
structured text that the LLM can understand.

Extraction strategy:
1. Try lightweight pypdf extraction for normal searchable PDFs
2. Fall back to Google Document AI for weak/complex documents
"""

import base64
import io
import json
import os
import time

import httpx
import jwt
import structlog

from agent.context import Context, ToolResult, DocType
from agent.interfaces import ToolInterface
from config.settings import settings

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
            raw_text = await self._extract_raw_text(context)

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

    async def _extract_raw_text(self, context: Context) -> str:
        lightweight_text = await self._extract_lightweight_text(context.raw_bytes)
        normalized_text = lightweight_text.strip()

        if normalized_text and not self._should_escalate_to_google(context, normalized_text):
            logger.info(
                "extractor_tool.using_lightweight_text_extraction",
                filename=context.filename,
                char_count=len(normalized_text),
            )
            return lightweight_text

        google_text = await self._extract_with_google_document_ai(context)
        if google_text and google_text.strip():
            return google_text

        if normalized_text:
            logger.warning(
                "extractor_tool.google_unavailable_or_failed_using_lightweight_text",
                filename=context.filename,
                char_count=len(normalized_text),
            )
            return lightweight_text

        raise RuntimeError("Unable to extract text with either pypdf or Google Document AI")

    def _should_escalate_to_google(self, context: Context, text: str) -> bool:
        if not text.strip():
            return True

        text_lower = text.lower()
        line_count = len([line for line in text.splitlines() if line.strip()])

        if len(text.strip()) < settings.EXTRACTION_LIGHTWEIGHT_MIN_CHARS:
            return True

        doc_type = context.doc_type

        if doc_type == DocType.BANK_STATEMENT:
            required_hints = ["opening balance", "closing balance", "account", "ifsc"]
            matched_hints = sum(1 for hint in required_hints if hint in text_lower)
            if matched_hints < 2 or line_count < 25:
                return True

        if doc_type in {DocType.INVOICE, DocType.RECONCILIATION}:
            invoice_hints = ["invoice", "gst", "tax", "amount", "total"]
            matched_hints = sum(1 for hint in invoice_hints if hint in text_lower)
            if matched_hints < 3 or line_count < 12:
                return True

        if doc_type in {DocType.GST_RETURN, DocType.TDS_CERTIFICATE} and line_count < 10:
            return True

        return False

    async def _extract_with_google_document_ai(self, context: Context) -> str | None:
        processor_ids = self._google_processors_for_doc_type(context.doc_type)
        if not processor_ids:
            logger.info("extractor_tool.google_processor_not_configured", filename=context.filename, doc_type=context.doc_type)
            return None

        access_token = await self._google_access_token()
        if not access_token:
            logger.warning("extractor_tool.google_access_token_unavailable", filename=context.filename)
            return None

        project_id = settings.GOOGLE_DOCUMENT_AI_PROJECT_ID.strip()
        location = settings.GOOGLE_DOCUMENT_AI_LOCATION.strip()
        payload = {
            "skipHumanReview": True,
            "rawDocument": {
                "mimeType": "application/pdf",
                "content": base64.b64encode(context.raw_bytes).decode("utf-8"),
            },
        }

        async with httpx.AsyncClient(timeout=settings.GOOGLE_DOCUMENT_AI_TIMEOUT_SECONDS) as client:
            for processor_id in processor_ids:
                endpoint = (
                    f"https://{location}-documentai.googleapis.com/v1/projects/{project_id}"
                    f"/locations/{location}/processors/{processor_id}:process"
                )
                try:
                    response = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {access_token}"},
                        json=payload,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "extractor_tool.google_document_ai_failed",
                        filename=context.filename,
                        doc_type=context.doc_type,
                        processor_id=processor_id,
                        status_code=exc.response.status_code,
                        error_body=exc.response.text[:500],
                    )
                    continue
                except Exception as exc:
                    logger.error(
                        "extractor_tool.google_document_ai_failed",
                        filename=context.filename,
                        doc_type=context.doc_type,
                        processor_id=processor_id,
                        error=str(exc),
                    )
                    continue

                document = response.json().get("document", {})
                text = str(document.get("text", "") or "")
                if not text.strip():
                    logger.warning(
                        "extractor_tool.google_document_ai_empty_text",
                        filename=context.filename,
                        doc_type=context.doc_type,
                        processor_id=processor_id,
                    )
                    continue

                logger.info(
                    "extractor_tool.using_google_document_ai",
                    filename=context.filename,
                    doc_type=context.doc_type,
                    processor_id=processor_id,
                    char_count=len(text),
                )
                return text

        return None

    async def _google_access_token(self) -> str | None:
        if settings.GOOGLE_DOCUMENT_AI_ACCESS_TOKEN.strip():
            return settings.GOOGLE_DOCUMENT_AI_ACCESS_TOKEN.strip()

        service_account = self._google_service_account_info()
        if not service_account:
            return None

        token_uri = service_account.get("token_uri", "https://oauth2.googleapis.com/token")
        now = int(time.time())
        payload = {
            "iss": service_account["client_email"],
            "scope": "https://www.googleapis.com/auth/cloud-platform",
            "aud": token_uri,
            "iat": now,
            "exp": now + 3600,
        }
        assertion = jwt.encode(payload, service_account["private_key"], algorithm="RS256")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    token_uri,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                )
                response.raise_for_status()
        except Exception as exc:
            logger.error("extractor_tool.google_oauth_failed", error=str(exc))
            return None

        return response.json().get("access_token")

    def _google_service_account_info(self) -> dict | None:
        raw_json = settings.GOOGLE_DOCUMENT_AI_SERVICE_ACCOUNT_JSON.strip()
        if raw_json:
            return json.loads(raw_json)

        candidate_paths = []
        configured_path = settings.GOOGLE_DOCUMENT_AI_SERVICE_ACCOUNT_PATH.strip()
        if configured_path:
            candidate_paths.append(configured_path)
        candidate_paths.extend([
            "./secrets/gcp-docai.json",
            "/app/secrets/gcp-docai.json",
        ])

        for json_path in candidate_paths:
            if not json_path or not os.path.exists(json_path):
                continue
            with open(json_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

        logger.warning("extractor_tool.google_service_account_not_found", paths=candidate_paths)
        return None

    def _google_processors_for_doc_type(self, doc_type: DocType) -> list[str]:
        def dedupe(values: list[str]) -> list[str]:
            result: list[str] = []
            seen: set[str] = set()
            for value in values:
                cleaned = value.strip()
                if not cleaned or cleaned in seen:
                    continue
                seen.add(cleaned)
                result.append(cleaned)
            return result

        if doc_type == DocType.INVOICE:
            return dedupe([
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_INVOICE,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
            ])
        if doc_type == DocType.BANK_STATEMENT:
            return dedupe([
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_BANK_STATEMENT,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
            ])
        if doc_type == DocType.GST_RETURN:
            return dedupe([
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_GST_RETURN,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
            ])
        if doc_type == DocType.TDS_CERTIFICATE:
            return dedupe([
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_TDS_CERTIFICATE,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
            ])
        if doc_type == DocType.RECONCILIATION:
            return dedupe([
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_RECONCILIATION,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
                settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
            ])
        return dedupe([
            settings.GOOGLE_DOCUMENT_AI_PROCESSOR_FORM,
            settings.GOOGLE_DOCUMENT_AI_PROCESSOR_OCR,
        ])

    async def _extract_lightweight_text(self, raw_bytes: bytes) -> str:
        """
        Lightweight extractor using pypdf for searchable PDFs.
        """
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except Exception as e:
            raise RuntimeError(f"All extraction methods failed: {e}")
