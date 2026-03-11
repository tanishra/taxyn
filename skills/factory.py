"""
factory.py — Skill Factory (Factory Pattern)
=============================================
The factory creates the correct skill object based on doc type.

Why a Factory?
- AgentLoop and Planner never import skill classes directly
- Adding a new skill = register it here. Nothing else changes.
- Centralizes all skill creation logic in one place

This is the Open/Closed Principle in action:
- Open for extension (add new skills)
- Closed for modification (existing code untouched)
"""

import structlog
from agent.context import DocType
from agent.interfaces import BaseSkill

logger = structlog.get_logger(__name__)


class SkillFactory:
    """
    Creates skill instances by doc type.
    Skills are imported lazily to avoid circular imports.
    """

    def create(self, doc_type: DocType) -> BaseSkill:
        """
        Factory method: returns the correct skill for doc_type.
        Raises ValueError for unsupported types.
        """
        # Lazy imports — skills are only loaded when needed
        if doc_type == DocType.INVOICE:
            from skills.invoice_skill import InvoiceSkill
            return InvoiceSkill()

        elif doc_type == DocType.GST_RETURN:
            from skills.gst_skill import GSTSkill
            return GSTSkill()

        elif doc_type == DocType.BANK_STATEMENT:
            from skills.other_skills import BankStatementSkill
            return BankStatementSkill()

        elif doc_type == DocType.TDS_CERTIFICATE:
            from skills.other_skills import TDSSkill
            return TDSSkill()

        elif doc_type == DocType.RECONCILIATION:
            from skills.reconciliation_skill import ReconciliationSkill
            return ReconciliationSkill()

        else:
            # Default to invoice for unknown types
            logger.warning("skill_factory.unknown_type_fallback", doc_type=doc_type)
            from skills.invoice_skill import InvoiceSkill
            return InvoiceSkill()