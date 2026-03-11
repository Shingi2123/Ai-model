from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class WardrobeBrain:
    state_store: Any

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _split_csv(value: Any) -> List[str]:
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def _profile_style_vector(self, profile: Dict[str, Any]) -> str:
        style = str(profile.get("style_profile") or "soft feminine realistic").strip()
        colors = str(profile.get("favorite_colors") or "beige,cream,white").strip()
        return f"{style}; palette={colors}"

    def apply_daily_strategy(self, context: Dict[str, Any], selected_item_ids: List[str]) -> None:
        if not hasattr(self.state_store, "load_wardrobe_items"):
            return

        items = self.state_store.load_wardrobe_items() or []
        if not items:
            return

        profile = self.state_store.load_character_profile() if hasattr(self.state_store, "load_character_profile") else {}
        style_vector = self._profile_style_vector(profile)

        by_id = {str(row.get("item_id") or row.get("id") or "").strip(): row for row in items}
        category_count: Dict[str, int] = {}

        for item in by_id.values():
            if not item.get("status"):
                item["status"] = "active"
            item.setdefault("capsule_role", "core")
            item.setdefault("style_vector", style_vector)
            item.setdefault("priority_score", 1)
            category = str(item.get("category") or "").strip()
            if category:
                category_count[category] = category_count.get(category, 0) + 1

            wear_count = self._to_int(item.get("wear_count"))
            if wear_count >= 35 and item.get("status") == "active":
                item["status"] = "reactivate_candidate"
                if hasattr(self.state_store, "append_wardrobe_action"):
                    self.state_store.append_wardrobe_action(
                        {
                            "date": context["date"].isoformat(),
                            "action_type": "temporary_pause",
                            "target_item_id": item.get("item_id"),
                            "reason": f"overused:{wear_count}",
                            "status": "suggested",
                            "context_day_type": context.get("day_type", ""),
                            "context_season": getattr(context.get("life_state"), "season", "all"),
                            "context_city": context.get("city", ""),
                            "notes": "Pause from rotation to avoid repetitive visual continuity",
                        }
                    )

        for item_id in selected_item_ids:
            item = by_id.get(item_id)
            if not item:
                continue
            item["priority_score"] = max(1, self._to_int(item.get("priority_score"), 1) - 1)

        tops = category_count.get("top", 0)
        bottoms = category_count.get("bottom", 0)
        outerwear = category_count.get("outerwear", 0)
        season = getattr(context.get("life_state"), "season", "all")

        if tops > bottoms + 2 and hasattr(self.state_store, "append_shopping_candidate"):
            self.state_store.append_shopping_candidate(
                {
                    "candidate_id": f"style_gap_{context['date'].isoformat()}_bottom",
                    "category": "bottom",
                    "subcategory": "versatile",
                    "suggested_name": "Базовые брюки для капсулы",
                    "reason": "capsule_balance_gap",
                    "priority": "high",
                    "season": season,
                    "style_match": style_vector,
                    "gap_score": tops - bottoms,
                    "status": "open",
                    "notes": "Need balancing bottom for repeat-safe combinations",
                }
            )

        if season in {"autumn", "winter"} and outerwear < 2 and hasattr(self.state_store, "append_shopping_candidate"):
            self.state_store.append_shopping_candidate(
                {
                    "candidate_id": f"style_gap_{context['date'].isoformat()}_outerwear",
                    "category": "outerwear",
                    "subcategory": "warm",
                    "suggested_name": "Тёплая верхняя одежда в спокойной палитре",
                    "reason": "seasonal_gap",
                    "priority": "medium",
                    "season": season,
                    "style_match": style_vector,
                    "gap_score": 2 - outerwear,
                    "status": "open",
                    "notes": "Season requires extra outer layer options",
                }
            )

        self.state_store.save_wardrobe_items(list(by_id.values()))
