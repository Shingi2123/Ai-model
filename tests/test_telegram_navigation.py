from datetime import date

from virtual_persona.delivery.telegram_navigation import (
    PlanScreenContext,
    build_plan_keyboard,
    format_caption_screen,
    format_plan_screen,
    format_post_screen,
    format_prompt_screen,
    parse_callback,
)
from virtual_persona.models.domain import PublishingPlanItem


def _item(index: int = 1) -> PublishingPlanItem:
    return PublishingPlanItem(
        publication_id=f"pub-{index}",
        date=date(2026, 3, 12),
        platform="Instagram",
        post_time="09:30",
        content_type="photo",
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        scene_moment="Final room check with luggage ready by the door",
        scene_source="engine",
        scene_moment_type="transition",
        moment_signature="s1",
        visual_focus="door",
        activity_type="packing",
        outfit_ids=["o1"],
        prompt_type="photo",
        prompt_text="A cinematic candid in warm morning light",
        caption_text="Last quiet moments before heading out...",
        short_caption="Last quiet moments before heading out...",
        post_timezone="Europe/Paris",
    )


def test_build_plan_keyboard_uses_dynamic_post_count():
    keyboard = build_plan_keyboard(3)

    assert [row[0][0] for row in keyboard[:3]] == ["POST 1", "POST 2", "POST 3"]
    assert keyboard[-1][0][1] == "plan:today"


def test_parse_callback_for_post_and_detail_views():
    assert parse_callback("p:2").post_index == 2
    assert parse_callback("pv:1:prompt").view == "prompt"
    assert parse_callback("back:post:0").view == "post"
    assert parse_callback("back:plan").view == "plan"


def test_format_plan_and_post_card_contains_core_fields():
    context = PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )

    plan_text = format_plan_screen(context, [_item()])
    post_text = format_post_screen(context, _item(), 0)

    assert "План публикаций" in plan_text
    assert "POST #1 — Instagram / Photo" in plan_text
    assert "Платформа: Instagram" in post_text
    assert "Вы: 13:30 (Asia/Pavlodar)" in post_text


def test_detail_views_have_fallback_for_empty_prompt_and_caption():
    empty = _item()
    empty.prompt_text = ""
    empty.caption_text = ""
    empty.short_caption = ""

    prompt_text = format_prompt_screen(empty, 0)
    caption_text = format_caption_screen(empty, 0)

    assert "нет сохранённого prompt" in prompt_text
    assert "нет сохранённой подписи" in caption_text
