from datetime import date, datetime

from virtual_persona.delivery.publishing_formatter import format_command_message, format_plan_message
from virtual_persona.models.domain import (
    DailyPackage,
    GeneratedContent,
    OutfitSelection,
    PublishingPlanItem,
    SunSnapshot,
    WeatherSnapshot,
)


def _pkg():
    return DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 1, 10),
        city="Prague",
        day_type="work_day",
        summary="summary",
        weather=WeatherSnapshot(city="Prague", temp_c=20, condition="clear", humidity=10, wind_speed=1, cloudiness=0),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["look_1"], summary="look"),
        scenes=[],
        content=GeneratedContent(post_caption="caption", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
    )


def test_formatter_includes_prompt_and_caption():
    package = _pkg()
    items = [
        PublishingPlanItem(
            publication_id="1",
            date=package.date,
            platform="Instagram",
            post_time="09:30",
            content_type="photo",
            city=package.city,
            day_type=package.day_type,
            narrative_phase="routine_stability",
            scene_moment="moment",
            scene_source="engine",
            scene_moment_type="detail",
            moment_signature="m1",
            visual_focus="focus",
            activity_type="coffee",
            outfit_ids=["look_1"],
            prompt_type="photo",
            prompt_text="prompt text",
            caption_text="caption text",
            short_caption="caption",
        )
    ]

    text = format_plan_message(package, items)

    assert "prompt text" in text
    assert "caption text" in text


def test_command_views_for_captions_and_moments():
    package = _pkg()
    items = [
        PublishingPlanItem(
            publication_id="1",
            date=package.date,
            platform="Instagram",
            post_time="09:30",
            content_type="photo",
            city=package.city,
            day_type=package.day_type,
            narrative_phase="routine_stability",
            scene_moment="moment one",
            scene_source="engine",
            scene_moment_type="detail",
            moment_signature="m1",
            visual_focus="focus",
            activity_type="coffee",
            outfit_ids=["look_1"],
            prompt_type="photo",
            prompt_text="prompt text",
            caption_text="caption text",
            short_caption="short",
        )
    ]
    assert "short" in format_command_message(package, items, "/captions")
    assert "moment one" in format_command_message(package, items, "/moments")
