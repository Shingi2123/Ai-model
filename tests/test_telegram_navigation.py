from datetime import date

from virtual_persona.delivery.telegram_navigation import (
    PlanScreenContext,
    build_detail_keyboard,
    build_plan_keyboard,
    build_post_keyboard,
    deserialize_context,
    format_caption_screen,
    format_plan_screen,
    format_post_screen,
    format_prompt_screen,
    normalize_plan_items,
    parse_callback,
    serialize_context,
)
from virtual_persona.models.domain import PublishingPlanItem


def _item(index: int = 1, publication_id: str | None = None) -> PublishingPlanItem:
    return PublishingPlanItem(
        publication_id=publication_id if publication_id is not None else f"pub-{index}",
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
        negative_prompt="extra fingers, plastic skin",
        shot_archetype="mirror_selfie",
        platform_intent="instagram_feed",
        generation_mode="mirror_selfie_mode",
        framing_mode="mirror selfie, head-and-shoulders",
        prompt_mode="compact",
        identity_mode="reference_manifest",
        reference_type="selfie",
        reference_pack_type="identity_lock",
        primary_anchors="refs/selfies/, refs/base/",
        secondary_anchors="refs/identity_lock/",
        manual_generation_step="Attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting.",
        caption_text="Last quiet moments before heading out...",
        short_caption="Last quiet moments before heading out...",
        post_timezone="Europe/Paris",
    )


def test_build_plan_keyboard_uses_publication_id_callback():
    items = [_item(1), _item(2)]
    keyboard = build_plan_keyboard(items, date(2026, 3, 12))

    assert [row[0][0] for row in keyboard[:2]] == ["📌 Пост 1", "📌 Пост 2"]
    assert keyboard[0][0][1] == "p:2026-03-12:pub-1"
    assert keyboard[-1][0][1] == "plan:2026-03-12"


def test_parse_callback_for_post_and_detail_views():
    parsed_post = parse_callback("p:2026-03-12:pub-2")
    parsed_detail = parse_callback("pv:2026-03-12:pub-1:prompt")
    parsed_back = parse_callback("back:post:2026-03-12:pub-1")

    assert parsed_post.view == "post"
    assert parsed_post.publication_id == "pub-2"
    assert parsed_detail.view == "prompt"
    assert parsed_detail.target_date == "2026-03-12"
    assert parsed_back.view == "post"
    assert parsed_back.publication_id == "pub-1"


def test_parse_callback_back_compat():
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

    assert "📅 Plan -" in plan_text
    assert "📌 POST #1" in plan_text
    assert "- Instagram / Photo" in plan_text
    assert "Platform: Instagram" in post_text
    assert "Your time: 13:30 (Asia/Pavlodar)" in post_text


def test_detail_views_have_fallback_for_empty_prompt_and_caption():
    empty = _item()
    empty.prompt_text = ""
    empty.caption_text = ""
    empty.short_caption = ""
    empty.negative_prompt = ""

    prompt_text = format_prompt_screen(empty, 0)
    caption_text = format_caption_screen(empty, 0)

    assert "Нет сохраненного prompt" in prompt_text
    assert "No negative prompt" in prompt_text
    assert "No saved caption" in caption_text


def test_prompt_screen_uses_new_workflow_order_and_aliases():
    text = format_prompt_screen(_item(), 0)

    sections = [
        "📌 POST #1 - Instagram / Photo",
        "🎯 Генерация",
        "🧠 Референсы",
        "🖼 Prompt",
        "🚫 Negative prompt",
        "✍️ Подпись",
        "📝 Короткая подпись",
        "⚙️ Дополнительно",
    ]

    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)
    assert "- Тип кадра: mirror_selfie" in text
    assert "- Фрейминг: mirror selfie, head-and-shoulders" in text
    assert "- Тип референсов: selfie" in text
    assert "- Режим генерации: mirror_selfie_mode" in text
    assert "- Основные: selfies, base" in text
    assert "- Дополнительные: identity_lock" in text
    assert "refs/selfies/" not in text
    assert "platform=Instagram" not in text
    assert "- Платформа: Instagram" in text
    assert "- Prompt mode: compact" in text
    assert "- Identity mode: reference_manifest" in text


def test_plan_screen_with_zero_posts_and_keyboard_refresh_only():
    context = PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )

    plan_text = format_plan_screen(context, [])
    keyboard = build_plan_keyboard([], date(2026, 3, 12))

    assert "Пока нет запланированных постов" in plan_text
    assert keyboard == [[("🔄 Обновить", "plan:2026-03-12")]]


def test_plan_screen_with_single_post_shows_post_card_not_empty_state():
    context = PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )

    plan_text = format_plan_screen(context, [_item()])
    keyboard = build_plan_keyboard([_item()], date(2026, 3, 12))

    assert "📌 POST #1" in plan_text
    assert "Пока нет запланированных постов" not in plan_text
    assert keyboard[0][0][0] == "📌 Пост 1"


def test_plan_screen_hides_unknown_city_and_keeps_compact_meta():
    context = PlanScreenContext(
        target_date=date(2026, 3, 19),
        city="Unknown",
        day_type="work_day",
        narrative_phase="routine_stability",
        persona_timezone="Europe/Prague",
        user_timezone="Asia/Pavlodar",
    )

    text = format_plan_screen(context, [])

    assert "Unknown" not in text
    assert "🕒 Europe/Prague -> Asia/Pavlodar" in text
    assert "🧭 work_day • routine_stability" in text


def test_normalize_plan_items_deduplicates_same_publication_id():
    duplicate_a = _item(1, publication_id="pub-1")
    duplicate_b = _item(1, publication_id="pub-1")

    normalized = normalize_plan_items([duplicate_a, duplicate_b])

    assert len(normalized) == 1
    assert normalized[0].publication_id == "pub-1"


def test_normalize_plan_items_stable_fallback_key_when_publication_id_missing():
    first = _item(1, publication_id="")
    second = _item(1, publication_id="")

    normalized = normalize_plan_items([first, second])

    assert len(normalized) == 1
    assert normalized[0].publication_id.startswith("2026-03-12|Instagram|photo")


def test_post_and_detail_keyboards_keep_same_post_identity():
    post_keyboard = build_post_keyboard(date(2026, 3, 12), "pub-1")
    detail_keyboard = build_detail_keyboard(date(2026, 3, 12), "pub-1")

    assert post_keyboard[0][0][0] == "🖼 Prompt"
    assert post_keyboard[0][1][0] == "✍️ Подпись"
    assert post_keyboard[1][0][0] == "🎯 Момент"
    assert post_keyboard[2][0][0] == "⬅️ К плану"
    assert detail_keyboard[0][0][0] == "⬅️ К посту"
    assert detail_keyboard[0][1][0] == "📅 К плану"
    assert post_keyboard[0][0][1] == "pv:2026-03-12:pub-1:prompt"
    assert post_keyboard[2][0][1] == "back:plan:2026-03-12"
    assert detail_keyboard[0][0][1] == "back:post:2026-03-12:pub-1"


def test_prompt_screen_is_copy_ready_and_does_not_leak_prompt_package_json():
    item = _item()
    item.prompt_package_json = '{"internal":"must_not_render"}'

    text = format_prompt_screen(item, 0)

    assert text.count("```") == 8
    assert "prompt_package_json" not in text
    assert "must_not_render" not in text


def test_serialize_context_preserves_detail_screen_metadata():
    context = PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )
    item = _item()

    raw = serialize_context(context, [item])
    _, items = deserialize_context(raw)

    assert items[0].identity_mode == "reference_manifest"
    assert items[0].reference_pack_type == "identity_lock"
