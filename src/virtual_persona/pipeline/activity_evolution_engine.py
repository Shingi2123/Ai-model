from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ActivityEvolutionEngine:
    state_store: Any

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except Exception:
            return default

    def run(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not hasattr(self.state_store, "load_activity_memory"):
            return []

        rows = self.state_store.load_activity_memory() or []
        repeated = [r for r in rows if self._to_int(r.get("usage_count")) >= 6]
        if not repeated:
            return []

        out: List[Dict[str, Any]] = []
        for i, row in enumerate(repeated[:3], start=1):
            origin = str(row.get("activity_id") or row.get("activity_type") or "daily_activity")
            generated_variant = f"{origin}_variant_{i}"
            evo_payload = {
                "activity_id": f"ae_{context['date'].isoformat()}_{i}",
                "origin_activity": origin,
                "generated_variant": generated_variant,
                "reason": "repetition_detected",
                "status": "candidate",
            }
            if hasattr(self.state_store, "append_activity_evolution"):
                self.state_store.append_activity_evolution(evo_payload)

            if hasattr(self.state_store, "append_activity_candidate"):
                self.state_store.append_activity_candidate(
                    {
                        "candidate_id": f"activity_evolved_{context['date'].isoformat()}_{i}",
                        "activity_code": generated_variant,
                        "activity_label": generated_variant.replace("_", " "),
                        "day_type": context.get("day_type", "day_off"),
                        "time_block": "afternoon",
                        "city": context.get("city", ""),
                        "season": getattr(context.get("life_state"), "season", "all"),
                        "mood_fit": "curious",
                        "fatigue_min": 0,
                        "fatigue_max": 7,
                        "weather_fit": "all",
                        "source_context": "activity_evolution_engine",
                        "generated_by_ai": True,
                        "status": "candidate",
                        "score": 0.81,
                        "notes": f"Generated from {origin}",
                    }
                )
            out.append(evo_payload)
        return out
