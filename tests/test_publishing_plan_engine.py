from datetime import date, datetime

from virtual_persona.models.domain import (
    DailyPackage,
    DayScene,
    GeneratedContent,
    LifeState,
    OutfitSelection,
    SunSnapshot,
    WeatherSnapshot,
)
from virtual_persona.pipeline.publishing_plan_engine import PublishingPlanEngine


class DummyState:
    def __init__(self, rules=None):
        self.rules = rules or []
        self.rows = []

    def load_posting_rules(self):
        return self.rules

    def append_publishing_plan(self, row):
        self.rows.append(row)


def _build_package(day_type: str = "work_day") -> DailyPackage:
    scenes = [
        DayScene(
            block="morning",
            location="cafe",
            description="coffee before work",
            mood="focused",
            time_of_day="morning",
            activity="coffee",
            scene_moment="hotel coffee by window",
            scene_moment_type="detail",
            scene_source="scene_moment_engine",
            moment_signature="coffee-window",
            visual_focus="espresso cup",
        ),
        DayScene(
            block="evening",
            location="street",
            description="evening walk",
            mood="calm",
            time_of_day="evening",
            activity="walk",
            scene_moment="neon street walk",
            scene_moment_type="motion",
            scene_source="scene_moment_engine",
            moment_signature="street-neon",
            visual_focus="city lights",
        ),
    ]
    return DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 1, 10),
        city="Prague",
        day_type=day_type,
        summary="day",
        weather=WeatherSnapshot(city="Prague", temp_c=20, condition="clear", humidity=10, wind_speed=1, cloudiness=0),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["look_1", "jeans"], summary="look"),
        scenes=scenes,
        content=GeneratedContent(
            post_caption="caption text",
            story_lines=["story-1", "story-2"],
            photo_prompts=["photo-1", "photo-2"],
            video_prompts=["video-1", "video-2"],
            publish_windows=["09:00", "18:00"],
            creative_notes=[],
        ),
        life_state=LifeState(
            date=date(2026, 1, 10),
            weekday="saturday",
            month=1,
            season="winter",
            is_holiday=False,
            holiday_name="",
            home_city="Prague",
            current_city="Prague",
            day_type=day_type,
            day_type_reason="",
            fatigue_level=2,
            mood_base="good",
            narrative_phase="growth",
        ),
    )


def test_publishing_plan_generates_at_least_one_row():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    package = _build_package()

    rows = engine.generate(package)

    assert len(rows) >= 1
    assert state.rows
    assert rows[0].prompt_text
    assert rows[0].caption_text == "caption text"


def test_publishing_plan_uses_rules_and_supports_two_posts():
    rules = [
        {
            "rule_id": "r1",
            "platform": "Instagram",
            "content_type": "photo",
            "preferred_time": "08:30",
            "enabled": "true",
            "priority": "10",
            "min_per_day": "1",
            "max_per_day": "1",
        },
        {
            "rule_id": "r2",
            "platform": "Instagram",
            "content_type": "video",
            "preferred_time": "18:30",
            "enabled": "true",
            "priority": "9",
            "min_per_day": "1",
            "max_per_day": "1",
            "day_type_filter": "work_day",
        },
    ]
    state = DummyState(rules=rules)
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package("work_day"))

    assert len(rows) == 2
    assert rows[0].content_type == "photo"
    assert rows[1].content_type == "video"
    assert rows[0].moment_signature != rows[1].moment_signature
