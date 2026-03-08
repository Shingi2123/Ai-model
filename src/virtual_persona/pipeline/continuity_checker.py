from __future__ import annotations

from datetime import date
from typing import Dict, List

from virtual_persona.models.domain import ContinuityIssue, DayScene, OutfitSelection


class ContinuityChecker:
    def run(self, context: Dict, scenes: List[DayScene], outfit: OutfitSelection) -> List[ContinuityIssue]:
        issues: List[ContinuityIssue] = []
        history = context["recent_history"]
        current_city = context["city"]

        if history:
            last_city = history[-1]["city"]
            if last_city != current_city and context["day_type"] not in {"relocation", "airport_transfer", "flight_day"}:
                issues.append(ContinuityIssue(level="warning", code="CITY_JUMP", message="City changed without transfer day type."))

            today = context["date"]
            repeated = [h for h in history if today != date.fromisoformat(h["date"]) and set(h.get("outfit_ids", [])) == set(outfit.item_ids)]
            if repeated:
                issues.append(ContinuityIssue(level="warning", code="OUTFIT_REPEAT", message="Outfit combination repeated in recent window."))

        condition = context["weather"].condition
        if condition.startswith("rain") and any("sun" in s.description.lower() for s in scenes):
            issues.append(ContinuityIssue(level="error", code="LIGHTING_WEATHER_CLASH", message="Scene mentions bright sun during rain."))

        return issues
