"""bank_skill.py & tds_skill.py — Stub Skills"""
from typing import Any
from agent.context import Context
from agent.interfaces import BaseSkill
from tools.extractor_tool import ExtractorTool
from tools.bank_enrichment_tool import BankEnrichmentTool
from tools.parser_tool import ParserTool
from tools.validator_tool import ValidatorTool
from tools.confidence_scorer_tool import ConfidenceScorerTool
from memory.stores import CorrectionStore


class BankStatementSkill(BaseSkill):
    def __init__(self, correction_store: CorrectionStore | None = None):
        self._tools = [
            ExtractorTool(),
            ParserTool(correction_store=correction_store),
            BankEnrichmentTool(),
            ValidatorTool(),
            ConfidenceScorerTool(),
        ]

    @property
    def skill_name(self) -> str:
        return "bank_statement"

    async def run(self, context: Context) -> dict[str, Any]:
        for tool in self._tools:
            result = await tool.execute(context)
            context.add_tool_result(result)
            if not result.success and not isinstance(tool, (ValidatorTool, ConfidenceScorerTool)):
                raise RuntimeError(f"{tool.name} failed: {result.error}")
        return {"skill": self.skill_name, "extracted_data": context.extracted_data}


class TDSSkill(BaseSkill):
    def __init__(self, correction_store: CorrectionStore | None = None):
        self._tools = [ExtractorTool(), ParserTool(correction_store=correction_store), ValidatorTool(), ConfidenceScorerTool()]

    @property
    def skill_name(self) -> str:
        return "tds_certificate"

    async def run(self, context: Context) -> dict[str, Any]:
        for tool in self._tools:
            result = await tool.execute(context)
            context.add_tool_result(result)
            if not result.success and not isinstance(tool, (ValidatorTool, ConfidenceScorerTool)):
                raise RuntimeError(f"{tool.name} failed: {result.error}")
        return {"skill": self.skill_name, "extracted_data": context.extracted_data}
