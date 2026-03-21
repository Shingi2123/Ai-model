from datetime import date

from virtual_persona.pipeline.behavioral_logic_engine import BehavioralLogicEngine


class Narrative:
    def __init__(self, phase: str, energy: str = "medium") -> None:
        self.narrative_phase = phase
        self.energy_state = energy


class LifeState:
    def __init__(self, fatigue_level: int = 4) -> None:
        self.fatigue_level = fatigue_level


class DummyState:
    def __init__(self, behavior_memory=None):
        self.behavior_memory = behavior_memory or []

    def load_behavior_memory(self):
        return self.behavior_memory


def _context(day_type="travel_day", city="Paris", phase="travel_phase", energy="medium", recent_history=None, behavior_memory=None):
    return {
        "date": date(2026, 3, 20),
        "city": city,
        "day_type": day_type,
        "narrative_context": Narrative(phase, energy),
        "life_state": LifeState(7 if day_type in {"travel_day", "airport_transfer"} else 4),
        "recent_history": recent_history or [],
        "continuity_context": {
            "recent_days": recent_history or [],
            "previous_evening_moment": "quiet room before leaving",
            "arc_hint": "arrival_and_adaptation",
        },
        "character_profile": {
            "behavior_favorite_habits": "window_pause, terminal_pause, coffee_before_leaving",
            "behavior_favorite_place_archetypes": "quiet hotel window, airport side corridor, soft morning desk",
            "behavior_recurring_objects": "shoulder_bag, carry_on, mug, phone",
            "stable_caption_voice": "quiet_observational",
        },
        "_engine_state": DummyState(behavior_memory),
    }


def test_behavior_engine_keeps_travel_day_grounded_after_recent_transit():
    state = DummyState(
        [
            {
                "date": "2026-03-18",
                "selected_habit": "terminal_pause",
                "familiar_place_anchor": "airport side corridor",
                "emotional_arc": "between_flights_introspection",
                "daily_behavior_state": {"energy_level": 0.42},
                "slow_behavior_state": {"city_adaptation": 0.33, "route_familiarity": 0.28},
            }
        ]
    )
    context = _context(
        recent_history=[
            {"date": "2026-03-18", "city": "Rome", "day_type": "travel_day"},
            {"date": "2026-03-19", "city": "Paris", "day_type": "travel_day"},
        ]
    )
    engine = BehavioralLogicEngine(state)

    behavior = engine.build(context)

    assert behavior.daily_state.energy_level < 0.65
    assert behavior.daily_state.transit_fatigue > 0.45
    assert behavior.emotional_arc in {"between_flights_introspection", "adaptation_in_new_city"}
    assert "transit" in behavior.allowed_scene_families


def test_behavior_engine_applies_anti_repetition_to_habit_and_place():
    repeated = [
        {
            "date": "2026-03-17",
            "selected_habit": "window_pause",
            "familiar_place_anchor": "quiet hotel window",
            "emotional_arc": "quiet_settling",
            "daily_behavior_state": {"energy_level": 0.5},
            "slow_behavior_state": {"city_adaptation": 0.55, "route_familiarity": 0.5},
        },
        {
            "date": "2026-03-18",
            "selected_habit": "window_pause",
            "familiar_place_anchor": "quiet hotel window",
            "emotional_arc": "quiet_settling",
            "daily_behavior_state": {"energy_level": 0.48},
            "slow_behavior_state": {"city_adaptation": 0.58, "route_familiarity": 0.56},
        },
    ]
    engine = BehavioralLogicEngine(DummyState(repeated))

    behavior = engine.build(_context(day_type="hotel_rest", phase="quiet_reset_phase", energy="low"))

    assert behavior.selected_habit != "window_pause"
    assert behavior.familiar_place_anchor != "quiet hotel window"


def test_behavior_engine_selects_caption_voice_and_object_continuity():
    engine = BehavioralLogicEngine(DummyState())

    behavior = engine.build(_context(day_type="work_day", phase="routine_stability", energy="medium"))

    assert behavior.daily_state.caption_voice_mode in {"restrained_workday", "quiet_reflective", "quiet_observational"}
    assert behavior.daily_state.self_presentation_mode == "uniform_composed"
    assert "phone" in behavior.recurring_objects
    assert behavior.habit_family
    assert behavior.action_family


def test_behavior_engine_smooths_state_and_marks_repetition_pressure():
    engine = BehavioralLogicEngine(
        DummyState(
            [
                {
                    "date": "2026-03-17",
                    "selected_habit": "coffee_before_leaving",
                    "habit_family": "departure_ritual",
                    "familiar_place_anchor": "soft morning desk",
                    "emotional_arc": "quiet_settling",
                    "caption_voice_mode": "quiet_reflective",
                    "recurring_objects_in_scene": "mug, bag, phone",
                    "daily_behavior_state": {
                        "energy_level": 0.52,
                        "social_openness": 0.4,
                        "routine_stability": 0.66,
                        "desire_for_quiet": 0.69,
                        "desire_for_movement": 0.31,
                    },
                    "slow_behavior_state": {
                        "city_adaptation": 0.61,
                        "route_familiarity": 0.58,
                        "city_confidence": 0.55,
                        "settledness": 0.57,
                    },
                },
                {
                    "date": "2026-03-18",
                    "selected_habit": "quiet_before_leaving",
                    "habit_family": "departure_ritual",
                    "familiar_place_anchor": "soft morning desk",
                    "emotional_arc": "quiet_settling",
                    "caption_voice_mode": "quiet_reflective",
                    "recurring_objects_in_scene": "mug, bag, phone",
                    "daily_behavior_state": {
                        "energy_level": 0.49,
                        "social_openness": 0.39,
                        "routine_stability": 0.68,
                        "desire_for_quiet": 0.72,
                        "desire_for_movement": 0.28,
                    },
                    "slow_behavior_state": {
                        "city_adaptation": 0.64,
                        "route_familiarity": 0.61,
                        "city_confidence": 0.58,
                        "settledness": 0.6,
                    },
                },
            ]
        )
    )

    behavior = engine.build(_context(day_type="travel_day", phase="transition_phase", energy="medium"))

    assert 0.3 < behavior.daily_state.energy_level < 0.7
    assert "caption_voice_streak" in behavior.anti_repetition_flags
    assert behavior.caption_opening_guard
