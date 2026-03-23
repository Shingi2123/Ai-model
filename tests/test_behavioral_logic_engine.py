from datetime import date

from virtual_persona.pipeline.behavior_engine import BehaviorEngine, build_behavior


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


class DummyAuxState(DummyState):
    def __init__(self, behavior_memory=None, habit_memory=None, place_memory=None, object_usage=None):
        super().__init__(behavior_memory=behavior_memory)
        self.habit_memory = habit_memory or []
        self.place_memory = place_memory or []
        self.object_usage = object_usage or []

    def load_habit_memory(self):
        return self.habit_memory

    def load_place_memory(self):
        return self.place_memory

    def load_object_usage(self):
        return self.object_usage


def _context(day_type="travel_day", city="Paris", phase="travel_phase", energy="medium"):
    return {
        "date": date(2026, 3, 20),
        "city": city,
        "day_type": day_type,
        "narrative_context": Narrative(phase, energy),
        "life_state": LifeState(7 if day_type in {"travel_day", "airport_transfer"} else 4),
        "continuity_context": {"arc_hint": "arrival_and_adaptation" if day_type == "travel_day" else "stable_routine"},
    }


def test_behavior_is_always_generated():
    behavior = build_behavior(_context(), [])

    assert behavior is not None
    assert behavior.energy_level in {"low", "medium", "high"}
    assert behavior.social_mode in {"alone", "light_public", "social"}
    assert behavior.emotional_arc in {"arrival", "routine", "reflection", "transition", "departure"}
    assert behavior.place_anchor in {"hotel_window", "kitchen_corner", "terminal_gate", "cafe_corner"}


def test_behavior_anti_repeat_blocks_third_same_habit_place_and_arc():
    memory = [
        {"date": "2026-03-18", "habit": "coffee_moment", "place_anchor": "terminal_gate", "emotional_arc": "transition"},
        {"date": "2026-03-19", "habit": "coffee_moment", "place_anchor": "terminal_gate", "emotional_arc": "transition"},
    ]

    behavior = build_behavior(_context(day_type="travel_day", phase="transition_phase", energy="medium"), memory)

    assert behavior.habit != "coffee_moment"
    assert behavior.place_anchor != "terminal_gate"
    assert behavior.emotional_arc != "transition"
    assert "habit_varied" in behavior.anti_repetition_flags
    assert "place_varied" in behavior.anti_repetition_flags
    assert "emotional_arc_varied" in behavior.anti_repetition_flags


def test_objects_match_place_and_day_logic():
    terminal_behavior = build_behavior(_context(day_type="travel_day", phase="travel_phase", energy="medium"), [])
    assert "carry_on" in terminal_behavior.objects or terminal_behavior.place_anchor != "terminal_gate"

    kitchen_behavior = build_behavior(_context(day_type="day_off", phase="quiet_reset_phase", energy="low"), [])
    if kitchen_behavior.place_anchor == "kitchen_corner":
        assert "coffee_cup" in kitchen_behavior.objects


def test_place_anchor_stays_logical_for_context():
    work_behavior = build_behavior(_context(day_type="work_day", phase="routine_stability", energy="medium"), [])
    assert work_behavior.place_anchor in {"terminal_gate", "kitchen_corner", "cafe_corner"}

    rest_behavior = build_behavior(_context(day_type="day_off", phase="quiet_reset_phase", energy="low"), [])
    assert rest_behavior.place_anchor in {"hotel_window", "kitchen_corner", "cafe_corner"}


def test_engine_memory_rows_include_new_behavior_fields():
    engine = BehaviorEngine(DummyState())
    behavior = build_behavior(_context(day_type="work_day", phase="routine_stability", energy="medium"), [])

    row = engine.to_memory_row(date(2026, 3, 20), "Paris", "work_day", behavior)

    assert row["behavior_state"]
    assert row["habit"] == behavior.habit
    assert row["place_anchor"] == behavior.place_anchor
    assert row["objects"] == ", ".join(behavior.objects)
    assert row["self_presentation"] == behavior.self_presentation


def test_behavior_engine_uses_auxiliary_memory_sheets_for_anti_repeat():
    state = DummyAuxState(
        behavior_memory=[],
        habit_memory=[
            {"date": "2026-03-18", "city": "Paris", "day_type": "travel_day", "habit": "coffee_moment", "emotional_arc": "transition", "place_anchor": "terminal_gate"},
            {"date": "2026-03-19", "city": "Paris", "day_type": "travel_day", "habit": "coffee_moment", "emotional_arc": "transition", "place_anchor": "terminal_gate"},
        ],
        place_memory=[
            {"date": "2026-03-18", "city": "Paris", "day_type": "travel_day", "place_anchor": "terminal_gate", "emotional_arc": "transition", "habit": "coffee_moment"},
            {"date": "2026-03-19", "city": "Paris", "day_type": "travel_day", "place_anchor": "terminal_gate", "emotional_arc": "transition", "habit": "coffee_moment"},
        ],
        object_usage=[
            {"date": "2026-03-19", "city": "Paris", "day_type": "travel_day", "place_anchor": "terminal_gate", "objects": "coffee_cup, carry_on", "habit": "coffee_moment"},
        ],
    )

    behavior = BehaviorEngine(state).build(_context(day_type="travel_day", phase="transition_phase", energy="medium"))

    assert behavior.habit != "coffee_moment"
    assert behavior.place_anchor != "terminal_gate"
    assert behavior.emotional_arc != "transition"
