from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from typing import Any, Dict, List, Sequence

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
            "family": "quiet_pause",
            "tone_family": "reflective_pause",
            "min_gap_days": 2,
            "place": "quiet hotel window",
            "objects": ["mug", "phone"],
            "actions": ["pause_by_window", "steady_breath", "small_hair_adjustment"],
        },
        "coffee_before_leaving": {
            "contexts": {"travel_day", "work_day", "day_off", "layover_day"},
            "family": "departure_ritual",
            "tone_family": "anchoring_ritual",
            "min_gap_days": 1,
            "place": "soft morning desk",
            "objects": ["mug", "bag"],
            "actions": ["coffee_pause", "bag_check", "quiet_start"],
        },
        "terminal_pause": {
            "contexts": {"travel_day", "airport_transfer", "work_day"},
            "family": "transit_ritual",
            "tone_family": "transit_introspection",
            "min_gap_days": 2,
            "place": "airport side corridor",
            "objects": ["carry_on", "shoulder_bag", "headphones"],
            "actions": ["terminal_pause", "look_to_window", "touch_bag_strap"],
        },
        "outfit_tidy": {
            "contexts": {"work_day", "travel_day", "airport_transfer"},
            "family": "self_presentation",
            "tone_family": "composed_focus",
            "min_gap_days": 1,
            "place": "hallway mirror",
            "objects": ["jacket", "phone"],
            "actions": ["smooth_sleeve", "check_collar", "steady_posture"],
        },
        "quiet_before_leaving": {
            "contexts": {"travel_day", "hotel_rest", "layover_day"},
            "family": "departure_ritual",
            "tone_family": "departure_softness",
            "min_gap_days": 2,
            "place": "tidy room mirror",
            "objects": ["bag", "jacket", "suitcase"],
            "actions": ["last_room_scan", "touch_handle", "small_reset"],
        },
        "slow_walk": {
            "contexts": {"day_off", "layover_day", "hotel_rest"},
            "family": "gentle_movement",
            "tone_family": "soft_openness",
            "min_gap_days": 2,
            "place": "cafe corner near glass",
            "objects": ["shoulder_bag", "sunglasses"],
            "actions": ["slow_walk", "look_sideways", "quiet_notice"],
        },
    }
    DEFAULT_PLACE_ANCHORS = {
        "quiet hotel window": {"family": "window_corner", "label": "familiar quiet window"},
        "airport side corridor": {"family": "transit_edge", "label": "side corridor she tends to choose"},
        "cafe corner near glass": {"family": "public_corner", "label": "glass-side cafe corner"},
        "tidy room mirror": {"family": "private_reset", "label": "tidy mirror corner"},
        "hallway mirror": {"family": "departure_axis", "label": "hallway mirror before leaving"},
        "living space corner": {"family": "home_base", "label": "soft living-space corner"},
        "soft morning desk": {"family": "morning_station", "label": "small morning desk setup"},
    }
    DEFAULT_OBJECTS = {
        "travel_day": ["carry_on", "shoulder_bag", "jacket", "headphones", "phone", "scarf"],
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
        "transition_phase": "subtle_pre_departure_melancholy",
    }
    CAPTION_OPENINGS = {
        "quiet_reflective": ["still", "today", "kept", "softly"],
        "restrained_workday": ["early", "workday", "between", "just"],
        "quiet_observational": ["small", "somehow", "another", "little"],
    }

    def __init__(self, state_store: Any) -> None:
        self.state_store = state_store

    def build(self, context: Dict[str, Any]) -> BehavioralContext:
        profile = self._build_profile(context.get("character_profile") or {})
        memory = self._load_behavior_memory()
        slow_state = self._build_slow_state(context, profile, memory)
        daily_state = self._build_daily_state(context, profile, slow_state, memory)
        emotional_arc = self._select_emotional_arc(context, daily_state, slow_state)
        habit = self._select_habit(context, profile, daily_state, memory)
        familiar_place_anchor = self._select_place_anchor(context, profile, daily_state, slow_state, habit, memory)
        place_meta = self.DEFAULT_PLACE_ANCHORS.get(familiar_place_anchor, {})
        familiarity_score = self._familiarity_score(familiar_place_anchor, slow_state, memory)
        recurring_objects = self._select_recurring_objects(context, profile, daily_state, habit, memory)
        object_presence_mode = self._object_presence_mode(context, daily_state, recurring_objects)
        transition_hint, transition_context = self._build_transition_hint(context, daily_state, familiar_place_anchor, recurring_objects)
        outfit_behavior_mode = self._outfit_behavior_mode(context, daily_state)
        allowed_scene_families = self._scene_families(context, daily_state, emotional_arc, habit["family"], outfit_behavior_mode)
        likely_actions = self._likely_actions(habit, daily_state, recurring_objects)
        gesture_bias = self._gesture_bias(profile, daily_state, outfit_behavior_mode)
        anti_repetition_flags = self._anti_repetition_flags(
            context=context,
            memory=memory,
            habit=habit["name"],
            habit_family=habit["family"],
            place=familiar_place_anchor,
            arc=emotional_arc,
            objects=recurring_objects,
            caption_voice_mode=daily_state.caption_voice_mode,
            emotional_tone_family=daily_state.emotional_tone_family,
            place_family=str(place_meta.get("family", "")),
        )
        social_context_hint, social_presence_detail = self._social_context_hint(daily_state)
        caption_opening_guard = self._caption_opening_guard(daily_state.caption_voice_mode, memory)
        caption_voice_constraints = self._caption_voice_constraints(profile, daily_state, emotional_arc)
        familiar_place_label = str(place_meta.get("label", familiar_place_anchor))
        action_family = self._primary_action_family(habit["family"], likely_actions)
        recurring_habit_summary = self._habit_summary(habit["name"], habit["family"], memory)
        debug_summary = (
            f"energy={daily_state.energy_level:.2f}; quiet={daily_state.desire_for_quiet:.2f}; "
            f"movement={daily_state.desire_for_movement:.2f}; hurry={daily_state.hurry_level:.2f}; "
            f"arc={emotional_arc}; habit={habit['name']}; place={familiar_place_anchor}; "
            f"objects={','.join(recurring_objects[:3])}; social={daily_state.social_presence_mode}; "
            f"presentation={daily_state.self_presentation_mode}"
        )
        return BehavioralContext(
            profile=profile,
            slow_state=slow_state,
            daily_state=daily_state,
            emotional_arc=emotional_arc,
            selected_habit=habit["name"],
            habit_family=habit["family"],
            habit_context=habit["context"],
            recurring_habit_summary=recurring_habit_summary,
            familiar_place_anchor=familiar_place_anchor,
            familiar_place_label=familiar_place_label,
            familiar_place_family=str(place_meta.get("family", "")),
            familiarity_score=familiarity_score,
            recurring_objects=recurring_objects,
            object_presence_mode=object_presence_mode,
            outfit_behavior_mode=outfit_behavior_mode,
            transition_hint=transition_hint,
            transition_context=transition_context,
            allowed_scene_families=allowed_scene_families,
            likely_actions=likely_actions,
            action_family=action_family,
            gesture_bias=gesture_bias,
            social_context_hint=social_context_hint,
            social_presence_detail=social_presence_detail,
            caption_voice_constraints=caption_voice_constraints,
            caption_opening_guard=caption_opening_guard,
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
            "habit_family": behavior.habit_family,
            "habit_context": behavior.habit_context,
            "recurring_habit_summary": behavior.recurring_habit_summary,
            "familiar_place_anchor": behavior.familiar_place_anchor,
            "familiar_place_label": behavior.familiar_place_label,
            "familiar_place_family": behavior.familiar_place_family,
            "familiarity_score": behavior.familiarity_score,
            "recurring_objects_in_scene": ", ".join(behavior.recurring_objects),
            "object_presence_mode": behavior.object_presence_mode,
            "self_presentation_mode": behavior.daily_state.self_presentation_mode,
            "social_presence_mode": behavior.daily_state.social_presence_mode,
            "transition_hint_used": behavior.transition_hint,
            "transition_context": behavior.transition_context,
            "caption_voice_mode": behavior.daily_state.caption_voice_mode,
            "action_family": behavior.action_family,
            "emotional_tone_family": behavior.daily_state.emotional_tone_family,
            "social_context_hint": behavior.social_context_hint,
            "social_presence_detail": behavior.social_presence_detail,
            "allowed_scene_families": ", ".join(behavior.allowed_scene_families),
            "likely_actions": ", ".join(behavior.likely_actions),
            "gesture_bias": ", ".join(behavior.gesture_bias),
            "caption_voice_constraints": ", ".join(behavior.caption_voice_constraints),
            "caption_opening_guard": ", ".join(behavior.caption_opening_guard),
            "anti_repetition_flags": ", ".join(behavior.anti_repetition_flags),
            "day_behavior_summary": behavior.debug_summary,
            "daily_behavior_state": daily,
            "slow_behavior_state": slow,
        }

    def _build_profile(self, profile: Dict[str, Any]) -> CharacterBehaviorProfile:
        habits = self._split_csv(profile.get("behavior_favorite_habits")) or ["window_pause", "coffee_before_leaving", "outfit_tidy"]
        place_archetypes = self._split_csv(profile.get("behavior_favorite_place_archetypes")) or list(self.DEFAULT_PLACE_ANCHORS.keys())[:4]
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
            preferred_repeat_routes=float(profile.get("behavior_preferred_repeat_routes") or 0.72),
            quiet_caption_restraint=float(profile.get("behavior_quiet_caption_restraint") or 0.78),
            caption_openness=float(profile.get("behavior_caption_openness") or 0.34),
            caption_length_preference=float(profile.get("behavior_caption_length_preference") or 0.42),
            reflective_bias=float(profile.get("behavior_reflective_bias") or 0.72),
            visual_consistency_need=float(profile.get("behavior_visual_consistency_need") or 0.8),
            familiar_space_bias=float(profile.get("behavior_familiar_space_bias") or 0.74),
            travel_lightness_preference=float(profile.get("behavior_travel_lightness_preference") or 0.76),
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

    def _build_slow_state(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        memory: Sequence[Dict[str, Any]],
    ) -> SlowBehaviorState:
        history = context.get("recent_history") or []
        city = str(context.get("city") or "")
        life_state = context.get("life_state")
        fatigue_level = float(getattr(life_state, "fatigue_level", 3) or 3)
        recent_city_days = [row for row in history[-7:] if str(row.get("city") or "") == city]
        recent_city_changes = sum(1 for row in history[-5:] if str(row.get("city") or "") and str(row.get("city") or "") != city)
        travel_days = sum(1 for row in history[-5:] if str(row.get("day_type") or "") in {"travel_day", "airport_transfer"})
        last_slow = self._coerce_mapping(self._coerce_json(memory[-1].get("slow_behavior_state"))) if memory else {}

        adaptation = _clamp(0.22 + 0.12 * len(recent_city_days) - 0.08 * recent_city_changes + profile.familiar_space_bias * 0.1)
        sense_of_home = _clamp(0.18 + adaptation * 0.38 + profile.repeat_place_affinity * 0.24)
        route_familiarity = _clamp(0.2 + len(recent_city_days) * 0.11 + profile.preferred_repeat_routes * 0.18)
        city_confidence = _clamp(0.16 + adaptation * 0.42 + route_familiarity * 0.24)
        settledness = _clamp(0.15 + sense_of_home * 0.32 + (0.16 if recent_city_days else 0.0) - fatigue_level / 18 - travel_days * 0.04)
        emotional_comfort = _clamp(0.24 + adaptation * 0.26 + sense_of_home * 0.18 + settledness * 0.16 - fatigue_level / 24)
        social_reserve = _clamp(0.4 + profile.solitude_preference * 0.3 + recent_city_changes * 0.05)
        location_comfort = _clamp(0.22 + emotional_comfort * 0.36 + profile.familiar_space_bias * 0.2)
        familiarity_weight = _clamp(0.2 + route_familiarity * 0.3 + profile.repeat_place_affinity * 0.24)
        recent_transition_load = _clamp(travel_days * 0.16 + recent_city_changes * 0.1 + fatigue_level / 18)

        if last_slow:
            adaptation = self._smooth(adaptation, float(last_slow.get("city_adaptation", adaptation)), 0.6)
            route_familiarity = self._smooth(route_familiarity, float(last_slow.get("route_familiarity", route_familiarity)), 0.56)
            city_confidence = self._smooth(city_confidence, float(last_slow.get("city_confidence", city_confidence)), 0.56)
            settledness = self._smooth(settledness, float(last_slow.get("settledness", settledness)), 0.6)
            location_comfort = self._smooth(location_comfort, float(last_slow.get("location_comfort", location_comfort)), 0.58)
            familiarity_weight = self._smooth(familiarity_weight, float(last_slow.get("familiarity_weight", familiarity_weight)), 0.58)

        return SlowBehaviorState(
            city_adaptation=adaptation,
            accumulated_fatigue=_clamp(fatigue_level / 10),
            sense_of_home=sense_of_home,
            route_familiarity=route_familiarity,
            emotional_comfort=emotional_comfort,
            social_reserve=social_reserve,
            city_confidence=city_confidence,
            settledness=settledness,
            location_comfort=location_comfort,
            familiarity_weight=familiarity_weight,
            recent_transition_load=recent_transition_load,
        )

    def _build_daily_state(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        slow_state: SlowBehaviorState,
        memory: Sequence[Dict[str, Any]],
    ) -> DailyBehaviorState:
        day_type = str(context.get("day_type") or "")
        narrative = context.get("narrative_context")
        phase = str(getattr(narrative, "narrative_phase", "routine_stability") or "routine_stability")
        energy_state = str(getattr(narrative, "energy_state", "medium") or "medium")
        last_daily = self._coerce_mapping(self._coerce_json(memory[-1].get("daily_behavior_state"))) if memory else {}

        base_energy = {"low": 0.34, "medium": 0.56, "high": 0.74}.get(energy_state, 0.56)
        transit_fatigue = _clamp(
            slow_state.accumulated_fatigue
            + slow_state.recent_transition_load * 0.22
            + (0.24 if day_type in {"travel_day", "airport_transfer"} else 0.18 if day_type == "work_day" else 0.04)
        )
        hurry = _clamp(
            0.16
            + (0.3 if day_type in {"travel_day", "airport_transfer"} else 0.18 if day_type == "work_day" else 0.06)
            + (0.1 if phase == "transition_phase" else 0.0)
            - profile.comfort_with_haste * 0.12
        )
        quiet = _clamp(
            profile.morning_pause_affinity * 0.3
            + slow_state.social_reserve * 0.24
            + transit_fatigue * 0.16
            + (0.1 if phase in {"recovery_phase", "quiet_reset_phase"} else 0.0)
            + (0.06 if slow_state.city_adaptation < 0.45 else 0.0)
        )
        movement = _clamp(
            profile.city_wandering_affinity * 0.4
            + slow_state.city_confidence * 0.18
            + (0.24 if day_type in {"travel_day", "layover_day"} else 0.08)
            - quiet * 0.14
        )
        social = _clamp(
            profile.social_openness * 0.48
            + slow_state.emotional_comfort * 0.16
            + (0.08 if phase == "exploration_phase" else 0.0)
            - slow_state.social_reserve * 0.18
            - (0.08 if day_type == "work_day" and profile.not_overly_social_on_workdays else 0.0)
        )
        routine = _clamp(
            profile.organization_level * 0.34
            + slow_state.route_familiarity * 0.18
            + slow_state.settledness * 0.18
            + (0.18 if day_type in {"work_day", "hotel_rest"} else -0.06 if day_type in {"travel_day", "airport_transfer"} else 0.04)
        )
        comfort = _clamp(slow_state.emotional_comfort * 0.58 + slow_state.city_adaptation * 0.14 + slow_state.location_comfort * 0.18)
        mental_load = _clamp(transit_fatigue * 0.28 + hurry * 0.24 + (0.24 if day_type == "work_day" else 0.16 if day_type in {"travel_day", "airport_transfer"} else 0.08))
        softness = _clamp(quiet * 0.38 + comfort * 0.26 + profile.quiet_caption_restraint * 0.14 - hurry * 0.12)
        internal_coherence = _clamp(routine * 0.33 + profile.organization_level * 0.22 + slow_state.settledness * 0.18 - mental_load * 0.1)
        energy = _clamp(base_energy - transit_fatigue * 0.24 - mental_load * 0.12 + slow_state.city_adaptation * 0.08 + movement * 0.06)

        if last_daily:
            energy = self._smooth(energy, float(last_daily.get("energy_level", energy)), 0.68)
            social = self._smooth(social, float(last_daily.get("social_openness", social)), 0.68)
            routine = self._smooth(routine, float(last_daily.get("routine_stability", routine)), 0.68)
            quiet = self._smooth(quiet, float(last_daily.get("desire_for_quiet", quiet)), 0.68)
            movement = self._smooth(movement, float(last_daily.get("desire_for_movement", movement)), 0.68)

        if day_type == "work_day":
            presentation = "uniform_composed"
        elif day_type in {"travel_day", "airport_transfer"}:
            presentation = "travel_neat"
        elif quiet >= 0.62:
            presentation = "soft_neat"
        else:
            presentation = "casual_open"

        emotional_tone = "grounded"
        tone_family = "grounded_daily"
        if transit_fatigue >= 0.58 and profile.more_reflective_after_flights:
            emotional_tone = "reflective"
            tone_family = "travel_reflection"
        elif movement >= 0.62 and comfort >= 0.5:
            emotional_tone = "curious"
            tone_family = "open_city"
        elif quiet >= 0.7:
            emotional_tone = "soft"
            tone_family = "quiet_softness"
        elif day_type == "work_day":
            emotional_tone = "focused"
            tone_family = "work_focus"

        focus = "gentle" if quiet >= movement else "forward"
        social_mode = "alone_but_in_public"
        if social >= 0.6 and comfort >= 0.52:
            social_mode = "quiet_crowd_around"
        elif day_type == "work_day":
            social_mode = "colleague_implied_world"
        elif social <= 0.34 and quiet >= 0.62:
            social_mode = "unseen_social_context"

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
            hurry_level=hurry,
            internal_coherence=internal_coherence,
            softness=softness,
            self_presentation_mode=presentation,
            internal_focus=focus,
            social_presence_mode=social_mode,
            caption_voice_mode=caption_voice,
            emotional_tone_family=tone_family,
        )

    def _select_emotional_arc(self, context: Dict[str, Any], daily: DailyBehaviorState, slow: SlowBehaviorState) -> str:
        narrative = context.get("narrative_context")
        phase = str(getattr(narrative, "narrative_phase", "routine_stability") or "routine_stability")
        day_type = str(context.get("day_type") or "")
        if day_type in {"travel_day", "airport_transfer"} and daily.transit_fatigue > 0.5:
            return "between_flights_introspection"
        if phase == "recovery_phase":
            return "low_energy_recovery"
        if phase == "exploration_phase" and daily.desire_for_movement > 0.55:
            return "curious_city_openness"
        if slow.city_adaptation < 0.42:
            return "adaptation_in_new_city"
        if phase == "transition_phase":
            return "subtle_pre_departure_melancholy"
        if daily.desire_for_quiet > 0.66:
            return "quiet_settling"
        return self.EMOTIONAL_ARCS.get(phase, "routine_stability")

    def _select_habit(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        daily: DailyBehaviorState,
        memory: Sequence[Dict[str, Any]],
    ) -> Dict[str, str]:
        day_type = str(context.get("day_type") or "")
        candidates: List[tuple[float, str]] = []
        for habit_name, meta in self.DEFAULT_HABITS.items():
            if day_type not in meta["contexts"]:
                continue
            score = 1.0
            if habit_name in profile.favorite_habits:
                score += 0.45
            gap = self._days_since(memory, "selected_habit", habit_name)
            recent_count = self._recent_count(memory[-6:], "selected_habit", habit_name)
            family_count = self._recent_count(memory[-5:], "habit_family", str(meta.get("family", "")))
            if gap is not None and gap < int(meta["min_gap_days"]):
                score -= 1.2
            if gap is not None and gap <= int(meta["min_gap_days"]) + 1:
                score -= 0.35
            score -= recent_count * 0.18
            score -= max(0, family_count - 1) * 0.12
            if habit_name == "window_pause" and daily.desire_for_quiet > 0.58:
                score += 0.35
            if habit_name == "slow_walk" and daily.desire_for_movement > 0.56:
                score += 0.26
            if habit_name == "terminal_pause" and day_type in {"travel_day", "airport_transfer"}:
                score += 0.44
            if habit_name == "outfit_tidy" and daily.self_presentation_mode in {"uniform_composed", "travel_neat"}:
                score += 0.24
            if habit_name == "coffee_before_leaving" and profile.keeps_small_rituals:
                score += 0.12
            candidates.append((score, habit_name))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        chosen = candidates[0][1] if candidates else "coffee_before_leaving"
        gap = self._days_since(memory, "selected_habit", chosen)
        return {
            "name": chosen,
            "family": str(self.DEFAULT_HABITS.get(chosen, {}).get("family", "daily_ritual")),
            "context": "recurring_behavior" if gap is not None else "fresh_rotation",
        }

    def _select_place_anchor(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        daily: DailyBehaviorState,
        slow: SlowBehaviorState,
        habit: Dict[str, str],
        memory: Sequence[Dict[str, Any]],
    ) -> str:
        day_type = str(context.get("day_type") or "")
        habit_place = str(self.DEFAULT_HABITS.get(habit["name"], {}).get("place", ""))
        preferred = list(dict.fromkeys(list(profile.favorite_place_archetypes) + [habit_place] + list(self.DEFAULT_PLACE_ANCHORS.keys())))
        best_place = habit_place or "living space corner"
        best_score = -999.0
        for place in preferred:
            if not place:
                continue
            meta = self.DEFAULT_PLACE_ANCHORS.get(place, {})
            family = str(meta.get("family", ""))
            gap = self._days_since(memory, "familiar_place_anchor", place)
            usage = self._recent_count(memory[-8:], "familiar_place_anchor", place)
            family_usage = self._recent_count(memory[-5:], "familiar_place_family", family)
            score = 1.0
            score += self._familiarity_score(place, slow, memory) * 0.32
            if gap is not None and gap < 2:
                score -= 0.8
            if gap is not None and gap >= 3:
                score += 0.18
            score -= usage * 0.12
            score -= max(0, family_usage - 1) * 0.08
            if place == habit_place:
                score += 0.42
            if day_type in {"travel_day", "airport_transfer"} and "airport" in place:
                score += 0.34
            if daily.desire_for_quiet > 0.6 and any(token in place for token in ["window", "desk", "corner", "mirror"]):
                score += 0.24
            if daily.desire_for_movement > 0.58 and "cafe" in place:
                score += 0.16
            if slow.city_adaptation < 0.45 and family in {"window_corner", "private_reset", "morning_station"}:
                score += 0.12
            if score > best_score:
                best_place = place
                best_score = score
        return best_place

    def _select_recurring_objects(
        self,
        context: Dict[str, Any],
        profile: CharacterBehaviorProfile,
        daily: DailyBehaviorState,
        habit: Dict[str, str],
        memory: Sequence[Dict[str, Any]],
    ) -> List[str]:
        day_type = str(context.get("day_type") or "")
        objects = list(
            dict.fromkeys(
                self.DEFAULT_OBJECTS.get(day_type, ["phone", "bag"])
                + self.DEFAULT_HABITS.get(habit["name"], {}).get("objects", [])
                + profile.recurring_objects
            )
        )
        recent_object_sets = [self._split_csv(row.get("recurring_objects_in_scene")) for row in memory[-4:]]
        filtered: List[str] = []
        for obj in objects:
            repeat_hits = sum(1 for row in recent_object_sets if obj in row)
            if repeat_hits >= 3 and len(objects) > 4:
                continue
            if obj == "phone" and daily.desire_for_quiet > 0.72 and day_type == "day_off":
                continue
            if obj in {"carry_on", "suitcase"} and day_type not in {"travel_day", "airport_transfer"}:
                continue
            if obj == "mug" and day_type in {"airport_transfer", "travel_day"} and daily.hurry_level > 0.54:
                continue
            filtered.append(obj)
        return filtered[:4]

    def _build_transition_hint(
        self,
        context: Dict[str, Any],
        daily: DailyBehaviorState,
        place_anchor: str,
        objects: List[str],
    ) -> tuple[str, str]:
        continuity = context.get("continuity_context") or {}
        previous = str(continuity.get("previous_evening_moment") or "")
        last_days = continuity.get("recent_days") or []
        previous_city = str(last_days[0].get("city") or "") if last_days else ""
        previous_day_type = str(last_days[0].get("day_type") or "") if last_days else ""
        city = str(context.get("city") or "")
        if previous_city and previous_city != city:
            return f"subtle_arrival_energy_from_{previous_city}", "city_change_transition"
        if previous_day_type in {"travel_day", "airport_transfer"} and daily.transit_fatigue > 0.5:
            return "subtle_tiredness_after_travel", "post_transit_recovery"
        if daily.transit_fatigue > 0.55:
            return (f"same_{objects[0]}_carried_forward" if objects else "subtle_tiredness_after_travel"), "object_continuity"
        if previous:
            return f"echo_of_{previous.replace(' ', '_')[:36]}", "narrative_echo"
        return f"continuation_via_{place_anchor.replace(' ', '_')}", "familiar_space_link"

    def _outfit_behavior_mode(self, context: Dict[str, Any], daily: DailyBehaviorState) -> str:
        day_type = str(context.get("day_type") or "")
        if day_type == "work_day":
            return "uniform_mode"
        if day_type in {"travel_day", "airport_transfer"}:
            return "travel_casual_mode"
        if daily.desire_for_quiet > 0.58:
            return "soft_casual_mode"
        return "lifestyle_mode"

    def _scene_families(
        self,
        context: Dict[str, Any],
        daily: DailyBehaviorState,
        emotional_arc: str,
        habit_family: str,
        outfit_behavior_mode: str,
    ) -> List[str]:
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
        if habit_family == "departure_ritual":
            families.append("departure_transition")
        if emotional_arc in {"curious_city_openness", "adaptation_in_new_city"}:
            families.append("urban_observation")
        if emotional_arc in {"low_energy_recovery", "quiet_settling"}:
            families.append("gentle_reset")
        if outfit_behavior_mode == "uniform_mode":
            families.append("structured_movement")
        elif outfit_behavior_mode == "soft_casual_mode":
            families.append("soft_pause")
        elif outfit_behavior_mode == "travel_casual_mode":
            families.append("travel_ready")
        return list(dict.fromkeys(families or ["quiet_public", "private"]))

    def _likely_actions(self, habit: Dict[str, str], daily: DailyBehaviorState, recurring_objects: List[str]) -> List[str]:
        actions = list(self.DEFAULT_HABITS.get(habit["name"], {}).get("actions", []))
        if daily.self_presentation_mode in {"uniform_composed", "travel_neat"}:
            actions.append("adjust_clothing")
        if daily.social_presence_mode == "quiet_crowd_around":
            actions.append("move_through_background_crowd")
        if recurring_objects and any(obj in {"carry_on", "bag", "shoulder_bag"} for obj in recurring_objects):
            actions.append("check_belongings")
        if daily.desire_for_quiet > 0.68:
            actions.append("hold_small_pause")
        return list(dict.fromkeys(actions))

    def _primary_action_family(self, habit_family: str, actions: Sequence[str]) -> str:
        if habit_family:
            return habit_family
        if any("walk" in action for action in actions):
            return "gentle_movement"
        if any("check" in action or "adjust" in action for action in actions):
            return "preparation"
        return "quiet_pause"

    def _gesture_bias(self, profile: CharacterBehaviorProfile, daily: DailyBehaviorState, outfit_behavior_mode: str) -> List[str]:
        gestures = ["small_hair_adjustment", "touch_bag_strap", "brief_side_glance"]
        if profile.uses_familiar_gestures_more_than_dramatic_posing:
            gestures.append("soft_posture_reset")
        if daily.self_presentation_mode == "uniform_composed":
            gestures.append("straighten_jacket")
        if outfit_behavior_mode == "soft_casual_mode":
            gestures.append("quiet_sleeve_touch")
        return list(dict.fromkeys(gestures))

    def _social_context_hint(self, daily: DailyBehaviorState) -> tuple[str, str]:
        mapping = {
            "alone_but_in_public": (
                "quiet_people_exist_around_her_but_not_center_frame",
                "alone in frame, public life nearby",
            ),
            "quiet_crowd_around": (
                "soft_background_presence_and_city_flow",
                "a small crowd may exist behind her without becoming the story",
            ),
            "colleague_implied_world": (
                "work_context_exists_without_second_main_character",
                "colleagues are implied by structure and movement rather than explicit interaction",
            ),
            "unseen_social_context": (
                "social_world_is_implied_off_camera",
                "the world exists around her, but the day still feels inward",
            ),
        }
        return mapping.get(daily.social_presence_mode, ("subtle_social_background", "subtle social world around her"))

    def _caption_opening_guard(self, voice_mode: str, memory: Sequence[Dict[str, Any]]) -> List[str]:
        recent_modes = [str(row.get("caption_voice_mode") or "") for row in memory[-4:]]
        blocked = list(self.CAPTION_OPENINGS.get(voice_mode, []))
        if recent_modes.count(voice_mode) >= 2:
            blocked = blocked[:2]
        return blocked

    def _anti_repetition_flags(
        self,
        *,
        context: Dict[str, Any],
        memory: Sequence[Dict[str, Any]],
        habit: str,
        habit_family: str,
        place: str,
        arc: str,
        objects: Sequence[str],
        caption_voice_mode: str,
        emotional_tone_family: str,
        place_family: str,
    ) -> List[str]:
        flags: List[str] = []
        last_rows = list(memory[-4:])
        if sum(1 for row in last_rows if str(row.get("selected_habit") or "") == habit) >= 1:
            flags.append("habit_recently_used")
        if sum(1 for row in last_rows if str(row.get("habit_family") or "") == habit_family) >= 2:
            flags.append("habit_family_streak")
        if sum(1 for row in last_rows if str(row.get("familiar_place_anchor") or "") == place) >= 1:
            flags.append("place_recently_used")
        if sum(1 for row in last_rows if str(row.get("familiar_place_family") or "") == place_family) >= 2:
            flags.append("place_family_streak")
        if sum(1 for row in last_rows if str(row.get("emotional_arc") or "") == arc) >= 2:
            flags.append("arc_repetition_pressure")
        if sum(1 for row in last_rows if str(row.get("caption_voice_mode") or "") == caption_voice_mode) >= 2:
            flags.append("caption_voice_streak")
        if sum(1 for row in last_rows if str(row.get("emotional_tone_family") or "") == emotional_tone_family) >= 2:
            flags.append("emotional_tone_streak")

        object_hits = 0
        for row in last_rows:
            row_objects = set(self._split_csv(row.get("recurring_objects_in_scene")))
            if row_objects and row_objects.intersection(objects):
                object_hits += 1
        if object_hits >= 3:
            flags.append("object_rotation_needed")

        recent_history = context.get("recent_history") or []
        if len(recent_history) >= 2 and all(str(row.get("day_type") or "") == str(context.get("day_type") or "") for row in recent_history[-2:]):
            flags.append("same_day_type_streak")
        return flags

    def _caption_voice_constraints(
        self,
        profile: CharacterBehaviorProfile,
        daily: DailyBehaviorState,
        emotional_arc: str,
    ) -> List[str]:
        constraints = [
            "keep the voice restrained and natural",
            "prefer one quiet thought over a dramatic statement",
            "avoid literary flourish or heavy metaphor",
        ]
        if profile.caption_length_preference <= 0.5:
            constraints.append("keep it concise, usually one short sentence")
        if profile.caption_openness <= 0.4:
            constraints.append("stay lightly private rather than fully confessional")
        if daily.caption_voice_mode == "restrained_workday":
            constraints.append("keep it composed and matter-of-fact")
        if emotional_arc in {"quiet_settling", "between_flights_introspection"}:
            constraints.append("allow soft reflection without melodrama")
        return constraints

    def _habit_summary(self, habit_name: str, habit_family: str, memory: Sequence[Dict[str, Any]]) -> str:
        gap = self._days_since(memory, "selected_habit", habit_name)
        if gap is None:
            return f"{habit_family}: first appearance in recent memory"
        return f"{habit_family}: last used {gap}d ago"

    def _familiarity_score(self, place: str, slow_state: SlowBehaviorState, memory: Sequence[Dict[str, Any]]) -> float:
        place_hits = self._recent_count(memory[-10:], "familiar_place_anchor", place)
        base = slow_state.familiarity_weight * 0.48 + slow_state.city_adaptation * 0.2 + slow_state.location_comfort * 0.18
        return _clamp(base + min(place_hits, 4) * 0.06)

    def _object_presence_mode(self, context: Dict[str, Any], daily: DailyBehaviorState, objects: Sequence[str]) -> str:
        day_type = str(context.get("day_type") or "")
        if any(obj in {"carry_on", "suitcase"} for obj in objects):
            return "transit_objects_visible"
        if daily.desire_for_quiet > 0.68 and day_type in {"day_off", "hotel_rest"}:
            return "minimal_objects_soft_frame"
        if daily.self_presentation_mode in {"uniform_composed", "travel_neat"}:
            return "functional_daily_objects"
        return "light_personal_objects"

    def _load_behavior_memory(self) -> List[Dict[str, Any]]:
        if hasattr(self.state_store, "load_behavior_memory"):
            try:
                rows = self.state_store.load_behavior_memory() or []
            except Exception:
                return []
            normalized: List[Dict[str, Any]] = []
            for row in rows:
                payload = dict(row)
                for key in ("daily_behavior_state", "slow_behavior_state"):
                    payload[key] = self._coerce_json(payload.get(key))
                normalized.append(payload)
            return normalized
        return []

    @staticmethod
    def _coerce_mapping(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {}

    @staticmethod
    def _coerce_json(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        text = str(value or "").strip()
        if not text or text[0] not in "{[":
            return value
        try:
            return json.loads(text)
        except Exception:
            return value

    def _days_since(self, memory: Sequence[Dict[str, Any]], key: str, value: str) -> int | None:
        if not value:
            return None
        for idx, row in enumerate(reversed(memory), start=1):
            if str(row.get(key) or "") == value:
                return idx
        return None

    @staticmethod
    def _recent_count(memory: Sequence[Dict[str, Any]], key: str, value: str) -> int:
        return sum(1 for row in memory if str(row.get(key) or "") == value)

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

    @staticmethod
    def _smooth(current: float, previous: float, current_weight: float) -> float:
        return _clamp(current * current_weight + previous * (1 - current_weight))
