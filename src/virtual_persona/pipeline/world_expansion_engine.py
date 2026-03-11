from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class WorldExpansionEngine:
    state_store: Any

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _safe_city(context: Dict[str, Any]) -> str:
        return str(context.get("city") or "").strip()

    def _recent_scenes(self, lookback_days: int = 14) -> List[Dict[str, Any]]:
        if not hasattr(self.state_store, "load_scene_memory"):
            return []
        return (self.state_store.load_scene_memory() or [])[-lookback_days:]

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self._recent_scenes()
        if not rows or not hasattr(self.state_store, "append_world_candidate"):
            return []

        city = self._safe_city(context)
        out: List[Dict[str, Any]] = []

        overused = [r for r in rows if self._norm(r.get("status")) in {"overused", "active"} and int(float(r.get("usage_count", 0) or 0)) >= 5]
        for i, row in enumerate(overused[:3], start=1):
            scene_id = self._norm(row.get("scene_id"))
            location_hint = scene_id.split(":")[-1].replace("_", " ") if scene_id else "city place"

            variants = [
                ("location", f"{location_hint} roastery", "new_location_from_repetition"),
                ("scene", f"Micro-scene near {location_hint}", "new_scene_from_repetition"),
            ]
            for j, (candidate_type, name, reason) in enumerate(variants, start=1):
                payload = {
                    "candidate_id": f"world_{context['date'].isoformat()}_{i}_{j}",
                    "candidate_type": candidate_type,
                    "name": name,
                    "city": city,
                    "description": f"Auto-generated to reduce repetition around: {scene_id}",
                    "source_reason": reason,
                    "priority": "medium",
                    "status": "candidate",
                }
                self.state_store.append_world_candidate(payload)
                out.append(payload)

        return out
