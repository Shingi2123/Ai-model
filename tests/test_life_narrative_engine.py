from datetime import date

from virtual_persona.narrative.life_narrative_engine import (
    LifeNarrativeEngine,
    LifeVariationController,
)


class DummyNarrativeState:
    def __init__(self):
        self.narrative_rows = []

    def load_life_state(self):
        return [
            {"date": "2026-01-09", "fatigue_level": 8},
            {"date": "2026-01-08", "fatigue_level": 7},
        ]

    def load_calendar(self):
        return [
            {"date": "2026-01-09", "day_type": "work_day", "city": "Prague"},
            {"date": "2026-01-08", "day_type": "work_day", "city": "Prague"},
            {"date": "2026-01-07", "day_type": "travel_day", "city": "Prague"},
            {"date": "2026-01-06", "day_type": "work_day", "city": "Prague"},
        ]

    def load_content_history(self):
        return [{"date": f"2026-01-{d:02d}", "day_type": "work_day", "city": "Prague"} for d in range(1, 10)]

    def load_scene_memory(self):
        return [{"scene_id": "work_day:morning:airport", "last_used": "2026-01-09", "usage_count": 12}]

    def load_activity_memory(self):
        return [{"activity_id": "work_day:focused", "last_used": "2026-01-09", "usage_count": 11}]

    def load_location_memory(self):
        return [{"location_id": "prague:airport", "last_used": "2026-01-09", "usage_count": 15}]

    def append_narrative_memory(self, row):
        self.narrative_rows.append(row)


def test_life_narrative_engine_detects_recovery_phase():
    state = DummyNarrativeState()
    engine = LifeNarrativeEngine(state)

    context = {"life_state": type("LS", (), {"fatigue_level": 8})()}
    narrative = engine.build_context(date(2026, 1, 10), context)

    assert narrative.narrative_phase == "recovery_phase"
    assert narrative.energy_state == "low"
    assert state.narrative_rows


def test_variation_controller_blocks_repeated_scene_and_activity():
    controller = LifeVariationController()
    assert not controller.scene_allowed(
        "work_day:morning:airport",
        [
            {"scene_id": "work_day:morning:airport", "last_used": "2026-01-09"},
            {"scene_id": "work_day:morning:airport", "last_used": "2026-01-08"},
        ],
    )
    assert not controller.activity_allowed(
        "work_day:focused",
        [{"activity_id": "work_day:focused", "last_used": "2026-01-09"}],
    )
