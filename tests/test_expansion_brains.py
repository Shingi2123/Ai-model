from datetime import date

from virtual_persona.models.domain import BehaviorState
from virtual_persona.pipeline.scene_activity_engine import SceneActivityExpansionEngine
from virtual_persona.pipeline.wardrobe_brain import WardrobeBrain


class DummyState:
    def __init__(self):
        self.scene_candidates = []
        self.activity_candidates = []
        self.wardrobe_items = [
            {"item_id": "top_1", "category": "top", "wear_count": 2, "status": "active"},
            {"item_id": "top_2", "category": "top", "wear_count": 2, "status": "active"},
            {"item_id": "top_3", "category": "top", "wear_count": 2, "status": "active"},
            {"item_id": "top_4", "category": "top", "wear_count": 1, "status": "active"},
            {"item_id": "bottom_1", "category": "bottom", "wear_count": 1, "status": "active"},
        ]
        self.shopping_candidates = []
        self.actions = []

    def load_scene_candidates(self):
        return self.scene_candidates

    def append_scene_candidate(self, row):
        self.scene_candidates.append(row)

    def load_activity_candidates(self):
        return self.activity_candidates

    def append_activity_candidate(self, row):
        self.activity_candidates.append(row)

    def load_wardrobe_items(self):
        return self.wardrobe_items

    def save_wardrobe_items(self, rows):
        self.wardrobe_items = rows

    def append_shopping_candidate(self, row):
        self.shopping_candidates.append(row)

    def append_wardrobe_action(self, row):
        self.actions.append(row)

    def load_character_profile(self):
        return {"style_profile": "soft feminine", "favorite_colors": "cream,beige"}


def test_scene_activity_engine_generates_candidates():
    state = DummyState()
    engine = SceneActivityExpansionEngine(state)

    context = {
        "date": date(2026, 1, 18),
        "day_type": "work_day",
        "city": "Prague",
        "life_state": type("LS", (), {"season": "winter", "fatigue_level": 7})(),
    }
    scenes, notes = engine.ensure_candidates(context)

    assert scenes
    assert notes
    assert state.scene_candidates
    assert state.activity_candidates


def test_scene_activity_engine_applies_behavior_to_generated_candidates():
    state = DummyState()
    engine = SceneActivityExpansionEngine(state)

    context = {
        "date": date(2026, 1, 18),
        "day_type": "travel_day",
        "city": "Prague",
        "life_state": type("LS", (), {"season": "winter", "fatigue_level": 6})(),
        "behavioral_context": BehaviorState(
            energy_level="low",
            social_mode="alone",
            emotional_arc="transition",
            habit="packing",
            place_anchor="terminal_gate",
            objects=["carry_on", "bag"],
            self_presentation="transitional",
        ),
    }

    scenes, _ = engine.ensure_candidates(context)

    assert scenes
    assert scenes[0].location == "airport terminal"
    assert "handling luggage" in scenes[0].description
    assert "no people nearby" in scenes[0].description


def test_wardrobe_brain_adds_balance_candidate():
    state = DummyState()
    brain = WardrobeBrain(state)

    context = {
        "date": date(2026, 1, 19),
        "day_type": "day_off",
        "city": "Prague",
        "life_state": type("LS", (), {"season": "winter"})(),
    }

    brain.apply_daily_strategy(context, selected_item_ids=["top_1", "bottom_1"])

    assert any(c["category"] == "bottom" for c in state.shopping_candidates)
