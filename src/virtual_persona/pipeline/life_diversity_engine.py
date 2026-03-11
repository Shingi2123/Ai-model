from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LifeDiversityEngine:
    state_store: Any

    @staticmethod
    def _to_float(value: float, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _normalized_unique_ratio(values: List[str]) -> float:
        cleaned = [str(v).strip().lower() for v in values if str(v).strip()]
        if not cleaned:
            return 1.0
        return round(len(set(cleaned)) / len(cleaned), 3)

    def analyze(self, lookback_days: int = 7) -> Dict[str, float]:
        scene_rows = (self.state_store.load_scene_memory() or [])[-lookback_days:] if hasattr(self.state_store, "load_scene_memory") else []
        activity_rows = (self.state_store.load_activity_memory() or [])[-lookback_days:] if hasattr(self.state_store, "load_activity_memory") else []
        location_rows = (self.state_store.load_location_memory() or [])[-lookback_days:] if hasattr(self.state_store, "load_location_memory") else []
        outfit_rows = (self.state_store.load_outfit_memory() or [])[-lookback_days:] if hasattr(self.state_store, "load_outfit_memory") else []

        scene_diversity = self._normalized_unique_ratio([r.get("scene_id", "") for r in scene_rows])
        activity_diversity = self._normalized_unique_ratio([r.get("activity_id", "") for r in activity_rows])
        location_diversity = self._normalized_unique_ratio([r.get("location_id", "") for r in location_rows])
        outfit_diversity = self._normalized_unique_ratio([r.get("item_ids", "") for r in outfit_rows])

        avg = (scene_diversity + activity_diversity + location_diversity + outfit_diversity) / 4
        novelty_boost = max(0.0, 0.85 - avg)
        return {
            "scene_diversity": scene_diversity,
            "activity_diversity": activity_diversity,
            "location_diversity": location_diversity,
            "outfit_diversity": outfit_diversity,
            "novelty_boost": round(novelty_boost, 3),
            "low_diversity": 1.0 if avg < 0.55 else 0.0,
        }

