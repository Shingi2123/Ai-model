from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Any

from virtual_persona.models.domain import OutfitSelection, WardrobeCatalog, WardrobeItem


class WardrobeManager:
    def __init__(self, state_store=None, wardrobe_path: str = "config/wardrobe.example.json") -> None:
        if isinstance(state_store, str) and wardrobe_path == "config/wardrobe.example.json":
            wardrobe_path = state_store
            state_store = None
        self.state_store = state_store
        self.wardrobe_path = wardrobe_path
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> WardrobeCatalog:
        sheet_items = []

        if self.state_store and hasattr(self.state_store, "load_wardrobe"):
            try:
                sheet_items = self.state_store.load_wardrobe() or []
            except Exception:
                sheet_items = []

        if sheet_items:
            return self._catalog_from_sheet_rows(sheet_items)

        with Path(self.wardrobe_path).open("r", encoding="utf-8") as f:
            payload = json.load(f)

        if not payload.get("items"):
            payload["items"] = [
                {
                    "id": "top_cream_turtleneck",
                    "category": "top",
                    "name": "Cream turtleneck",
                    "styles": ["soft minimal", "all"],
                    "colors": ["cream"],
                    "season": ["winter", "autumn"],
                    "temp_min_c": -5,
                    "temp_max_c": 16,
                    "weather_tags": ["cloudy", "all"],
                    "cooldown_days": 1,
                    "last_used": None,
                },
                {
                    "id": "bottom_trousers_wool",
                    "category": "bottom",
                    "name": "Wool trousers",
                    "styles": ["soft minimal", "all"],
                    "colors": ["beige"],
                    "season": ["winter", "autumn"],
                    "temp_min_c": -5,
                    "temp_max_c": 16,
                    "weather_tags": ["cloudy", "all"],
                    "cooldown_days": 1,
                    "last_used": None,
                },
                {
                    "id": "shoes_white_sneakers",
                    "category": "shoes",
                    "name": "White sneakers",
                    "styles": ["soft minimal", "all"],
                    "colors": ["white"],
                    "season": ["all"],
                    "temp_min_c": -5,
                    "temp_max_c": 24,
                    "weather_tags": ["cloudy", "all"],
                    "cooldown_days": 1,
                    "last_used": None,
                },
            ]

        return WardrobeCatalog.from_dict(payload)

    def _catalog_from_sheet_rows(self, rows: List[Dict[str, Any]]) -> WardrobeCatalog:
        items: List[WardrobeItem] = []

        for row in rows:
            item_id = str(row.get("id", "")).strip()
            if not item_id:
                continue

            category = str(row.get("category", "")).strip()
            name = str(row.get("name", "")).strip()

            styles = self._split_csv(row.get("styles"))
            colors = self._split_csv(row.get("colors"))
            season = self._split_csv(row.get("season"))
            weather_tags = self._split_csv(row.get("weather_tags"))

            temp_min_c = self._to_int(row.get("temp_min_c"), 0)
            temp_max_c = self._to_int(row.get("temp_max_c"), 30)
            cooldown_days = self._to_int(row.get("cooldown_days"), 2)

            last_used_raw = row.get("last_used")
            last_used = None
            if last_used_raw:
                try:
                    last_used = date.fromisoformat(str(last_used_raw))
                except Exception:
                    last_used = None

            items.append(
                WardrobeItem(
                    id=item_id,
                    category=category,
                    name=name,
                    styles=styles or ["all"],
                    colors=colors or ["neutral"],
                    season=season or ["all"],
                    temp_min_c=temp_min_c,
                    temp_max_c=temp_max_c,
                    weather_tags=weather_tags or ["all"],
                    cooldown_days=cooldown_days,
                    last_used=last_used,
                )
            )

        return WardrobeCatalog.from_dict(
            {
                "items": [
                    {
                        "id": i.id,
                        "category": i.category,
                        "name": i.name,
                        "styles": i.styles,
                        "colors": i.colors,
                        "season": i.season,
                        "temp_min_c": i.temp_min_c,
                        "temp_max_c": i.temp_max_c,
                        "weather_tags": i.weather_tags,
                        "cooldown_days": i.cooldown_days,
                        "last_used": i.last_used.isoformat() if i.last_used else None,
                    }
                    for i in items
                ],
                "combination_rules": {
                    "required_categories": ["top", "bottom", "shoes"],
                    "optional_categories": ["outerwear", "accessory", "homewear", "travel_set", "dress"],
                    "forbidden_color_pairs": [],
                },
            }
        )

    @staticmethod
    def _split_csv(value: Any) -> List[str]:
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            if value is None or value == "":
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _days_since_used(item: WardrobeItem, today: date) -> int:
        if not item.last_used:
            return 10_000
        return (today - item.last_used).days

    def select_outfit(self, temp_c: float, condition: str, preferred_style: str, today: date) -> OutfitSelection:
        eligible: List[WardrobeItem] = []

        season_now = current_season(today.month)

        for item in self.catalog.items:
            if item.season and "all" not in item.season and season_now not in item.season:
                continue
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
            if cand and category not in selected:
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

            json.dump(
                {
                    "items": items,
                    "combination_rules": self.catalog.combination_rules.__dict__,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def current_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"
