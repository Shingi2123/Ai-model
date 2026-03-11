from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class StoryArcEngine:
    state_store: Any

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return default

    def _default_arc(self, context: Dict[str, Any]) -> Dict[str, Any]:
        day_type = str(context.get("day_type") or "day_off")
        if day_type in {"work_day", "travel_day"}:
            arc_type, title = "new_city_life", "Settling into a dynamic city rhythm"
        else:
            arc_type, title = "creative_phase", "Creative micro-routine for everyday life"

        return {
            "arc_id": f"arc_{context['date'].isoformat()}",
            "arc_type": arc_type,
            "title": title,
            "status": "active",
            "start_date": context["date"].isoformat(),
            "progress": 10,
            "description": "Auto-created long-term life arc.",
        }

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not hasattr(self.state_store, "load_story_arcs"):
            return {}

        arcs = self.state_store.load_story_arcs() or []
        active = next((a for a in arcs if str(a.get("status", "")).lower() == "active"), None)

        if not active:
            active = self._default_arc(context)
            if hasattr(self.state_store, "append_story_arc"):
                self.state_store.append_story_arc(active)
            return active

        progress = min(100, self._to_int(active.get("progress"), 0) + 5)
        active["progress"] = progress
        if progress >= 100:
            active["status"] = "completed"

        if hasattr(self.state_store, "save_story_arcs"):
            self.state_store.save_story_arcs(arcs)
        return active
