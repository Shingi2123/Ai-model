from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Dict, Iterable, List, Sequence

from virtual_persona.models.domain import BehaviorState


logger = logging.getLogger(__name__)


ENERGY_ORDER = ("low", "medium", "high")
SOCIAL_ORDER = ("alone", "light_public", "social")
EMOTIONAL_ARCS = ("arrival", "routine", "reflection", "transition", "departure")
HABITS = ("window_pause", "coffee_moment", "packing", "slow_walk", "none")
PLACE_ANCHORS = ("hotel_window", "kitchen_corner", "terminal_gate", "cafe_corner")
SELF_PRESENTATIONS = ("relaxed", "composed", "focused", "soft", "transitional")


def _split_csv(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _load_memory_rows(memory: Any) -> List[Dict[str, Any]]:
    if memory is None:
        return []
    if isinstance(memory, list):
        rows = [dict(row) for row in memory if isinstance(row, dict)]
        return [_normalize_memory_row(row) for row in rows]
    if hasattr(memory, "load_behavior_memory"):
        try:
            rows = memory.load_behavior_memory() or []
            return [_normalize_memory_row(dict(row)) for row in rows if isinstance(row, dict)]
        except Exception:
            return []
    return []


def _normalize_memory_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    if not normalized.get("habit"):
        normalized["habit"] = normalized.get("selected_habit", "")
    if not normalized.get("place_anchor"):
        normalized["place_anchor"] = normalized.get("familiar_place_anchor", "")
    if not normalized.get("objects"):
        normalized["objects"] = normalized.get("recurring_objects_in_scene", "")
    if not normalized.get("self_presentation"):
        normalized["self_presentation"] = normalized.get("self_presentation_mode", "")
    if not normalized.get("social_mode"):
        normalized["social_mode"] = normalized.get("social_presence_mode", "")
    return normalized


def _sort_memory(memory: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(memory, key=lambda row: str(row.get("date") or ""))


def _recent_streak(memory: Sequence[Dict[str, Any]], field: str) -> int:
    if not memory:
        return 0
    ordered = _sort_memory(memory)
    last_value = str(ordered[-1].get(field) or "").strip()
    if not last_value:
        return 0
    streak = 0
    for row in reversed(ordered):
        if str(row.get(field) or "").strip() != last_value:
            break
        streak += 1
    return streak


def _force_variation(
    candidates: Iterable[str],
    memory: Sequence[Dict[str, Any]],
    field: str,
) -> tuple[str, bool]:
    candidate_list = [str(candidate).strip() for candidate in candidates if str(candidate).strip()]
    if not candidate_list:
        return "", False
    ordered = _sort_memory(memory)
    last_value = str(ordered[-1].get(field) or "").strip() if ordered else ""
    streak = _recent_streak(memory, field)
    if streak < 2 or not last_value:
        return candidate_list[0], False
    for candidate in candidate_list:
        if candidate != last_value:
            return candidate, True
    return candidate_list[0], False


def _derive_energy(context: Dict[str, Any]) -> str:
    narrative = context.get("narrative_context")
    explicit = str(getattr(narrative, "energy_state", "") or "").strip().lower()
    if explicit in ENERGY_ORDER:
        return explicit
    fatigue = int(getattr(context.get("life_state"), "fatigue_level", 4) or 4)
    if fatigue >= 7:
        return "low"
    if fatigue <= 2:
        return "high"
    return "medium"


def _derive_social_mode(context: Dict[str, Any], energy_level: str) -> str:
    day_type = str(context.get("day_type") or "").strip().lower()
    if day_type in {"day_off", "hotel_rest"}:
        return "alone"
    if day_type in {"work_day", "travel_day", "airport_transfer"}:
        return "light_public"
    if energy_level == "high":
        return "social"
    return "light_public"


def _derive_emotional_arc(context: Dict[str, Any], energy_level: str) -> str:
    day_type = str(context.get("day_type") or "").strip().lower()
    phase = str(getattr(context.get("narrative_context"), "narrative_phase", "") or "").strip().lower()
    continuity = context.get("continuity_context") or {}
    arc_hint = str(continuity.get("arc_hint") or "").strip().lower()

    if day_type in {"travel_day", "airport_transfer"}:
        return "transition" if energy_level != "high" else "departure"
    if "arrival" in arc_hint:
        return "arrival"
    if phase in {"recovery_phase", "quiet_reset_phase"}:
        return "reflection"
    if phase == "transition_phase":
        return "transition"
    return "routine"


def _habit_candidates(context: Dict[str, Any], energy_level: str, emotional_arc: str) -> List[str]:
    day_type = str(context.get("day_type") or "").strip().lower()
    candidates: List[str] = []
    if emotional_arc in {"transition", "departure"}:
        candidates.extend(["packing", "coffee_moment"])
    if energy_level == "low":
        candidates.extend(["window_pause", "coffee_moment", "none"])
    elif energy_level == "high":
        candidates.extend(["slow_walk", "coffee_moment"])
    else:
        candidates.extend(["coffee_moment", "window_pause", "none"])
    if day_type in {"work_day", "travel_day", "airport_transfer"}:
        candidates.append("packing")
    if day_type in {"day_off", "layover_day"}:
        candidates.append("slow_walk")
    return list(dict.fromkeys(candidates))


def _place_candidates(day_type: str, habit: str, emotional_arc: str, energy_level: str) -> List[str]:
    candidates: List[str] = []
    if habit == "window_pause":
        candidates.extend(["hotel_window", "kitchen_corner"])
    elif habit == "packing":
        candidates.extend(["hotel_window", "terminal_gate"])
    elif habit == "slow_walk":
        candidates.extend(["cafe_corner", "terminal_gate"])
    elif habit == "coffee_moment":
        candidates.extend(["kitchen_corner", "cafe_corner", "terminal_gate"])
    else:
        candidates.extend(["kitchen_corner", "hotel_window", "cafe_corner"])

    if day_type in {"travel_day", "airport_transfer", "work_day"}:
        candidates.insert(0, "terminal_gate")
    if emotional_arc == "arrival":
        candidates.insert(0, "hotel_window")
    if energy_level == "low":
        candidates.insert(0, "kitchen_corner")
        candidates.insert(1, "hotel_window")
    return list(dict.fromkeys(candidates))


def _build_objects(place_anchor: str, habit: str, day_type: str) -> List[str]:
    if place_anchor == "terminal_gate":
        objects = ["carry_on", "bag"]
        if habit == "coffee_moment":
            objects.insert(0, "coffee_cup")
        return objects
    if place_anchor == "kitchen_corner":
        return ["coffee_cup", "bag"] if habit == "coffee_moment" else ["coffee_cup"]
    if place_anchor == "hotel_window":
        return ["bag", "clothes"] if habit == "packing" or day_type in {"travel_day", "airport_transfer"} else ["bag"]
    return ["coffee_cup", "bag"] if habit == "coffee_moment" else ["bag"]


def _self_presentation(day_type: str, emotional_arc: str, energy_level: str, social_mode: str) -> str:
    if emotional_arc == "transition":
        return "transitional"
    if day_type == "work_day":
        return "focused"
    if social_mode == "social":
        return "composed"
    if emotional_arc == "reflection":
        return "soft"
    if energy_level == "low":
        return "relaxed"
    return "composed"


def build_behavior(context: Dict[str, Any], memory: Any) -> BehaviorState:
    memory_rows = _sort_memory(_load_memory_rows(memory))
    variation_flags: List[str] = []

    energy_level = _derive_energy(context)
    social_mode = _derive_social_mode(context, energy_level)

    emotional_arc, arc_varied = _force_variation(
        [_derive_emotional_arc(context, energy_level)] + [arc for arc in EMOTIONAL_ARCS if arc != _derive_emotional_arc(context, energy_level)],
        memory_rows,
        "emotional_arc",
    )
    if arc_varied:
        variation_flags.append("emotional_arc_varied")

    habit, habit_varied = _force_variation(
        _habit_candidates(context, energy_level, emotional_arc),
        memory_rows,
        "habit",
    )
    if habit_varied:
        variation_flags.append("habit_varied")

    day_type = str(context.get("day_type") or "").strip().lower()
    place_anchor, place_varied = _force_variation(
        _place_candidates(day_type, habit, emotional_arc, energy_level),
        memory_rows,
        "place_anchor",
    )
    if place_varied:
        variation_flags.append("place_varied")

    objects = _build_objects(place_anchor, habit, day_type)
    self_presentation = _self_presentation(day_type, emotional_arc, energy_level, social_mode)

    behavior = BehaviorState(
        energy_level=energy_level,
        social_mode=social_mode,
        emotional_arc=emotional_arc,
        habit=habit,
        place_anchor=place_anchor,
        objects=objects,
        self_presentation=self_presentation,
    )

    source = "variation" if variation_flags else "memory" if memory_rows else "new"
    behavior._source = source
    behavior._anti_repetition_flags = variation_flags
    return behavior


class BehaviorEngine:
    def __init__(self, state_store: Any = None) -> None:
        self.state_store = state_store

    def build(self, context: Dict[str, Any]) -> BehaviorState:
        memory = _load_memory_rows(self.state_store)
        behavior = build_behavior(context, memory)
        logger.info("[BEHAVIOR] generated: %s", behavior.debug_summary)
        logger.info("[BEHAVIOR] source: %s", behavior.source)
        return behavior

    def to_memory_row(self, target_date: date, city: str, day_type: str, behavior: BehaviorState) -> Dict[str, Any]:
        payload = {
            "date": target_date.isoformat(),
            "city": city,
            "day_type": day_type,
            "behavior_state": json.dumps(
                {
                    "energy_level": behavior.energy_level,
                    "social_mode": behavior.social_mode,
                    "emotional_arc": behavior.emotional_arc,
                    "habit": behavior.habit,
                    "place_anchor": behavior.place_anchor,
                    "objects": behavior.objects,
                    "self_presentation": behavior.self_presentation,
                },
                ensure_ascii=False,
            ),
            "energy_level": behavior.energy_level,
            "social_mode": behavior.social_mode,
            "emotional_arc": behavior.emotional_arc,
            "habit": behavior.habit,
            "place_anchor": behavior.place_anchor,
            "objects": ", ".join(behavior.objects),
            "self_presentation": behavior.self_presentation,
            "source": behavior.source,
            "day_behavior_summary": behavior.debug_summary,
        }
        payload["selected_habit"] = behavior.habit
        payload["familiar_place_anchor"] = behavior.place_anchor
        payload["recurring_objects_in_scene"] = payload["objects"]
        payload["self_presentation_mode"] = behavior.self_presentation
        payload["social_presence_mode"] = behavior.social_mode
        return payload

    def habit_memory_row(self, target_date: date, city: str, day_type: str, behavior: BehaviorState) -> Dict[str, Any]:
        return {
            "date": target_date.isoformat(),
            "city": city,
            "day_type": day_type,
            "habit": behavior.habit,
            "emotional_arc": behavior.emotional_arc,
            "place_anchor": behavior.place_anchor,
        }

    def place_memory_row(self, target_date: date, city: str, day_type: str, behavior: BehaviorState) -> Dict[str, Any]:
        return {
            "date": target_date.isoformat(),
            "city": city,
            "day_type": day_type,
            "place_anchor": behavior.place_anchor,
            "emotional_arc": behavior.emotional_arc,
            "habit": behavior.habit,
        }

    def object_usage_row(self, target_date: date, city: str, day_type: str, behavior: BehaviorState) -> Dict[str, Any]:
        return {
            "date": target_date.isoformat(),
            "city": city,
            "day_type": day_type,
            "place_anchor": behavior.place_anchor,
            "objects": ", ".join(behavior.objects),
            "habit": behavior.habit,
        }
