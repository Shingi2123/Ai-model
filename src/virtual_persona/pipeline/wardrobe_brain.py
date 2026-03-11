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

    def _balance_metrics(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        if not items:
            return {"style_balance": 1.0, "category_balance": 1.0, "season_balance": 1.0}

        categories: Dict[str, int] = {}
        style_tags: Dict[str, int] = {}
        season_tags: Dict[str, int] = {}

        for row in items:
            cat = str(row.get("category") or "").strip().lower()
            if cat:
                categories[cat] = categories.get(cat, 0) + 1
            for tag in self._split_csv(row.get("style_tags") or row.get("style_vector")):
                t = tag.lower()
                style_tags[t] = style_tags.get(t, 0) + 1
            for season in self._split_csv(row.get("season_tags")):
                s = season.lower()
                season_tags[s] = season_tags.get(s, 0) + 1

        def ratio(counts: Dict[str, int]) -> float:
            if not counts:
                return 0.3
            total = sum(counts.values())
            return round(len(counts) / max(total, 1), 3)

        return {
            "style_balance": ratio(style_tags),
            "category_balance": ratio(categories),
            "season_balance": ratio(season_tags),
        }

    def apply_daily_strategy(self, context: Dict[str, Any], selected_item_ids: List[str]) -> None:
        if not hasattr(self.state_store, "load_wardrobe_items"):
            return

        items = self.state_store.load_wardrobe_items() or []
        if not items:
            return

        profile = self.state_store.load_character_profile() if hasattr(self.state_store, "load_character_profile") else {}
        style_vector = self._profile_style_vector(profile)
        narrative = context.get("narrative_context")
        phase = getattr(narrative, "narrative_phase", "") if narrative else ""

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

        metrics = self._balance_metrics(list(by_id.values()))
        weak = [k for k, v in metrics.items() if v < 0.35]
        for axis in weak:
            if hasattr(self.state_store, "append_shopping_candidate"):
                self.state_store.append_shopping_candidate(
                    {
                        "candidate_id": f"style_evolution_{context['date'].isoformat()}_{axis}",
                        "category": "capsule",
                        "subcategory": axis,
                        "suggested_name": f"capsule upgrade for {axis}",
                        "reason": "style_evolution",
                        "priority": "medium",
                        "season": season,
                        "style_match": style_vector,
                        "gap_score": round(1 - metrics[axis], 3),
                        "status": "open",
                        "notes": f"auto balance metric: {metrics}",
                    }
                )

        if phase in {"social_phase", "exploration_phase", "recovery_phase"} and hasattr(self.state_store, "append_shopping_candidate"):
            target = {
                "social_phase": ("elevated_social_piece", "elegant"),
                "exploration_phase": ("active_exploration_piece", "active"),
                "recovery_phase": ("comfort_recovery_piece", "comfort"),
            }[phase]
            self.state_store.append_shopping_candidate(
                {
                    "candidate_id": f"narrative_{context['date'].isoformat()}_{phase}",
                    "category": "top",
                    "subcategory": target[1],
                    "suggested_name": target[0],
                    "reason": f"narrative_phase:{phase}",
                    "priority": "medium",
                    "season": season,
                    "style_match": style_vector,
                    "gap_score": 1,
                    "status": "open",
                    "notes": "Narrative-driven wardrobe refinement",
                }
            )

        self.state_store.save_wardrobe_items(list(by_id.values()))
