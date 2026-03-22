from __future__ import annotations

from typing import Any, Dict

from virtual_persona.models.domain import BehaviorState
from virtual_persona.pipeline.behavior_engine import BehaviorEngine, build_behavior


class BehavioralLogicEngine(BehaviorEngine):
    def build(self, context: Dict[str, Any]) -> BehaviorState:
        return super().build(context)


__all__ = ["BehavioralLogicEngine", "BehaviorEngine", "build_behavior"]
