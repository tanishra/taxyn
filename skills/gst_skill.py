"""
gst_skill.py — GST Return Processing Skill
"""
from typing import Any
from agent.context import Context
from agent.interfaces import BaseSkill
from tools.extractor_tool import ExtractorTool
from tools.parser_tool import ParserTool
from tools.validator_tool import ValidatorTool
from tools.confidence_scorer_tool import ConfidenceScorerTool
from memory.stores import CorrectionStore


class GSTSkill(BaseSkill):
    def __init__(self, correction_store: CorrectionStore | None = None):
        self._extractor = ExtractorTool()
        self._parser = ParserTool(correction_store=correction_store)
        self._validator = ValidatorTool()
        self._scorer = ConfidenceScorerTool()

    @property
    def skill_name(self) -> str:
        return "gst_return"

    async def run(self, context: Context) -> dict[str, Any]:
        for tool in [self._extractor, self._parser, self._validator, self._scorer]:
            result = await tool.execute(context)
            context.add_tool_result(result)
            if not result.success and tool != self._validator:
                raise RuntimeError(f"{tool.name} failed: {result.error}")
        return {"skill": self.skill_name, "extracted_data": context.extracted_data}
