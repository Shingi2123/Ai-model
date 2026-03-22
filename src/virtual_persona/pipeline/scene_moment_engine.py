from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import date
from typing import Any, Dict, List, Sequence

from virtual_persona.models.domain import DayScene


@dataclass
class MomentVariationController:
    cooldown_days: int = 3

    @staticmethod
    def _normalize(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9|\s]+", " ", (value or "").lower())
        return " ".join(cleaned.split())

    def _within_cooldown(self, used_on: str, target_date: date) -> bool:
        try:
            used_date = date.fromisoformat(str(used_on)[:10])
        except Exception:
            return False
        return (target_date - used_date).days < self.cooldown_days

    def blocked_signatures(self, memory_rows: Sequence[Dict[str, Any]], target_date: date) -> set[str]:
        blocked: set[str] = set()
        for row in memory_rows:
            sig = self._normalize(str(row.get("moment_signature") or ""))
            if not sig:
                continue
            used_on = str(row.get("date") or row.get("last_used") or "")
            if self._within_cooldown(used_on, target_date):
                blocked.add(sig)
        return blocked


class SceneMomentGenerator:
    ARCHETYPE_BY_TYPE = {
        "coffee_window_moment": "recovery",
        "terminal_walk_moment": "transit",
        "gate_waiting_moment": "transit",
        "packing_moment": "preparation",
        "departure_ritual_moment": "preparation",
        "window_pause_moment": "hotel_private",
        "checkout_moment": "transit",
        "home_coffee_moment": "recovery",
        "reading_moment": "recovery",
        "self_care_moment": "hotel_private",
        "cafe_table_moment": "meal",
        "street_walk_moment": "ambient_street",
        "grocery_moment": "city_observation",
        "route_familiarity_moment": "city_observation",
        "colleague_world_moment": "workday",
        "public_pause_moment": "quiet_public",
        "arrival_room_moment": "hotel_private",
        "routine_counter_moment": "recovery",
        "light_public_moment": "quiet_public",
    }

    def __init__(self, state_store: Any = None) -> None:
        self.state_store = state_store
        self.variation = MomentVariationController()

    @staticmethod
    def _scene_source(scene: DayScene) -> str:
        return str(getattr(scene, "source", "library") or "library")

    @staticmethod
    def _signature_text(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", (value or "").lower())
        compact = " ".join(cleaned.split())
        stop = {"a", "the", "and", "with", "by", "of", "to", "in", "on", "near", "before", "after"}
        return " ".join([t for t in compact.split() if t not in stop])

    @classmethod
    def normalize_signature(cls, signature: str) -> str:
        if not signature:
            return ""
        parts = [cls._signature_text(p) for p in str(signature).split("|")]
        return "|".join(part for part in parts if part)

    @classmethod
    def _build_signature(cls, day_type: str, scene: DayScene, moment_type: str, moment_text: str) -> str:
        location = cls._signature_text(str(getattr(scene, "location", "") or ""))
        time_of_day = cls._signature_text(str(getattr(scene, "time_of_day", "") or ""))
        canonical_type = cls._signature_text(moment_type.replace("_moment", ""))
        canonical_moment = cls._signature_text(moment_text)
        raw = "|".join([day_type.strip().lower(), location, time_of_day, canonical_type, canonical_moment])
        return cls.normalize_signature(raw)

    def _load_recent_moments(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        rows.extend(context.get("recent_moment_memory") or [])
        history = context.get("recent_history") or []
        for row in history:
            sig = str(row.get("moment_signature") or "").strip()
            if not sig:
                continue
            rows.append({"date": row.get("date"), "moment_signature": sig})
        return rows

    def _candidate_pool(self, context: Dict[str, Any], scene: DayScene) -> List[Dict[str, str]]:
        day_type = str(context.get("day_type") or "")
        behavior = context.get("behavioral_context")
        selected_habit = str(getattr(behavior, "habit", "") or "")
        place_anchor = str(getattr(behavior, "place_anchor", "") or "")
        recurring_objects = list(getattr(behavior, "objects", []) or [])
        action_family = str(getattr(behavior, "action_family", "") or "")
        emotional_arc = str(getattr(behavior, "emotional_arc", "") or "")
        social_mode = str(getattr(behavior, "social_mode", "alone") or "alone")

        pools = {
            "terminal_gate": [
                {"type": "gate_waiting_moment", "moment": "Calm waiting at the terminal gate before boarding", "focus": "carry_on, bag, gate seating"},
                {"type": "terminal_walk_moment", "moment": "Slow walk through the terminal with luggage in hand", "focus": "carry_on, bag, airport reflections"},
                {"type": "coffee_window_moment", "moment": "Coffee at the gate while watching the runway", "focus": "coffee_cup, carry_on, runway view"},
            ],
            "hotel_window": [
                {"type": "window_pause_moment", "moment": "Quiet pause by the hotel window before leaving", "focus": "bag, city view, window frame"},
                {"type": "packing_moment", "moment": "Packing essentials in a hotel room with everything laid out neatly", "focus": "bag, clothes, suitcase"},
                {"type": "arrival_room_moment", "moment": "A first quiet look around the room after arriving", "focus": "bag, clothes, new room details"},
            ],
            "kitchen_corner": [
                {"type": "home_coffee_moment", "moment": "Slow first coffee in the kitchen corner before the day starts", "focus": "coffee_cup, counter light, bag"},
                {"type": "window_pause_moment", "moment": "A still pause in the kitchen while morning light settles in", "focus": "coffee_cup, window light"},
                {"type": "routine_counter_moment", "moment": "A small routine moment with everything kept simple and close", "focus": "coffee_cup, bag"},
            ],
            "cafe_corner": [
                {"type": "cafe_table_moment", "moment": "A quiet coffee pause at a familiar cafe corner", "focus": "coffee_cup, bag, table edge"},
                {"type": "street_walk_moment", "moment": "An unhurried walk after leaving the cafe", "focus": "bag movement, street light"},
                {"type": "public_pause_moment", "moment": "A still moment in public while life moves softly nearby", "focus": "coffee_cup, soft crowd blur"},
            ],
        }

        pool = list(pools.get(place_anchor, pools["kitchen_corner"]))
        if selected_habit == "coffee_moment":
            pool = sorted(pool, key=lambda row: 0 if "coffee" in row["type"] or "coffee" in row["moment"].lower() else 1)
        elif selected_habit == "packing":
            pool = sorted(pool, key=lambda row: 0 if "packing" in row["type"] or "arrival" in row["type"] else 1)
        elif selected_habit == "slow_walk":
            pool = sorted(pool, key=lambda row: 0 if "walk" in row["type"] else 1)
        elif selected_habit == "window_pause":
            pool = sorted(pool, key=lambda row: 0 if "window" in row["type"] else 1)

        if emotional_arc == "arrival":
            pool = sorted(pool, key=lambda row: 0 if "arrival" in row["type"] or "first" in row["moment"].lower() else 1)
        elif emotional_arc in {"transition", "departure"}:
            pool = sorted(pool, key=lambda row: 0 if any(token in row["type"] for token in ["packing", "gate", "walk"]) else 1)
        elif emotional_arc == "reflection":
            pool = [row for row in pool if "walk" not in row["type"]] or pool

        if social_mode == "alone":
            pool = [row for row in pool if "crowd" not in row["focus"]] or pool
        elif social_mode == "light_public":
            pool.append(
                {
                    "type": "light_public_moment",
                    "moment": "A personal pause with soft background people nearby",
                    "focus": ", ".join(recurring_objects[:2]) or "soft background people",
                }
            )

        if action_family == "walking":
            pool.append(
                {
                    "type": "route_familiarity_moment",
                    "moment": "An easy familiar route taken without rushing",
                    "focus": ", ".join(recurring_objects[:2]) or "bag movement",
                }
            )
        return pool

    def _pick_candidate(
        self,
        context: Dict[str, Any],
        scene: DayScene,
        blocked_signatures: set[str],
        used_archetypes: set[str],
        used_signatures: set[str],
    ) -> Dict[str, str]:
        day_type = str(context.get("day_type") or "")
        continuity = context.get("continuity_context") or {}
        arc_hint = str(continuity.get("arc_hint") or "")
        behavior = context.get("behavioral_context")
        anti_repeat = set(getattr(behavior, "anti_repetition_flags", []) or [])
        pool = self._candidate_pool(context, scene)
        if arc_hint == "arrival_and_adaptation":
            pool = sorted(pool, key=lambda row: 0 if "arrival" in row["type"] or "walk" in row["type"] else 1)
        if "habit_varied" in anti_repeat:
            chosen_habit = str(getattr(behavior, "habit", "") or "")
            pool = [row for row in pool if chosen_habit.split("_")[0] not in row["type"]] or pool
        if "place_varied" in anti_repeat:
            familiar = str(getattr(behavior, "place_anchor", "") or "")
            pool = [row for row in pool if familiar.lower() not in row["moment"].lower()] or pool
        if "emotional_arc_varied" in anti_repeat:
            pool = [row for row in pool if "quiet" not in row["type"]] or pool
        for candidate in pool:
            sig = self._build_signature(day_type, scene, candidate["type"], candidate["moment"])
            archetype = self.ARCHETYPE_BY_TYPE.get(candidate["type"], "daily")
            if sig in used_signatures:
                continue
            if sig in blocked_signatures:
                continue
            if archetype in used_archetypes and len(pool) > 1:
                continue
            return {**candidate, "signature": sig, "archetype": archetype}
        fallback = pool[0]
        return {
            **fallback,
            "signature": self._build_signature(day_type, scene, fallback["type"], fallback["moment"]),
            "archetype": self.ARCHETYPE_BY_TYPE.get(fallback["type"], "daily"),
        }

    def generate_for_scene(self, context: Dict[str, Any], scene: DayScene) -> DayScene:
        target_date = context.get("date")
        if not isinstance(target_date, date):
            target_date = date.today()

        memory_rows = self._load_recent_moments(context)
        blocked = self.variation.blocked_signatures(memory_rows, target_date)
        picked = self._pick_candidate(context, scene, blocked, set(), set())

        scene.scene_moment = picked["moment"]
        scene.scene_moment_type = picked["type"]
        scene.scene_source = self._scene_source(scene)
        scene.moment_signature = picked["signature"]
        scene.moment_reason = (
            f"Selected from {scene.scene_source} day scene with narrative-aware deduplication"
        )
        scene.visual_focus = picked["focus"]
        scene.scene_moment_type = picked["archetype"]
        return scene

    def generate(self, context: Dict[str, Any], scenes: Sequence[DayScene]) -> List[DayScene]:
        generated: List[DayScene] = []
        seen: set[str] = set()
        used_archetypes: set[str] = set()
        target_date = context.get("date")
        if not isinstance(target_date, date):
            target_date = date.today()
        blocked = self.variation.blocked_signatures(self._load_recent_moments(context), target_date)
        for scene in scenes:
            picked = self._pick_candidate(context, scene, blocked, used_archetypes, seen)
            scene.scene_moment = picked["moment"]
            scene.scene_moment_type = picked["archetype"]
            scene.scene_source = self._scene_source(scene)
            scene.moment_signature = picked["signature"]
            scene.moment_reason = f"Selected with archetype diversity and continuity weighting ({picked['archetype']})"
            scene.visual_focus = picked["focus"]
            scene.scene_family = getattr(scene, "scene_family", "") or picked["archetype"]
            scene.action_family = getattr(scene, "action_family", "") or str(getattr(context.get("behavioral_context"), "action_family", "") or "daily_life")
            scene.location_family = getattr(scene, "location_family", "") or ("private" if any(token in (scene.location or "").lower() for token in ["home", "room", "hotel"]) else "public")
            enriched = scene
            if enriched.moment_signature in seen:
                continue
            seen.add(enriched.moment_signature)
            used_archetypes.add(str(getattr(enriched, "scene_moment_type", "daily")))
            generated.append(enriched)
        return generated
