from __future__ import annotations

from agent.tools.handlers.knowledge import KNOWLEDGE_TOOLS
from agent.tools.handlers.learning import LEARNING_READ_TOOLS
from agent.tools.handlers.notification import NOTIFICATION_TOOLS
from agent.tools.handlers.safety import SAFETY_TOOLS
from agent.tools.handlers.write_actions import CORE_WRITE_TOOLS, LEARNING_WRITE_TOOLS

ALL_TOOLS = (
    *SAFETY_TOOLS,
    *LEARNING_READ_TOOLS,
    *KNOWLEDGE_TOOLS,
    *NOTIFICATION_TOOLS,
    *CORE_WRITE_TOOLS,
    *LEARNING_WRITE_TOOLS,
)

__all__ = [
    "ALL_TOOLS",
    "CORE_WRITE_TOOLS",
    "KNOWLEDGE_TOOLS",
    "LEARNING_READ_TOOLS",
    "LEARNING_WRITE_TOOLS",
    "NOTIFICATION_TOOLS",
    "SAFETY_TOOLS",
]
