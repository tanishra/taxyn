"""
loop.py — The AgentLoop (Stateless Orchestrator)
=================================================
This is the BRAIN of Taxyn.

What it does:
1. Receives a Context object
2. Asks the Planner: "which skill should handle this?"
3. Runs the skill
4. Handles output routing (confident → response, unsure → HITL)
5. Logs everything for observability

What it does NOT do:
- It does NOT hold any state (stateless = horizontally scalable)
- It does NOT make business decisions (that's the skill's job)
- It does NOT know about HTTP, databases, or LLMs directly

Think of AgentLoop as a project manager:
- It delegates to specialists (skills)
- It tracks progress (context)
- It escalates when unsure (HITL)
- It never does the actual work itself
"""

import time
import structlog
from agent.context import Context, ProcessingStatus
from agent.interfaces import PlannerInterface
from output.serializer import ResponseSerializer
from output.hitl_queue import HITLQueue
from observability.tracer import Tracer
from config.settings import settings

logger = structlog.get_logger(__name__)


class AgentLoop:
    """
    Central stateless orchestrator.

    Depends on abstractions (PlannerInterface), not concrete classes.
    → Dependency Inversion Principle
    """

    def __init__(
        self,
        planner: PlannerInterface,
        serializer: ResponseSerializer,
        hitl_queue: HITLQueue,
        tracer: Tracer,
    ):
        # All dependencies injected — no hidden globals
        self._planner = planner
        self._serializer = serializer
        self._hitl_queue = hitl_queue
        self._tracer = tracer

    async def run(self, context: Context) -> dict:
        """
        Execute the full document processing pipeline.

        Flow:
        Context → Plan → Skill → Confidence Check → Output
        """
        start_time = time.time()

        log = logger.bind(
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            doc_type=context.doc_type,
            filename=context.filename,
        )

        try:
            log.info("agent_loop.started")
            context.status = ProcessingStatus.PROCESSING

            # ── Step 1: Plan (which skill handles this doc type?) ──
            skill = await self._planner.plan(context)
            log.info("agent_loop.skill_selected", skill=skill.skill_name)

            # ── Step 2: Execute skill pipeline ────────────────────
            result = await skill.run(context)
            log.info("agent_loop.skill_completed", skill=skill.skill_name)

            # ── Step 3: Confidence gate ────────────────────────────
            # This is a DETERMINISTIC decision — not made by AI
            # If confidence is low, we route to human review
            if context.overall_confidence < settings.CONFIDENCE_THRESHOLD:
                log.warning(
                    "agent_loop.low_confidence",
                    confidence=context.overall_confidence,
                    threshold=settings.CONFIDENCE_THRESHOLD,
                )
                context.status = ProcessingStatus.NEEDS_REVIEW
                await self._hitl_queue.enqueue(context)
                return self._serializer.needs_review_response(context)

            # ── Step 4: Success path ───────────────────────────────
            context.status = ProcessingStatus.COMPLETED
            context.processing_time_ms = (time.time() - start_time) * 1000

            # ── Step 5: Trace for observability ───────────────────
            await self._tracer.record(context)
            log.info(
                "agent_loop.completed",
                confidence=context.overall_confidence,
                time_ms=context.processing_time_ms,
            )

            return self._serializer.success_response(context)

        except Exception as e:
            context.status = ProcessingStatus.FAILED
            context.processing_time_ms = (time.time() - start_time) * 1000
            log.error("agent_loop.failed", error=str(e), exc_info=True)
            await self._tracer.record(context)
            return self._serializer.error_response(context, str(e))