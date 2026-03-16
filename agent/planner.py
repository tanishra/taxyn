"""
planner.py — Skill Selector (Strategy Pattern)
================================================
The Planner's only job: look at the Context and decide
which Skill should handle this document.

It uses a SkillFactory to create the correct skill.
AgentLoop never knows which skill was chosen — it just
calls skill.run(context). This is the Strategy Pattern.

Adding a new document type:
1. Create new Skill class
2. Register it in SkillFactory
3. Add detection logic here
→ AgentLoop and Planner core never change (OCP)
"""

import structlog
import io
from agent.context import Context, DocType
from agent.interfaces import PlannerInterface, BaseSkill
from skills.factory import SkillFactory
from memory.stores import SchemaStore

logger = structlog.get_logger(__name__)


class Planner(PlannerInterface):
    """
    Concrete planner implementation.
    Detects document type and returns the correct skill.
    """

    def __init__(self, skill_factory: SkillFactory, schema_store: SchemaStore):
        self._factory = skill_factory
        self._schema_store = schema_store

    async def plan(self, context: Context) -> BaseSkill:
        """
        Determine which skill to use.
        Doc type may already be set (by API route) or needs detection.
        """
        doc_type = context.doc_type

        if doc_type == DocType.UNKNOWN:
            doc_type = await self._detect_doc_type(context)
            context.doc_type = doc_type
            logger.info("planner.doc_type_detected", doc_type=doc_type)
            
            # ── RELOAD SCHEMA ─────────────────────────────────────────
            # Since doc_type was detected, we must reload the schema
            # to see if the tenant has a custom one for this type.
            new_schema = await self._schema_store.get_schema(
                context.tenant_id, 
                str(doc_type).split(".")[-1].lower()
            )
            context.extraction_schema = new_schema
            logger.info("planner.schema_reloaded", fields=list(new_schema.keys()))

        skill = self._factory.create(doc_type)
        return skill

    async def _detect_doc_type(self, context: Context) -> DocType:
        """
        Heuristic detection based on filename and content hints.
        Deterministic logic — no LLM involved here.
        """
        filename_lower = context.filename.lower()

        if any(k in filename_lower for k in ["invoice", "inv", "bill"]):
            return DocType.INVOICE
        if any(k in filename_lower for k in ["gst", "gstr"]):
            return DocType.GST_RETURN
        if any(k in filename_lower for k in ["bank", "statement", "ledger"]):
            return DocType.BANK_STATEMENT
        if any(k in filename_lower for k in ["tds", "form16", "form-16"]):
            return DocType.TDS_CERTIFICATE
        if any(k in filename_lower for k in ["recon", "2a", "2b"]):
            return DocType.RECONCILIATION

        content_hint = self._peek_pdf_text(context.raw_bytes)
        if any(k in content_hint for k in ["tax invoice", "invoice no", "bill to"]):
            return DocType.INVOICE
        if any(k in content_hint for k in ["gstr-1", "gstr-2a", "gstr-2b", "gst return"]):
            return DocType.GST_RETURN
        if any(k in content_hint for k in ["account statement", "opening balance", "closing balance", "ifsc"]):
            return DocType.BANK_STATEMENT
        if any(k in content_hint for k in ["form 16", "form 16a", "tds certificate", "deductor"]):
            return DocType.TDS_CERTIFICATE
        if any(k in content_hint for k in ["reconciliation", "missing in portal", "2a", "2b"]):
            return DocType.RECONCILIATION

        # Default fallback
        return DocType.INVOICE

    def _peek_pdf_text(self, raw_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw_bytes))
            snippets = []
            for page in reader.pages[:2]:
                snippets.append(page.extract_text() or "")
            return "\n".join(snippets).lower()
        except Exception:
            return ""
