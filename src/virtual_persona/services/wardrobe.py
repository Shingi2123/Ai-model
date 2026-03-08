from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

from virtual_persona.models.domain import OutfitSelection, WardrobeCatalog, WardrobeItem


class WardrobeManager:
    def __init__(self, wardrobe_path: str = "config/wardrobe.example.json") -> None:
        with Path(wardrobe_path).open("r", encoding="utf-8") as f:
            self.catalog = WardrobeCatalog.from_dict(json.load(f))

    @staticmethod
    def _days_since_used(item: WardrobeItem, today: date) -> int:
        if not item.last_used:
            return 10_000
        return (today - item.last_used).days

    def select_outfit(self, temp_c: float, condition: str, preferred_style: str, today: date) -> OutfitSelection:
        eligible: List[WardrobeItem] = []
        for item in self.catalog.items:
            if not (item.temp_min_c <= temp_c <= item.temp_max_c):
                continue
            if condition not in item.weather_tags and "all" not in item.weather_tags:
                continue
            if preferred_style not in item.styles and "all" not in item.styles:
                continue
            if self._days_since_used(item, today) < item.cooldown_days:
                continue
            eligible.append(item)

        required = self.catalog.combination_rules.required_categories
        selected: Dict[str, WardrobeItem] = {}
        for category in required:
            cand = next((i for i in eligible if i.category == category), None)
            if cand:
                selected[category] = cand

        for category in self.catalog.combination_rules.optional_categories:
            cand = next((i for i in eligible if i.category == category), None)
            if cand:
                selected[category] = cand

        if len([c for c in required if c in selected]) != len(required):
            fallback = [i for i in self.catalog.items if i.category in required][: len(required)]
            selected = {i.category: i for i in fallback}

        for item in selected.values():
            item.last_used = today

        ids = [i.id for i in selected.values()]
        summary = ", ".join(i.name for i in selected.values())
        return OutfitSelection(item_ids=ids, summary=summary)

    def persist(self, wardrobe_path: str = "data/state/wardrobe_state.json") -> None:
        Path(wardrobe_path).parent.mkdir(parents=True, exist_ok=True)
        with Path(wardrobe_path).open("w", encoding="utf-8") as f:
            items = []
            for i in self.catalog.items:
                item_dict = i.__dict__.copy()
                item_dict["last_used"] = i.last_used.isoformat() if i.last_used else None
                items.append(item_dict)
            json.dump({"items": items, "combination_rules": self.catalog.combination_rules.__dict__}, f, ensure_ascii=False, indent=2)


def current_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"
