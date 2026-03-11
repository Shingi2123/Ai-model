from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Any

from virtual_persona.models.domain import OutfitSelection, WardrobeCatalog, WardrobeItem


logger = logging.getLogger(__name__)


class OutfitBuilderEngine:
    OUTERWEAR_THRESHOLD_C = 14

    def __init__(self, manager: "WardrobeManager") -> None:
        self.manager = manager

    def build(
        self,
        *,
        temp_c: float,
        condition: str,
        preferred_style: str,
        today: date,
        season: str,
        day_type: str,
        city: str,
        occasion: str,
    ) -> OutfitSelection:
        eligible = self._eligible_items(
            temp_c=temp_c,
            condition=condition,
            preferred_style=preferred_style,
            today=today,
            season=season,
            occasion=occasion,
            day_type=day_type,
        )
        logger.info("OutfitBuilder: eligible items=%s for city=%s day_type=%s", len(eligible), city, day_type)

        selected: Dict[str, WardrobeItem] = {}
        dress = self._pick_best(eligible, "dress")
        if dress:
            selected["dress"] = dress
        else:
            top = self._pick_best(eligible, "top")
            bottom = self._pick_best(eligible, "bottom")
            if top:
                selected["top"] = top
            if bottom:
                selected["bottom"] = bottom

        shoes = self._pick_best(eligible, "shoes")
        if shoes:
            selected["shoes"] = shoes

        if temp_c < self.OUTERWEAR_THRESHOLD_C:
            outerwear = self._pick_best(eligible, "outerwear")
            if outerwear:
                selected["outerwear"] = outerwear

        accessory = self._pick_best(eligible, "accessory")
        if accessory:
            selected["accessory"] = accessory

        selected = self._ensure_required(selected, temp_c=temp_c)

        for item in selected.values():
            item.last_used = today

        ordered_categories = ["dress", "top", "bottom", "shoes", "outerwear", "accessory"]
        selected_items = [selected[c] for c in ordered_categories if c in selected]
        ids = [i.id for i in selected_items]
        summary = ", ".join(i.name for i in selected_items)
        logger.info("OutfitBuilder: built outfit ids=%s", ids)
        return OutfitSelection(item_ids=ids, summary=summary)

    def _eligible_items(
        self,
        *,
        temp_c: float,
        condition: str,
        preferred_style: str,
        today: date,
        season: str,
        occasion: str,
        day_type: str,
    ) -> List[WardrobeItem]:
        eligible: List[WardrobeItem] = []
        for item in self.manager.catalog.items:
            if item.season and "all" not in item.season and season not in item.season:
                continue
            if not (item.temp_min_c <= temp_c <= item.temp_max_c):
                continue
            if condition not in item.weather_tags and "all" not in item.weather_tags:
                continue
            if preferred_style not in item.styles and "all" not in item.styles:
                continue
            if self.manager._days_since_used(item, today) < item.cooldown_days:
                continue
            if not self._occasion_match(item, occasion, day_type):
                continue
            eligible.append(item)
        return eligible

    @staticmethod
    def _occasion_match(item: WardrobeItem, occasion: str, day_type: str) -> bool:
        occasions = {v.strip() for v in item.styles if v.strip()}
        if not occasions:
            return True
        known_occasion_tags = {"work_day", "day_off", "travel_day", "event", "all"}
        if not (occasions & known_occasion_tags):
            return True
        normalized = {occasion.strip(), day_type.strip(), "all"}
        return bool(occasions & normalized) or "all" in occasions

    def _pick_best(self, eligible: List[WardrobeItem], category: str) -> WardrobeItem | None:
        candidates = [i for i in eligible if i.category == category]
        if not candidates:
            return None

        repeats = self._recent_repeats()
        candidates.sort(key=lambda i: (repeats.get(i.id, 0), self.manager._days_since_used(i, date.today())))
        return candidates[0]

    def _recent_repeats(self) -> Counter:
        if not self.manager.state_store or not hasattr(self.manager.state_store, "load_outfit_memory"):
            return Counter()
        repeats: Counter = Counter()
        memory = self.manager.state_store.load_outfit_memory() or []
        for row in memory[-20:]:
            for item_id in self.manager._split_csv(row.get("item_ids")):
                repeats[item_id] += 1
        return repeats

    def _ensure_required(self, selected: Dict[str, WardrobeItem], *, temp_c: float) -> Dict[str, WardrobeItem]:
        has_base = ("dress" in selected) or ("top" in selected and "bottom" in selected)
        if has_base and "shoes" in selected:
            return selected

        fallback = [i for i in self.manager.catalog.items if i.category in {"dress", "top", "bottom", "shoes", "outerwear"}]
        for item in fallback:
            if item.category == "dress":
                selected.setdefault("dress", item)
            elif item.category == "top" and "dress" not in selected:
                selected.setdefault("top", item)
            elif item.category == "bottom" and "dress" not in selected:
                selected.setdefault("bottom", item)
            elif item.category == "shoes":
                selected.setdefault("shoes", item)
            elif item.category == "outerwear" and temp_c < self.OUTERWEAR_THRESHOLD_C:
                selected.setdefault("outerwear", item)
        return selected


class WardrobeManager:
    def __init__(self, state_store=None, wardrobe_path: str = "config/wardrobe.example.json") -> None:
        if isinstance(state_store, str) and wardrobe_path == "config/wardrobe.example.json":
            wardrobe_path = state_store
            state_store = None
        self.state_store = state_store
        self.wardrobe_path = wardrobe_path
        self.catalog = self._load_catalog()
        self.outfit_builder = OutfitBuilderEngine(self)

    def _load_catalog(self) -> WardrobeCatalog:
        sheet_items = []

        if self.state_store:
            try:
                if hasattr(self.state_store, "load_wardrobe_items"):
                    sheet_items = self.state_store.load_wardrobe_items() or []
                elif hasattr(self.state_store, "load_wardrobe"):
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
            item_id = str(row.get("item_id") or row.get("id") or "").strip()
            if not item_id:
                continue

            category = str(row.get("category", "")).strip()
            status = str(row.get("status") or "active").strip().lower()
            if status not in {"active", ""}:
                continue
            name = str(row.get("name", "")).strip()

            styles = self._split_csv(row.get("styles") or row.get("style_tags"))
            occasion_tags = self._split_csv(row.get("occasion_tags"))
            if occasion_tags:
                styles = styles + [t for t in occasion_tags if t not in styles]
            colors = self._split_csv(row.get("colors") or row.get("color"))
            season = self._split_csv(row.get("season") or row.get("season_tags"))
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

    def select_outfit(
        self,
        temp_c: float,
        condition: str,
        preferred_style: str,
        today: date,
        day_type: str = "day_off",
        city: str = "",
        occasion: str | None = None,
    ) -> OutfitSelection:
        season_now = current_season(today.month)
        return self.outfit_builder.build(
            temp_c=temp_c,
            condition=condition,
            preferred_style=preferred_style,
            today=today,
            season=season_now,
            day_type=day_type,
            city=city,
            occasion=occasion or day_type,
        )

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
