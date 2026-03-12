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
    def __init__(self, rules=None, history=None):
        self.rules = rules or []
        self.rows = []
        self.history = history or []
        self.logs = []

    def load_posting_rules(self):
        return self.rules

    def append_publishing_plan(self, row):
        self.rows.append(row)

    def load_content_moment_memory(self):
        return self.history

    def load_publishing_plan(self, target_date=None):
        return []

    def save_run_log(self, status, message):
        self.logs.append((status, message))


def _build_package(day_type: str = "work_day", phase: str = "growth", scenes=None) -> DailyPackage:
    scenes = scenes or [
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
            block="day",
            location="street",
            description="city transfer",
            mood="active",
            time_of_day="day",
            activity="commute",
            scene_moment="arriving at terminal",
            scene_moment_type="transition",
            scene_source="scene_moment_engine",
            moment_signature="terminal-transfer",
            visual_focus="departure board",
        ),
        DayScene(
            block="evening",
            location="river",
            description="golden hour",
            mood="calm",
            time_of_day="evening",
            activity="walk",
            scene_moment="golden hour river walk",
            scene_moment_type="cinematic",
            scene_source="scene_moment_engine",
            moment_signature="river-golden-hour",
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
            photo_prompts=["photo-1", "photo-2", "photo-3"],
            video_prompts=["video-1", "video-2", "video-3"],
            publish_windows=["09:00", "09:00", "09:00"],
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
            narrative_phase=phase,
        ),
    )


def test_publishing_plan_generates_reasonable_count_and_logs():
    state = DummyState()
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase"))

    assert 1 <= len(rows) <= 3
    assert state.rows
    assert any(status == "debug" and "publishing_decision" in msg for status, msg in state.logs)


def test_publishing_plan_avoids_duplicate_times_even_if_windows_repeat():
    state = DummyState()
    engine = PublishingPlanEngine(state)

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase"))

    times = [row.post_time for row in rows]
    assert len(times) == len(set(times))


def test_publishing_plan_can_return_zero_for_low_quality_recovery_day():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    weak_scenes = [
        DayScene(
            block="day",
            location="home",
            description="rest",
            mood="calm",
            time_of_day="day",
            activity="rest",
            scene_moment="quiet room",
            scene_moment_type="transition",
            scene_source="scene_moment_engine",
            moment_signature="quiet-room",
            visual_focus="",
        )
    ]

    rows = engine.generate(_build_package(day_type="day_off", phase="recovery_phase", scenes=weak_scenes))

    assert len(rows) in {0, 1}


def test_publishing_plan_selects_subset_and_drops_duplicates():
    state = DummyState()
    engine = PublishingPlanEngine(state)
    scenes = [
        DayScene("morning", "cafe", "a", "focused", "morning", scene_moment="moment a", scene_moment_type="detail", moment_signature="same", visual_focus="cup"),
        DayScene("day", "cafe", "b", "focused", "day", scene_moment="moment b", scene_moment_type="detail", moment_signature="same", visual_focus="cup"),
        DayScene("evening", "street", "c", "active", "evening", scene_moment="moment c", scene_moment_type="cinematic", moment_signature="unique", visual_focus="lights"),
    ]

    rows = engine.generate(_build_package(day_type="travel_day", phase="transition_phase", scenes=scenes))

    signatures = [row.moment_signature for row in rows]
    assert len(signatures) == len(set(signatures))
