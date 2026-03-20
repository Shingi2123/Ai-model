from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List

from virtual_persona.models.domain import (
    BehavioralContext,
    CharacterBehaviorProfile,
    DailyBehaviorState,
    SlowBehaviorState,
)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, round(value, 3)))


class BehavioralLogicEngine:
    DEFAULT_HABITS = {
        "window_pause": {
            "contexts": {"hotel_rest", "day_off", "layover_day", "travel_day", "work_day"},
            "min_gap_days": 2,
            "place": "quiet hotel window",
            "objects": ["mug", "phone"],
            "actions": ["pause_by_window", "steady_breath", "small_hair_adjustment"],
        },
        "coffee_before_leaving": {
            "contexts": {"travel_day", "work_day", "day_off", "layover_day"},
            "min_gap_days": 1,
            "place": "soft morning desk",
            "objects": ["mug", "bag"],
            "actions": ["coffee_pause", "bag_check", "quiet_start"],
        },
        "terminal_pause": {
            "contexts": {"travel_day", "airport_transfer", "work_day"},
            "min_gap_days": 2,
            "place": "airport side corridor",
            "objects": ["carry_on", "shoulder_bag", "headphones"],
            "actions": ["terminal_pause", "look_to_window", "touch_bag_strap"],
        },
        "outfit_tidy": {
            "contexts": {"work_day", "travel_day", "airport_transfer"},
            "min_gap_days": 1,
            "place": "hallway mirror",
            "objects": ["jacket", "phone"],
            "actions": ["smooth_sleeve", "check_collar", "steady_posture"],
        },
        "quiet_before_leaving": {
            "contexts": {"travel_day", "hotel_rest", "layover_day"},
            "min_gap_days": 2,
            "place": "tidy room mirror",
            "objects": ["bag", "jacket", "suitcase"],
            "actions": ["last_room_scan", "touch_handle", "small_reset"],
        },
        "slow_walk": {
            "contexts": {"day_off", "layover_day", "hotel_rest"},
            "min_gap_days": 2,
            "place": "cafe corner near glass",
            "objects": ["shoulder_bag", "sunglasses"],
            "actions": ["slow_walk", "look_sideways", "quiet_notice"],
        },
    }

    DEFAULT_PLACE_ANCHORS = [
        "quiet hotel window",
        "airport side corridor",
        "cafe corner near glass",
        "tidy room mirror",
        "hallway mirror",
        "living space corner",
        "soft morning desk",
    ]

    DEFAULT_OBJECTS = {
        "travel_day": ["carry_on", "shoulder_bag", "jacket", "headphones", "phone"],
        "airport_transfer": ["carry_on", "shoulder_bag", "phone", "scarf"],
        "work_day": ["phone", "shoulder_bag", "jacket", "notebook"],
        "day_off": ["mug", "notebook", "phone"],
        "layover_day": ["shoulder_bag", "sunglasses", "phone", "mug"],
        "hotel_rest": ["mug", "bag", "jacket"],
    }

    EMOTIONAL_ARCS = {
        "travel_phase": "between_flights_introspection",
        "exploration_phase": "curious_city_openness",
        "recovery_phase": "low_energy_recovery",
        "quiet_reset_phase": "quiet_settling",
        "routine_stability": "routine_stability",
    }

    def __init__(self, state_store: Any) -> None:
        self.state_store = state_store

    def build(self, context: Dict[str, Any]) -> BehavioralContext:
        profile = self._build_profile(context.get("character_profile") or {})
        slow_state = self._build_slow_state(context, profile)
        daily_state = self._build_daily_state(context, profile, slow_state)
        emotional_arc = self._select_emotional_arc(context, daily_state)
        habit = self._select_habit(context, profile, daily_state)
        familiar_place_anchor = self._select_place_anchor(context, profile, daily_state, habit)
        recurring_objects = self._select_recurring_objects(context, profile, habit)
        transition_hint = self._build_transition_hint(context, daily_state, familiar_place_anchor, recurring_objects)
        outfit_behavior_mode = self._outfit_behavior_mode(context, daily_state)
        allowed_scene_families = self._scene_families(context, daily_state, emotional_arc)
        likely_actions = self._likely_actions(habit, daily_state)
        gesture_bias = self._gesture_bias(profile, daily_state)
        anti_repetition_flags = self._anti_repetition_flags(context, habit["name"], familiar_place_anchor, emotional_arc)

        debug_summary = (
            f"energy={daily_state.energy_level:.2f}; quiet={daily_state.desire_for_quiet:.2f}; "
            f"movement={daily_state.desire_for_movement:.2f}; arc={emotional_arc}; habit={habit['name']}; "
            f"place={familiar_place_anchor}; objects={','.join(recurring_objects[:3])}"
        )

        return BehavioralContext(
            profile=profile,
            slow_state=slow_state,
            daily_state=daily_state,
            emotional_arc=emotional_arc,
            selected_habit=habit["name"],
            habit_context=habit["context"],
            familiar_place_anchor=familiar_place_anchor,
            recurring_objects=recurring_objects,
            outfit_behavior_mode=outfit_behavior_mode,
            transition_hint=transition_hint,
            allowed_scene_families=allowed_scene_families,
            likely_actions=likely_actions,
            gesture_bias=gesture_bias,
            anti_repetition_flags=anti_repetition_flags,
            debug_summary=debug_summary,
        )

    def to_memory_row(self, target_date: date, city: str, day_type: str, behavior: BehavioralContext) -> Dict[str, Any]:
        daily = asdict(behavior.daily_state)
        slow = asdict(behavior.slow_state)
        return {
            "date": target_date.isoformat(),
            "city": city,
            "day_type": day_type,
            "emotional_arc": behavior.emotional_arc,
            "selected_habit": behavior.selected_habit,
            "habit_context": behavior.habit_context,
            "familiar_place_anchor": behavior.familiar_place_anchor,
            "recurring_objects_in_scene": ", ".join(behavior.recurring_objects),
            "self_presentation_mode": behavior.daily_state.self_presentation_mode,
            "social_presence_mode": behavior.daily_state.social_presence_mode,
            "transition_hint_used": behavior.transition_hint,
            "caption_voice_mode": behavior.daily_state.caption_voice_mode,
            "allowed_scene_families": ", ".join(behavior.allowed_scene_families),
            "likely_actions": ", ".join(behavior.likely_actions),
            "gesture_bias": ", ".join(behavior.gesture_bias),
            "anti_repetition_flags": ", ".join(behavior.anti_repetition_flags),
            "day_behavior_summary": behavior.debug_summary,
            "daily_behavior_state": daily,
            "slow_behavior_state": slow,
        }

    def _build_profile(self, profile: Dict[str, Any]) -> CharacterBehaviorProfile:
        habits = self._split_csv(profile.get("behavior_favorite_habits")) or ["window_pause", "coffee_before_leaving", "outfit_tidy"]
        place_archetypes = self._split_csv(profile.get("behavior_favorite_place_archetypes")) or list(self.DEFAULT_PLACE_ANCHORS[:4])
        recurring_objects = self._split_csv(profile.get("behavior_recurring_objects")) or ["shoulder_bag", "mug", "phone", "jacket"]
        return CharacterBehaviorProfile(
            baseline_temperament=str(profile.get("behavior_baseline_temperament") or "soft_observant"),
            social_openness=float(profile.get("behavior_social_openness") or 0.42),
            organization_level=float(profile.get("behavior_organization_level") or 0.74),
            comfort_with_haste=float(profile.get("behavior_comfort_with_haste") or 0.32),
            ritual_need=float(profile.get("behavior_ritual_need") or 0.78),
            solitude_preference=float(profile.get("behavior_solitude_preference") or 0.68),
            city_wandering_affinity=float(profile.get("behavior_city_wandering_affinity") or 0.58),
            coffee_affinity=float(profile.get("behavior_coffee_affinity") or 0.71),
            window_pause_affinity=float(profile.get("behavior_window_pause_affinity") or 0.8),
            morning_pause_affinity=float(profile.get("behavior_morning_pause_affinity") or 0.82),
            work_uniform_alignment=float(profile.get("behavior_work_uniform_alignment") or 0.76),
            orderliness_with_items=float(profile.get("behavior_orderliness_with_items") or 0.79),
            self_photography_affinity=float(profile.get("behavior_self_photography_affinity") or 0.41),
            environment_photography_affinity=float(profile.get("behavior_environment_photography_affinity") or 0.64),
            improvisation_tolerance=float(profile.get("behavior_improvisation_tolerance") or 0.43),
            aesthetic_attention=float(profile.get("behavior_aesthetic_attention") or 0.81),
            repeat_place_affinity=float(profile.get("behavior_repeat_place_affinity") or 0.75),
            prefers_quiet_mornings=self._as_bool(profile.get("prefers_quiet_mornings"), True),
            keeps_small_rituals=self._as_bool(profile.get("keeps_small_rituals"), True),
            often_pauses_by_window=self._as_bool(profile.get("often_pauses_by_window"), True),
            likes_light_travel_routine=self._as_bool(profile.get("likes_light_travel_routine"), True),
            not_overly_social_on_workdays=self._as_bool(profile.get("not_overly_social_on_workdays"), True),
            more_reflective_after_flights=self._as_bool(profile.get("more_reflective_after_flights"), True),
            keeps_outfit_neat_even_off_duty=self._as_bool(profile.get("keeps_outfit_neat_even_off_duty"), True),
            avoids_overly_party_scenes_without_reason=self._as_bool(profile.get("avoids_overly_party_scenes_without_reason"), True),
            uses_familiar_gestures_more_than_dramatic_posing=self._as_bool(profile.get("uses_familiar_gestures_more_than_dramatic_posing"), True),
            stable_caption_voice=str(profile.get("stable_caption_voice") or "quiet_observational"),
            favorite_habits=habits,
            favorite_place_archetypes=place_archetypes,
            recurring_objects=recurring_objects,
        )

    def _build_slow_state(self, context: Dict[str, Any], profile: CharacterBehaviorProfile) -> SlowBehaviorState:
        history = context.get("recent_history") or []
        behavior_memory = self._load_behavior_memory()
        last_behavior = behavior_memory[-1] if behavior_memory else {}
        city = str(context.get("city") or "")
        life_state = context.get("life_state")
        fatigue_level = float(getattr(life_state, "fatigue_level", 3) or 3)
        recent_city_days = [row for row in history[-5:] if str(row.get("city") or "") == city]
        city_changes = sum(1 for row in history[-5:] if str(row.get("city") or "") != city)
        adaptation = _clamp(0.3 + 0.12 * len(recent_city_days) - 0.08 * city_changes)
        last_city = str(history[-1].get("city") or "") if history else ""
        sense_of_home = _clamp(0.35 + (0.2 if last_city == city else 0.0) + 0.25 * profile.repeat_place_affinity)
        route_familiarity = _clamp(0.28 + 0.1 * len(recent_city_days))
        emotional_comfort = _clamp(0.4 + adaptation * 0.3 + sense_of_home * 0.2 - fatigue_level / 25)
        social_reserve = _clamp(0.45 + profile.solitude_preference * 0.35 + (0.08 if city_changes else 0.0))
        if last_behavior:
            slow = last_behavior.get("slow_behavior_state") or {}
            adaptation = _clamp((adaptation + float(slow.get("city_adaptation", adaptation))) / 2)
            route_familiarity = _clamp((route_familiarity + float(slow.get("route_familiarity", route_familiarity))) / 2)
        return SlowBehaviorState(
            city_adaptation=adaptation,
            accumulated_fatigue=_clamp(fatigue_level / 10),
            sense_of_home=sense_of_home,
            route_familiarity=route_familiarity,
            emotional_comfort=emotional_comfort,
            social_reserve=social_reserve,
        )

    def _build_daily_state(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        slow_state: SlowBehaviorState,
    ) -> DailyBehaviorState:
        day_type = str(context.get("day_type") or "")
        narrative = context.get("narrative_context")
        phase = str(getattr(narrative, "narrative_phase", "routine_stability") or "routine_stability")
        energy_state = str(getattr(narrative, "energy_state", "medium") or "medium")
        phase_factor = {
            "recovery_phase": -0.18,
            "quiet_reset_phase": -0.12,
            "travel_phase": -0.08,
            "exploration_phase": 0.08,
            "routine_stability": 0.03,
        }.get(phase, 0.0)
        base_energy = {"low": 0.34, "medium": 0.55, "high": 0.74}.get(energy_state, 0.55)
        transit_fatigue = _clamp(slow_state.accumulated_fatigue + (0.25 if day_type in {"travel_day", "airport_transfer", "work_day"} else 0.0))
        energy = _clamp(base_energy + phase_factor - transit_fatigue * 0.3 + slow_state.city_adaptation * 0.1)
        quiet = _clamp(profile.morning_pause_affinity * 0.35 + slow_state.social_reserve * 0.3 + transit_fatigue * 0.25)
        movement = _clamp(profile.city_wandering_affinity * 0.45 + (0.24 if day_type in {"travel_day", "layover_day"} else 0.08) - quiet * 0.18)
        social = _clamp(profile.social_openness * 0.55 + (0.06 if phase == "exploration_phase" else -0.04 if day_type == "work_day" and profile.not_overly_social_on_workdays else 0.0) - slow_state.social_reserve * 0.18)
        routine = _clamp(profile.organization_level * 0.4 + slow_state.route_familiarity * 0.25 + (0.18 if day_type in {"work_day", "hotel_rest"} else -0.08 if day_type in {"travel_day", "airport_transfer"} else 0.0))
        comfort = _clamp(slow_state.emotional_comfort * 0.7 + slow_state.city_adaptation * 0.15)
        mental_load = _clamp(transit_fatigue * 0.35 + (0.24 if day_type in {"work_day", "travel_day"} else 0.1) + (0.08 if phase == "transition_phase" else 0.0))

        if day_type == "work_day":
            presentation = "uniform_composed"
        elif day_type in {"travel_day", "airport_transfer"}:
            presentation = "travel_neat"
        elif quiet >= 0.62:
            presentation = "soft_neat"
        else:
            presentation = "casual_open"

        emotional_tone = "grounded"
        if transit_fatigue >= 0.58 and profile.more_reflective_after_flights:
            emotional_tone = "reflective"
        elif movement >= 0.62 and comfort >= 0.5:
            emotional_tone = "curious"
        elif quiet >= 0.7:
            emotional_tone = "soft"
        elif day_type == "work_day":
            emotional_tone = "focused"

        focus = "gentle" if quiet >= movement else "forward"
        social_mode = "alone_but_in_public"
        if social >= 0.58 and comfort >= 0.55:
            social_mode = "quiet_crowd_around"
        if day_type == "work_day" and social < 0.44:
            social_mode = "colleague_implied_world"
        caption_voice = profile.stable_caption_voice
        if emotional_tone in {"reflective", "soft"}:
            caption_voice = "quiet_reflective"
        elif day_type == "work_day":
            caption_voice = "restrained_workday"

        return DailyBehaviorState(
            energy_level=energy,
            social_openness=social,
            routine_stability=routine,
            transit_fatigue=transit_fatigue,
            comfort_in_city=comfort,
            desire_for_quiet=quiet,
            desire_for_movement=movement,
            emotional_tone=emotional_tone,
            mental_load=mental_load,
            self_presentation_mode=presentation,
            internal_focus=focus,
            social_presence_mode=social_mode,
            caption_voice_mode=caption_voice,
        )

    def _select_emotional_arc(self, context: Dict[str, Any], daily: DailyBehaviorState) -> str:
        narrative = context.get("narrative_context")
        phase = str(getattr(narrative, "narrative_phase", "routine_stability") or "routine_stability")
        day_type = str(context.get("day_type") or "")
        if day_type in {"travel_day", "airport_transfer"} and daily.transit_fatigue > 0.5:
            return "between_flights_introspection"
        if phase == "recovery_phase":
            return "low_energy_recovery"
        if phase == "exploration_phase" and daily.desire_for_movement > 0.55:
            return "curious_city_openness"
        if daily.comfort_in_city < 0.42:
            return "adaptation_in_new_city"
        return self.EMOTIONAL_ARCS.get(phase, "routine_stability")

    def _select_habit(self, context: Dict[str, Any], profile: CharacterBehaviorProfile, daily: DailyBehaviorState) -> Dict[str, str]:
        day_type = str(context.get("day_type") or "")
        habit_memory = self._load_behavior_memory()
        recent_names = [str(row.get("selected_habit") or "") for row in habit_memory[-3:]]
        candidates: List[tuple[float, str]] = []
        for habit_name, meta in self.DEFAULT_HABITS.items():
            if day_type not in meta["contexts"]:
                continue
            score = 1.0
            if habit_name in profile.favorite_habits:
                score += 0.45
            recent_count = recent_names.count(habit_name)
            if recent_count:
                score -= 0.7
            if recent_count >= 2:
                score -= 1.2
            if habit_name == "window_pause" and daily.desire_for_quiet > 0.55:
                score += 0.35
            if habit_name == "slow_walk" and daily.desire_for_movement > 0.55:
                score += 0.25
            if habit_name == "terminal_pause" and day_type in {"travel_day", "airport_transfer"}:
                score += 0.4
            candidates.append((score, habit_name))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        chosen = candidates[0][1] if candidates else "coffee_before_leaving"
        context_label = "recurring_behavior" if chosen in recent_names else "fresh_rotation"
        return {"name": chosen, "context": context_label}

    def _select_place_anchor(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        daily: DailyBehaviorState,
        habit: Dict[str, str],
    ) -> str:
        day_type = str(context.get("day_type") or "")
        habit_place = self.DEFAULT_HABITS.get(habit["name"], {}).get("place", "")
        place_memory = self._load_behavior_memory()
        recent_places = [str(row.get("familiar_place_anchor") or "") for row in place_memory[-3:]]
        preferred = list(profile.favorite_place_archetypes) + [habit_place] + list(self.DEFAULT_PLACE_ANCHORS)
        for place in preferred:
            if not place:
                continue
            if place in recent_places and recent_places.count(place) >= 2:
                continue
            if day_type in {"travel_day", "airport_transfer"} and "airport" in place:
                return place
            if daily.desire_for_quiet > 0.6 and any(token in place for token in ["window", "desk", "corner", "mirror"]):
                return place
            if daily.desire_for_movement > 0.58 and "cafe" in place:
                return place
        return habit_place or "living space corner"

    def _select_recurring_objects(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        habit: Dict[str, str],
    ) -> List[str]:
        day_type = str(context.get("day_type") or "")
        objects = list(dict.fromkeys(
            self.DEFAULT_OBJECTS.get(day_type, ["phone", "bag"]) +
            self.DEFAULT_HABITS.get(habit["name"], {}).get("objects", []) +
            profile.recurring_objects
        ))
        behavior_memory = self._load_behavior_memory()
        recent_object_sets = [self._split_csv(row.get("recurring_objects_in_scene")) for row in behavior_memory[-2:]]
        filtered: List[str] = []
        for obj in objects:
            if sum(1 for row in recent_object_sets if obj in row) >= 2 and len(objects) > 3:
                continue
            filtered.append(obj)
        return filtered[:4]

    def _build_transition_hint(
        self,
        context: Dict[str, Any],
        daily: DailyBehaviorState,
        place_anchor: str,
        objects: List[str],
    ) -> str:
        continuity = context.get("continuity_context") or {}
        previous = str(continuity.get("previous_evening_moment") or "")
        last_days = continuity.get("recent_days") or []
        previous_city = str(last_days[0].get("city") or "") if last_days else ""
        city = str(context.get("city") or "")
        if previous_city and previous_city != city:
            return f"subtle_arrival_energy_from_{previous_city}"
        if daily.transit_fatigue > 0.55:
            return f"same_{objects[0]}_carried_forward" if objects else "subtle_tiredness_after_travel"
        if previous:
            return f"echo_of_{previous.replace(' ', '_')[:36]}"
        return f"continuation_via_{place_anchor.replace(' ', '_')}"

    def _outfit_behavior_mode(self, context: Dict[str, Any], daily: DailyBehaviorState) -> str:
        day_type = str(context.get("day_type") or "")
        if day_type == "work_day":
            return "uniform_mode"
        if day_type in {"travel_day", "airport_transfer"}:
            return "travel_casual_mode"
        if daily.desire_for_quiet > 0.58:
            return "soft_casual_mode"
        return "lifestyle_mode"

    def _scene_families(self, context: Dict[str, Any], daily: DailyBehaviorState, emotional_arc: str) -> List[str]:
        day_type = str(context.get("day_type") or "")
        families: List[str] = []
        if day_type in {"travel_day", "airport_transfer"}:
            families.extend(["transit", "preparation"])
        if day_type == "work_day":
            families.extend(["workday", "transit"])
        if daily.desire_for_quiet > 0.56:
            families.extend(["private", "quiet_public"])
        if daily.desire_for_movement > 0.56:
            families.append("city_walk")
        if emotional_arc in {"curious_city_openness", "adaptation_in_new_city"}:
            families.append("urban_observation")
        if emotional_arc in {"low_energy_recovery", "quiet_settling"}:
            families.append("gentle_reset")
        return list(dict.fromkeys(families or ["quiet_public", "private"]))

    def _likely_actions(self, habit: Dict[str, str], daily: DailyBehaviorState) -> List[str]:
        actions = list(self.DEFAULT_HABITS.get(habit["name"], {}).get("actions", []))
        if daily.self_presentation_mode in {"uniform_composed", "travel_neat"}:
            actions.append("adjust_clothing")
        if daily.social_presence_mode == "quiet_crowd_around":
            actions.append("move_through_background_crowd")
        return list(dict.fromkeys(actions))

    def _gesture_bias(self, profile: CharacterBehaviorProfile, daily: DailyBehaviorState) -> List[str]:
        gestures = ["small_hair_adjustment", "touch_bag_strap", "brief_side_glance"]
        if profile.uses_familiar_gestures_more_than_dramatic_posing:
            gestures.append("soft_posture_reset")
        if daily.self_presentation_mode == "uniform_composed":
            gestures.append("straighten_jacket")
        return list(dict.fromkeys(gestures))

    def _anti_repetition_flags(self, context: Dict[str, Any], habit: str, place: str, arc: str) -> List[str]:
        behavior_memory = self._load_behavior_memory()
        flags: List[str] = []
        last_rows = behavior_memory[-3:]
        if sum(1 for row in last_rows if str(row.get("selected_habit") or "") == habit) >= 1:
            flags.append("habit_recently_used")
        if sum(1 for row in last_rows if str(row.get("familiar_place_anchor") or "") == place) >= 1:
            flags.append("place_recently_used")
        if sum(1 for row in last_rows if str(row.get("emotional_arc") or "") == arc) >= 2:
            flags.append("arc_repetition_pressure")
        recent_history = context.get("recent_history") or []
        if len(recent_history) >= 2 and all(str(row.get("day_type") or "") == str(context.get("day_type") or "") for row in recent_history[-2:]):
            flags.append("same_day_type_streak")
        return flags

    def _load_behavior_memory(self) -> List[Dict[str, Any]]:
        if hasattr(self.state_store, "load_behavior_memory"):
            try:
                return self.state_store.load_behavior_memory() or []
            except Exception:
                return []
        return []

    @staticmethod
    def _split_csv(value: Any) -> List[str]:
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]

    @staticmethod
    def _as_bool(value: Any, default: bool) -> bool:
        if value in (None, ""):
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
