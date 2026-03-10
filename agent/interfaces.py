"""
interfaces.py — Core Abstractions for Taxyn
============================================
All major components depend on these interfaces, NOT concrete classes.
This is the Dependency Inversion Principle in action.

Adding a new tool/skill/memory store = implement the interface.
Nothing else changes.
"""

from abc import ABC, abstractmethod
from typing import Any
from agent.context import Context, ToolResult


# ─────────────────────────────────────────────────────────────
# TOOL INTERFACE  (Single Responsibility + Liskov Substitution)
# Every tool does ONE job and is safely substitutable
# ─────────────────────────────────────────────────────────────
class ToolInterface(ABC):
    """
    Contract every Tool must follow.
    Input: Context object
    Output: ToolResult (structured, typed)
    """

    @abstractmethod
    async def execute(self, context: Context) -> ToolResult:
        """Execute the tool's single responsibility."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...


# ─────────────────────────────────────────────────────────────
# SKILL INTERFACE  (Open/Closed Principle)
# Add new doc type = new Skill. Never modify existing skills.
# ─────────────────────────────────────────────────────────────
class BaseSkill(ABC):
    """
    Abstract base for all document processing skills.
    Each skill composes tools in the correct order for its domain.
    """

    @abstractmethod
    async def run(self, context: Context) -> dict[str, Any]:
        """Execute the full skill pipeline for this document type."""
        ...

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """Unique skill identifier (e.g. 'invoice', 'gst', 'bank_statement')"""
        ...


# ─────────────────────────────────────────────────────────────
# MEMORY REPOSITORY INTERFACE  (Repository Pattern)
# Swap Postgres for Redis or MongoDB = new class only
# ─────────────────────────────────────────────────────────────
class MemoryRepositoryInterface(ABC):
    """Contract for all memory stores."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        ...

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


# ─────────────────────────────────────────────────────────────
# CHANNEL INTERFACE  (Adapter Pattern)
# REST, Webhook, WhatsApp = different adapters, same interface
# ─────────────────────────────────────────────────────────────
class ChannelInterface(ABC):
    """Contract for all input channels."""

    @abstractmethod
    async def parse_request(self, raw_input: Any) -> Context:
        """Convert raw channel input into a Context object."""
        ...


# ─────────────────────────────────────────────────────────────
# PLANNER INTERFACE  (Strategy Pattern)
# Swap planning strategies without touching AgentLoop
# ─────────────────────────────────────────────────────────────
class PlannerInterface(ABC):
    """Decides which skill to use based on context."""

    @abstractmethod
    async def plan(self, context: Context) -> BaseSkill:
        """Return the correct skill for this document type."""
        ...