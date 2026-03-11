from datetime import date

from virtual_persona.pipeline.activity_evolution_engine import ActivityEvolutionEngine
from virtual_persona.pipeline.life_diversity_engine import LifeDiversityEngine
from virtual_persona.pipeline.story_arc_engine import StoryArcEngine
from virtual_persona.pipeline.world_expansion_engine import WorldExpansionEngine


class DummyState:
    def __init__(self):
        self.scene_memory = [
            {"scene_id": "day_off:afternoon:city_cafe", "usage_count": 7, "status": "overused"},
            {"scene_id": "day_off:evening:home", "usage_count": 8, "status": "active"},
        ]
        self.activity_memory = [
            {"activity_id": "coffee_pause", "usage_count": 8},
            {"activity_id": "reading_evening", "usage_count": 2},
        ]
        self.location_memory = [{"location_id": "prague:home"}, {"location_id": "prague:home"}]
        self.outfit_memory = [{"item_ids": "a,b"}, {"item_ids": "a,b"}, {"item_ids": "c,d"}]
        self.world_candidates = []
        self.activity_evolution = []
        self.story_arcs = []
        self.activity_candidates = []

    def load_scene_memory(self):
        return self.scene_memory

    def load_activity_memory(self):
        return self.activity_memory

    def load_location_memory(self):
        return self.location_memory

    def load_outfit_memory(self):
        return self.outfit_memory

    def append_world_candidate(self, row):
        self.world_candidates.append(row)

    def append_activity_evolution(self, row):
        self.activity_evolution.append(row)

    def append_activity_candidate(self, row):
        self.activity_candidates.append(row)

    def load_story_arcs(self):
        return self.story_arcs

    def append_story_arc(self, row):
        self.story_arcs.append(row)

    def save_story_arcs(self, rows):
        self.story_arcs = rows


class LS:
    season = "winter"


def test_world_and_activity_expansion_generate_candidates():
    state = DummyState()
    context = {"date": date(2026, 1, 20), "city": "Prague", "day_type": "day_off", "life_state": LS()}

    world = WorldExpansionEngine(state)
    activity = ActivityEvolutionEngine(state)

    wc = world.run(context)
    ac = activity.run(context)

    assert wc
    assert ac
    assert state.world_candidates
    assert state.activity_candidates


def test_story_arc_and_diversity_metrics_work_with_fallbacks():
    state = DummyState()
    context = {"date": date(2026, 1, 21), "day_type": "work_day"}

    arc_engine = StoryArcEngine(state)
    arc = arc_engine.run(context)
    assert arc["status"] == "active"

    diversity = LifeDiversityEngine(state).analyze(lookback_days=7)
    assert 0 <= diversity["scene_diversity"] <= 1
    assert "novelty_boost" in diversity
