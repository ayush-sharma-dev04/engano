"""Review Orchestrator / Coordinator Agent.

Re-exports CoordinatorAgent and backward-compatible ReviewOrchestrator interface.
"""

from ai_engine.agents.coordinator import (
    CoordinatorAgent,
    ReviewOrchestrator,
    _route_decision,
)

__all__ = [
    "CoordinatorAgent",
    "ReviewOrchestrator",
    "_route_decision",
]
