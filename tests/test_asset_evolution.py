from datetime import date, datetime

from virtual_persona.models.domain import DailyPackage, DayScene, GeneratedContent, LifeState, OutfitSelection, SunSnapshot, WeatherSnapshot
from virtual_persona.pipeline.asset_evolution_engine import AssetEvolutionEngine


class DummyState:
    def __init__(self):
        self.wardrobe_items = [
            {
                "item_id": "top_1",
                "name": "Top",
                "category": "top",
                "status": "active",
                "wear_count": 0,
                "times_in_content": 0,
            }
        ]
        self.outfit_memory = []
        self.scene_memory = []
        self.activity_memory = []
        self.location_memory = []
        self.actions = []
        self.candidates = []

    def load_wardrobe_items(self):
        return self.wardrobe_items

    def save_wardrobe_items(self, rows):
        self.wardrobe_items = rows

    def load_outfit_memory(self):
        return self.outfit_memory

    def append_outfit_memory(self, row):
        self.outfit_memory.append(row)

    def append_wardrobe_action(self, row):
        self.actions.append(row)

    def append_shopping_candidate(self, row):
        self.candidates.append(row)

    def load_scene_memory(self):
        return self.scene_memory

    def save_scene_memory(self, rows):
        self.scene_memory = rows

    def load_activity_memory(self):
        return self.activity_memory

    def save_activity_memory(self, rows):
        self.activity_memory = rows

    def load_location_memory(self):
        return self.location_memory

    def save_location_memory(self, rows):
        self.location_memory = rows


def test_asset_evolution_updates_memories():
    state = DummyState()
    engine = AssetEvolutionEngine(state)

    package = DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 1, 10),
        city="Prague",
        day_type="day_off",
        summary="test",
        weather=WeatherSnapshot(city="Prague", temp_c=12, condition="cloudy", humidity=70, wind_speed=3, cloudiness=80),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["top_1"], summary="Top"),
        scenes=[DayScene(block="morning", location="city cafe", description="coffee", mood="calm", time_of_day="morning")],
        content=GeneratedContent(post_caption="c", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
        life_state=LifeState(
            date=date(2026, 1, 10),
            weekday="Saturday",
            month=1,
            season="winter",
            is_holiday=False,
            holiday_name="",
            home_city="Prague",
            current_city="Prague",
            day_type="day_off",
            day_type_reason="rest",
            fatigue_level=2,
            mood_base="calm",
            continuity_note="stable",
        ),
    )

    engine.run(package)

    assert state.wardrobe_items[0]["wear_count"] == 1
    assert len(state.outfit_memory) == 1
    assert len(state.scene_memory) == 1
    assert len(state.activity_memory) == 1
    assert len(state.location_memory) == 1


def test_asset_evolution_adds_balance_candidate_for_bottom_gap():
    state = DummyState()
    state.wardrobe_items = [
        {"item_id": "top_1", "name": "Top1", "category": "top", "status": "active", "wear_count": 1, "times_in_content": 1},
        {"item_id": "top_2", "name": "Top2", "category": "top", "status": "active", "wear_count": 1, "times_in_content": 1},
        {"item_id": "top_3", "name": "Top3", "category": "top", "status": "active", "wear_count": 1, "times_in_content": 1},
        {"item_id": "top_4", "name": "Top4", "category": "top", "status": "active", "wear_count": 1, "times_in_content": 1},
        {"item_id": "bottom_1", "name": "Bottom1", "category": "bottom", "status": "active", "wear_count": 1, "times_in_content": 1},
    ]
    engine = AssetEvolutionEngine(state)

    package = DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 1, 11),
        city="Prague",
        day_type="day_off",
        summary="test",
        weather=WeatherSnapshot(city="Prague", temp_c=12, condition="cloudy", humidity=70, wind_speed=3, cloudiness=80),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["top_1", "bottom_1"], summary="Top + Bottom"),
        scenes=[DayScene(block="morning", location="city cafe", description="coffee", mood="calm", time_of_day="morning")],
        content=GeneratedContent(post_caption="c", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
        life_state=LifeState(
            date=date(2026, 1, 11),
            weekday="Sunday",
            month=1,
            season="winter",
            is_holiday=False,
            holiday_name="",
            home_city="Prague",
            current_city="Prague",
            day_type="day_off",
            day_type_reason="rest",
            fatigue_level=2,
            mood_base="calm",
            continuity_note="stable",
        ),
    )

    engine.run(package)

    assert any(c.get("category") == "bottom" and c.get("reason") == "wardrobe imbalance" for c in state.candidates)
