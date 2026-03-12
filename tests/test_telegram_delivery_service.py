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
        city="Paris",
        day_type="work_day",
        summary="summary",
        weather=WeatherSnapshot(city="Paris", temp_c=20, condition="clear", humidity=10, wind_speed=1, cloudiness=0),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["look_1"], summary="look"),
        scenes=[],
        content=GeneratedContent(post_caption="caption", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
    )


def _item(post_time: str = "09:30", content_type: str = "photo") -> PublishingPlanItem:
    package = _pkg()
    return PublishingPlanItem(
        publication_id="1",
        date=package.date,
        platform="Instagram",
        post_time=post_time,
        content_type=content_type,
        city=package.city,
        day_type=package.day_type,
        narrative_phase="routine_stability",
        scene_moment="Morning coffee at a small Parisian terrace with warm light and reflections.",
        scene_source="engine",
        scene_moment_type="detail",
        moment_signature="m1",
        visual_focus="focus",
        activity_type="coffee",
        outfit_ids=["look_1"],
        prompt_type=content_type,
        prompt_text="very long detailed prompt text",
        caption_text="caption text",
        short_caption="short caption",
        post_timezone="Europe/Paris",
    )


def test_today_plan_is_compact_and_converts_time_between_timezones():
    package = _pkg()
    text = format_plan_message(package, [_item()], "Europe/Paris", "Asia/Pavlodar")

    assert "Персонаж: 09:30 (Europe/Paris)" in text
    assert "Вы: 13:30 (Asia/Pavlodar)" in text
    assert "very long detailed prompt text" not in text


def test_command_views_for_captions_moments_photo_video():
    package = _pkg()
    items = [_item(content_type="photo"), _item(post_time="18:30", content_type="video")]

    assert "short caption" in format_command_message(package, items, "/captions", "Europe/Paris", "Asia/Pavlodar")
    assert "Parisian terrace" in format_command_message(package, items, "/moments", "Europe/Paris", "Asia/Pavlodar")

    photo_text = format_command_message(package, items, "/photo", "Europe/Paris", "Asia/Pavlodar")
    assert "very long detailed prompt text" in photo_text
    assert "Video" not in photo_text

    video_text = format_command_message(package, items, "/video", "Europe/Paris", "Asia/Pavlodar")
    assert "very long detailed prompt text" in video_text
    assert "Photo" not in video_text


def test_timezone_resolution_uses_cities_sheet_before_default():
    from virtual_persona.config.settings import AppSettings
    from virtual_persona.delivery.telegram_delivery_service import TelegramDeliveryService

    class _State:
        @staticmethod
        def load_cities():
            return [{"city": "Paris", "timezone": "Europe/Paris"}]

    settings = AppSettings(timezone="Europe/Prague", user_timezone="Asia/Pavlodar")
    service = TelegramDeliveryService(settings, _State())

    assert service._resolve_persona_timezone("Paris") == "Europe/Paris"
    assert service._resolve_persona_timezone("Unknown") == "Europe/Prague"
