from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class AssetEvolutionEngine:
    state_store: Any

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except Exception:
            return default

    def _update_wardrobe_memory(self, package: Any, weather_summary: str) -> None:
        if not hasattr(self.state_store, "load_wardrobe_items"):
            return

        items = self.state_store.load_wardrobe_items() or []
        if not items:
            return

        by_id: Dict[str, Dict[str, Any]] = {}
        for row in items:
            row_id = str(row.get("item_id") or row.get("id") or "").strip()
            if not row_id:
                continue
            if not row.get("item_id"):
                row["item_id"] = row_id
            if not row.get("status"):
                row["status"] = "active"
            by_id[row_id] = row

        used_ids = set(package.outfit.item_ids)
        for item_id in used_ids:
            row = by_id.get(item_id)
            if not row:
                continue
            row["last_used"] = package.date.isoformat()
            row["wear_count"] = self._to_int(row.get("wear_count")) + 1
            row["times_in_content"] = self._to_int(row.get("times_in_content")) + 1
            if row.get("status") in {"inactive", "deprecated", "seasonal_pause"}:
                self.state_store.append_wardrobe_action(
                    {
                        "date": package.date.isoformat(),
                        "action_type": "reactivate",
                        "target_item_id": item_id,
                        "reason": "selected_in_outfit",
                        "status": "done",
                        "context_day_type": package.day_type,
                        "context_season": package.life_state.season if package.life_state else "all",
                        "context_city": package.city,
                        "notes": "Automatically reactivated due to real usage",
                    }
                )
                row["status"] = "active"

        category_counts: Dict[str, int] = {}
        for row in by_id.values():
            category = str(row.get("category") or "").strip()
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

            wear_count = self._to_int(row.get("wear_count"))
            if wear_count >= 30 and str(row.get("status") or "") == "active":
                self.state_store.append_wardrobe_action(
                    {
                        "date": package.date.isoformat(),
                        "action_type": "replace",
                        "target_item_id": row.get("item_id"),
                        "reason": f"high_wear_count:{wear_count}",
                        "status": "suggested",
                        "context_day_type": package.day_type,
                        "context_season": package.life_state.season if package.life_state else "all",
                        "context_city": package.city,
                        "notes": "Consider replacing this heavily used item",
                    }
                )
                self.state_store.append_shopping_candidate(
                    {
                        "candidate_id": f"cand_{package.date.isoformat()}_{row.get('item_id')}",
                        "category": row.get("category", ""),
                        "subcategory": row.get("subcategory", ""),
                        "suggested_name": f"Replacement for {row.get('name') or row.get('item_id')}",
                        "reason": "item_replacement",
                        "priority": "high",
                        "season": row.get("season_tags", "all"),
                        "style_match": row.get("style_tags", "all"),
                        "status": "open",
                        "notes": "Auto-suggested by AssetEvolutionEngine",
                    }
                )
            elif wear_count >= 20 and str(row.get("status") or "") == "active":
                self.state_store.append_wardrobe_action(
                    {
                        "date": package.date.isoformat(),
                        "action_type": "cooldown",
                        "target_item_id": row.get("item_id"),
                        "reason": f"high_wear_count:{wear_count}",
                        "status": "suggested",
                        "context_day_type": package.day_type,
                        "context_season": package.life_state.season if package.life_state else "all",
                        "context_city": package.city,
                        "notes": "Reduce selection priority temporarily",
                    }
                )

        tops = category_counts.get("top", 0)
        bottoms = category_counts.get("bottom", 0)
        if tops >= bottoms + 3:
            self.state_store.append_shopping_candidate(
                {
                    "candidate_id": f"cand_{package.date.isoformat()}_balance_bottom",
                    "category": "bottom",
                    "subcategory": "",
                    "suggested_name": "Versatile bottom for wardrobe balance",
                    "reason": "wardrobe imbalance",
                    "priority": "high",
                    "season": package.life_state.season if package.life_state else "all",
                    "style_match": package.day_type,
                    "gap_score": tops - bottoms,
                    "status": "open",
                    "notes": f"top={tops}, bottom={bottoms}",
                }
            )

        self.state_store.save_wardrobe_items(list(by_id.values()))

        repeat_score = 0
        if hasattr(self.state_store, "load_outfit_memory"):
            memory = self.state_store.load_outfit_memory() or []
            signature = ",".join(sorted(package.outfit.item_ids))
            repeat_score = sum(1 for row in memory[-14:] if str(row.get("item_ids", "")) == signature)

        self.state_store.append_outfit_memory(
            {
                "date": package.date.isoformat(),
                "outfit_id": f"outfit_{package.date.isoformat()}",
                "item_ids": ",".join(package.outfit.item_ids),
                "city": package.city,
                "day_type": package.day_type,
                "weather": weather_summary,
                "occasion": package.day_type,
                "used_in_content": True,
                "repeat_score": repeat_score,
                "notes": package.outfit.summary,
            }
        )

    def _update_scene_memory(self, package: Any) -> None:
        if not hasattr(self.state_store, "load_scene_memory"):
            return

        rows = self.state_store.load_scene_memory() or []
        mem: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            sid = str(row.get("scene_id") or "").strip()
            if sid:
                mem[sid] = row

        for scene in package.scenes:
            scene_id = f"{package.day_type}:{scene.block}:{scene.location}"
            row = mem.get(scene_id, {"scene_id": scene_id, "usage_count": 0, "status": "active", "notes": ""})
            usage = self._to_int(row.get("usage_count")) + 1
            row.update(
                {
                    "last_used": package.date.isoformat(),
                    "usage_count": usage,
                    "last_city": package.city,
                    "last_day_type": package.day_type,
                    "repeat_cooldown": 2 if usage < 6 else 4,
                    "status": "overused" if usage >= 10 else "active",
                }
            )
            mem[scene_id] = row

        self.state_store.save_scene_memory(list(mem.values()))

    def _update_activity_memory(self, package: Any) -> None:
        if not hasattr(self.state_store, "load_activity_memory"):
            return

        rows = self.state_store.load_activity_memory() or []
        mem: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            aid = str(row.get("activity_id") or "").strip()
            if aid:
                mem[aid] = row

        for scene in package.scenes:
            activity_type = f"{package.day_type}:{scene.mood}"
            activity_id = activity_type
            row = mem.get(activity_id, {"activity_id": activity_id, "usage_count": 0, "status": "active", "notes": ""})
            usage = self._to_int(row.get("usage_count")) + 1
            row.update(
                {
                    "activity_type": activity_type,
                    "last_used": package.date.isoformat(),
                    "usage_count": usage,
                    "context_tags": f"{scene.block},{scene.location}",
                    "status": "active",
                }
            )
            mem[activity_id] = row

        self.state_store.save_activity_memory(list(mem.values()))

    def _update_location_memory(self, package: Any, season: str) -> None:
        if not hasattr(self.state_store, "load_location_memory"):
            return

        rows = self.state_store.load_location_memory() or []
        mem: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            lid = str(row.get("location_id") or "").strip()
            if lid:
                mem[lid] = row

        for scene in package.scenes:
            location_type = str(scene.location).strip().lower().replace(" ", "_")
            location_id = f"{package.city}:{location_type}"
            row = mem.get(location_id, {"location_id": location_id, "usage_count": 0, "status": "active", "notes": ""})
            usage = self._to_int(row.get("usage_count")) + 1
            row.update(
                {
                    "city": package.city,
                    "location_type": location_type,
                    "name": scene.location,
                    "usage_count": usage,
                    "visit_frequency": usage,
                    "last_used": package.date.isoformat(),
                    "last_scene": scene.description,
                    "cooldown_days": 2 if usage < 6 else 4,
                    "season_tags": season,
                    "status": "active",
                }
            )
            mem[location_id] = row

        self.state_store.save_location_memory(list(mem.values()))

    def run(self, package: Any) -> None:
        weather_summary = f"{package.weather.condition}, {package.weather.temp_c}C"
        self._update_wardrobe_memory(package, weather_summary)
        season = package.life_state.season if package.life_state else "all"
        self._update_scene_memory(package)
        self._update_activity_memory(package)
        self._update_location_memory(package, season)
