from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Sequence

from virtual_persona.models.domain import DayScene


@dataclass
class MomentVariationController:
    cooldown_days: int = 3

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join((value or "").strip().lower().split())

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
    def __init__(self, state_store: Any = None) -> None:
        self.state_store = state_store
        self.variation = MomentVariationController()

    @staticmethod
    def _scene_source(scene: DayScene) -> str:
        return str(getattr(scene, "source", "library") or "library")

    @staticmethod
    def _build_signature(day_type: str, scene: DayScene, moment_type: str, visual_focus: str) -> str:
        location = str(getattr(scene, "location", "") or "")
        time_of_day = str(getattr(scene, "time_of_day", "") or "")
        return "|".join(
            [
                day_type.strip().lower(),
                location.strip().lower(),
                time_of_day.strip().lower(),
                moment_type.strip().lower(),
                visual_focus.strip().lower(),
            ]
        )

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
        return pool

    def _pick_candidate(
        self,
        context: Dict[str, Any],
        scene: DayScene,
        blocked_signatures: set[str],
    ) -> Dict[str, str]:
        day_type = str(context.get("day_type") or "")
        for candidate in self._candidate_pool(context, scene):
            sig = self._build_signature(day_type, scene, candidate["type"], candidate["focus"])
            if sig not in blocked_signatures:
                return {**candidate, "signature": sig}
        fallback = self._candidate_pool(context, scene)[0]
        return {
            **fallback,
            "signature": self._build_signature(day_type, scene, fallback["type"], fallback["focus"]),
        }

    def generate_for_scene(self, context: Dict[str, Any], scene: DayScene) -> DayScene:
        target_date = context.get("date")
        if not isinstance(target_date, date):
            target_date = date.today()

        memory_rows = self._load_recent_moments(context)
        blocked = self.variation.blocked_signatures(memory_rows, target_date)
        picked = self._pick_candidate(context, scene, blocked)

        scene.scene_moment = picked["moment"]
        scene.scene_moment_type = picked["type"]
        scene.scene_source = self._scene_source(scene)
        scene.moment_signature = picked["signature"]
        scene.moment_reason = (
            f"Selected from {scene.scene_source} day scene with narrative-aware deduplication"
        )
        scene.visual_focus = picked["focus"]
        return scene

    def generate(self, context: Dict[str, Any], scenes: Sequence[DayScene]) -> List[DayScene]:
        generated: List[DayScene] = []
        seen: set[str] = set()
        for scene in scenes:
            enriched = self.generate_for_scene(context, scene)
            if enriched.moment_signature in seen:
                continue
            seen.add(enriched.moment_signature)
            generated.append(enriched)
        return generated
