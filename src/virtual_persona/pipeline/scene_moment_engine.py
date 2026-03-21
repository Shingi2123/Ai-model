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
        phase = str(getattr(context.get("narrative_context"), "narrative_phase", "") or "")
        energy = str(getattr(context.get("narrative_context"), "energy_state", "") or "")
        location = str(scene.location or "").lower()
        behavior = context.get("behavioral_context")
        selected_habit = str(getattr(behavior, "selected_habit", "") or "")
        place_anchor = str(getattr(behavior, "familiar_place_anchor", "") or "")
        recurring_objects = list(getattr(behavior, "recurring_objects", []) or [])
        habit_family = str(getattr(behavior, "habit_family", "") or "")
        action_family = str(getattr(behavior, "action_family", "") or "")
        emotional_arc = str(getattr(behavior, "emotional_arc", "") or "")
        social_mode = str(getattr(getattr(behavior, "daily_state", None), "social_presence_mode", "") or "")
        place_label = str(getattr(behavior, "familiar_place_label", "") or place_anchor)

        airport_pool = [
            {"type": "coffee_window_moment", "moment": "Quiet coffee by the terminal window before boarding", "focus": "coffee cup in hand, runway view through glass"},
            {"type": "terminal_walk_moment", "moment": "Slow walk through a nearly empty terminal with carry-on", "focus": "airport glass reflections and carry-on silhouette"},
            {"type": "gate_waiting_moment", "moment": "Calm waiting at the gate while watching aircraft pushback", "focus": "boarding pass and distant aircraft at gate"},
        ]
        hotel_pool = [
            {"type": "packing_moment", "moment": "Packing essentials near the hotel bed before checkout", "focus": "open suitcase near bed and folded outfit"},
            {"type": "window_pause_moment", "moment": "Quiet pause by the hotel window before leaving", "focus": "city view through hotel window and soft morning light"},
            {"type": "checkout_moment", "moment": "Final room check with luggage ready by the door", "focus": "suitcase handle, keycard, and doorway framing"},
        ]
        home_pool = [
            {"type": "home_coffee_moment", "moment": "Slow first coffee in a quiet kitchen corner", "focus": "warm mug, morning table light, simple home details"},
            {"type": "reading_moment", "moment": "Short reading pause on the sofa before heading out", "focus": "open book, blanket texture, soft daylight"},
            {"type": "self_care_moment", "moment": "Gentle self-care reset and tidy-up before evening", "focus": "mirror corner, skincare items, calm interior"},
        ]
        city_pool = [
            {"type": "cafe_table_moment", "moment": "A quiet table moment in a local cafe between errands", "focus": "notebook, espresso, and street reflections"},
            {"type": "street_walk_moment", "moment": "Unhurried walk along a side street during golden light", "focus": "crossbody bag movement and cobblestone texture"},
            {"type": "grocery_moment", "moment": "Small grocery stop for essentials on the way back", "focus": "paper bag, fresh produce, everyday city details"},
        ]

        if "airport" in location or "terminal" in location or "aircraft" in location or day_type in {"work_day", "travel_day"}:
            pool = airport_pool + hotel_pool
        elif "hotel" in location or day_type == "layover_day":
            pool = hotel_pool + city_pool
        elif "home" in location or day_type == "day_off":
            pool = home_pool + city_pool
        else:
            pool = city_pool + home_pool

        if phase in {"recovery_phase", "quiet_reset_phase"} or energy == "low":
            pool = [p for p in pool if "walk" not in p["type"]]
        if phase == "exploration_phase":
            pool = city_pool + airport_pool + hotel_pool
        if selected_habit == "terminal_pause" and airport_pool:
            pool = airport_pool + pool
        if selected_habit == "window_pause" and hotel_pool:
            pool = sorted(pool, key=lambda row: 0 if "window" in row["type"] else 1)
        if habit_family == "departure_ritual":
            pool.insert(
                0,
                {
                    "type": "departure_ritual_moment",
                    "moment": "A quiet before-leaving check with everything already in place",
                    "focus": "bag strap, folded layer, and a paused breath before moving",
                },
            )
        if action_family == "gentle_movement":
            pool.append(
                {
                    "type": "route_familiarity_moment",
                    "moment": "An easy route chosen almost by habit through a familiar stretch",
                    "focus": "small movement details and a familiar corner coming into view",
                }
            )
        if place_anchor and not any(place_anchor in p["moment"].lower() for p in pool):
            pool.insert(
                0,
                {
                    "type": f"{selected_habit or 'behavior'}_moment",
                    "moment": f"Quiet everyday pause near the {place_label}",
                    "focus": ", ".join(recurring_objects[:2]) or "familiar corner details",
                },
            )
        if social_mode == "quiet_crowd_around":
            pool.append(
                {
                    "type": "public_pause_moment",
                    "moment": "A quiet pause while the world moves softly in the background",
                    "focus": "subtle crowd blur behind a calm foreground gesture",
                }
            )
        if social_mode == "colleague_implied_world":
            pool.append(
                {
                    "type": "colleague_world_moment",
                    "moment": "A composed in-between moment with work life implied just outside the frame",
                    "focus": "structured posture, neat outfit, and nearby movement not centered in frame",
                }
            )
        if emotional_arc == "subtle_pre_departure_melancholy":
            pool = sorted(pool, key=lambda row: 0 if any(token in row["type"] for token in ["departure", "window", "checkout"]) else 1)
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
            pool = sorted(pool, key=lambda row: 0 if "walk" in row["type"] or "checkout" in row["type"] else 1)
        if "habit_recently_used" in anti_repeat:
            pool = [row for row in pool if not row["type"].startswith(str(getattr(behavior, "selected_habit", "")))] or pool
        if "place_recently_used" in anti_repeat:
            familiar = str(getattr(behavior, "familiar_place_anchor", "") or "")
            pool = [row for row in pool if familiar.lower() not in row["moment"].lower()] or pool
        if "habit_family_streak" in anti_repeat:
            family = str(getattr(behavior, "habit_family", "") or "")
            pool = [row for row in pool if family not in row["type"]] or pool
        if "caption_voice_streak" in anti_repeat:
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
