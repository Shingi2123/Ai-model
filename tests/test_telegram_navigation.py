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
    item_from_row,
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


def test_build_plan_keyboard_uses_russian_utf8_labels():
    items = [_item(1), _item(2)]
    keyboard = build_plan_keyboard(items, date(2026, 3, 12))

    assert [row[0][0] for row in keyboard[:2]] == ["📸 Пост 1", "📸 Пост 2"]
    assert keyboard[0][0][1] == "p:2026-03-12:pub-1"
    assert keyboard[-1][0] == ("🔄 Обновить", "plan:2026-03-12")


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

    assert "📅 План публикаций" in plan_text
    assert "📍 Город персонажа: Paris" in plan_text
    assert "📸 POST #1" in plan_text
    assert "🌐 Платформа: Instagram • Photo" in plan_text
    assert "🌐 Платформа: Instagram" in post_text
    assert "🕒 Вы: 13:30 (Asia/Pavlodar)" in post_text


def test_detail_views_have_fallback_for_empty_prompt_and_caption():
    empty = _item()
    empty.prompt_text = ""
    empty.caption_text = ""
    empty.short_caption = ""
    empty.negative_prompt = ""

    prompt_text = format_prompt_screen(empty, 0)
    caption_text = format_caption_screen(empty, 0)

    assert "Нет сохранённого prompt" in prompt_text
    assert "No negative prompt" in prompt_text
    assert "пока нет сохранённой подписи" in caption_text


def test_prompt_screen_falls_back_to_final_prompt_from_prompt_package_json():
    item = _item()
    item.prompt_text = ""
    item.prompt_package_json = '{"final_prompt":"A realistic candid friend-shot walking through the terminal."}'

    prompt_text = format_prompt_screen(item, 0)

    assert "A realistic candid friend-shot walking through the terminal." in prompt_text
    assert "Нет сохранённого prompt" not in prompt_text


def test_prompt_screen_uses_new_workflow_order_and_aliases():
    text = format_prompt_screen(_item(), 0)

    sections = [
        "📌 POST #1 — Instagram / Photo",
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


def test_plan_screen_hides_unknown_city_and_keeps_russian_meta():
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
    assert "Таймзона персонажа: Europe/Prague" in text
    assert "Таймзона пользователя: Asia/Pavlodar" in text
    assert "День: work_day" in text
    assert "Фаза: routine_stability" in text


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
    assert detail_keyboard[0][1][0] == "⬅️ К плану"
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
    assert items[0].caption_text == "Last quiet moments before heading out..."
    assert items[0].generation_mode == "mirror_selfie_mode"
    assert items[0].framing_mode == "mirror selfie, head-and-shoulders"
    assert items[0].reference_type == "selfie"


def test_item_from_row_recovers_detail_fields_from_canonical_snapshot_keys():
    row = {
        "publication_id": "pub-1",
        "date": "2026-03-12",
        "platform": "Instagram",
        "post_time": "09:30",
        "content_type": "photo",
        "city": "Paris",
        "day_type": "work_day",
        "narrative_phase": "recovery_phase",
        "scene_moment": "Final room check with luggage ready by the door",
        "prompt_text": "Prompt body",
        "caption": "Canonical caption",
        "short_caption": "Short canonical caption",
        "prompt_package_json": (
            '{"shot_archetype":"mirror_selfie","framing_mode":"mirror selfie, head-and-shoulders",'
            '"generation_mode":"mirror_selfie_mode","reference_type":"selfie","identity_mode":"reference_manifest",'
            '"primary_anchors":"refs/selfies/, refs/base/","secondary_anchors":"refs/identity_lock/"}'
        ),
    }

    item = item_from_row(row, date(2026, 3, 12))

    assert item.caption_text == "Canonical caption"
    assert item.short_caption == "Short canonical caption"
    assert item.shot_archetype == "mirror_selfie"
    assert item.framing_mode == "mirror selfie, head-and-shoulders"
    assert item.generation_mode == "mirror_selfie_mode"
    assert item.reference_type == "selfie"
    assert item.identity_mode == "reference_manifest"
    assert item.primary_anchors == "refs/selfies/, refs/base/"
    assert item.secondary_anchors == "refs/identity_lock/"


def test_item_from_row_filters_debug_strings_and_uses_prompt_meta_fallbacks():
    row = {
        "publication_id": "pub-1",
        "date": "2026-03-12",
        "platform": "Instagram",
        "post_time": "09:30",
        "content_type": "photo",
        "caption_text": "mirror_selfie_mode",
        "short_caption": "friend-shot, 3/4 body",
        "reference_type": "selected_by_primary_decision_and_diversity",
        "generation_mode": "score=3.60; reasons=visual_focus",
        "identity_mode": 36,
        "prompt_package_json": (
            '{"caption_text":"Real caption","short_caption":"Real short caption",'
            '"reference_type":"selfie","generation_mode":"mirror_selfie_mode","identity_mode":"reference_manifest"}'
        ),
    }

    item = item_from_row(row, date(2026, 3, 12))

    assert item.caption_text == "Real caption"
    assert item.short_caption == "Real short caption"
    assert item.reference_type == "selfie"
    assert item.generation_mode == "mirror_selfie_mode"
    assert item.identity_mode == "reference_manifest"


def test_prompt_screen_uses_only_canonical_detail_fields_not_debug_strings():
    item = _item()
    item.caption_text = "Real caption"
    item.short_caption = "Real short caption"
    item.reference_type = "selfie"
    item.generation_mode = "mirror_selfie_mode"
    item.identity_mode = "reference_manifest"
    item.framing_mode = "mirror selfie, head-and-shoulders"
    item.notes = "score=9.5; explanation text that must not replace generation mode"
    item.selection_reason = "selected_by_primary_decision_and_diversity"
    item.generation_diagnostics = "debug-string"

    text = format_prompt_screen(item, 0)

    assert "Real caption" in text
    assert "Real short caption" in text
    assert "selfie" in text
    assert "mirror_selfie_mode" in text
    assert "reference_manifest" in text
    assert "mirror selfie, head-and-shoulders" in text
    assert "debug-string" not in text
    assert "score=9.5" not in text


def test_item_from_row_replaces_legacy_prompt_with_canonical_final_prompt():
    row = {
        "publication_id": "pub-legacy",
        "date": "2026-03-12",
        "platform": "Instagram",
        "post_time": "09:30",
        "content_type": "photo",
        "scene_moment": "Walking through the airport terminal before boarding",
        "prompt_text": "Half-body and 3/4 body framing from waist-up, no plastic skin, rounded personal smartphone in hand",
        "prompt_package_json": (
            '{"final_prompt":"A realistic candid airport walk.\\n\\n3/4 body walking shot.\\n\\n'
            'Off-duty crew member between flights in a casual travel look.",'
            '"prompt_format_version":"v5"}'
        ),
    }

    item = item_from_row(row, date(2026, 3, 12))

    assert "Half-body" not in item.prompt_text
    assert "3/4 body walking shot" in item.prompt_text


def test_prompt_screen_does_not_render_legacy_prompt_when_canonical_prompt_exists():
    item = _item()
    item.scene_moment = "Walking through the airport terminal before boarding"
    item.prompt_text = "Half-body and 3/4 body framing from waist-up, no plastic skin"
    item.prompt_package_json = (
        '{"final_prompt":"A realistic candid airport walk.\\n\\n3/4 body walking shot.\\n\\n'
        'Off-duty crew member between flights in a casual travel look.",'
        '"prompt_format_version":"v5"}'
    )

    text = format_prompt_screen(item, 0)

    assert "Half-body and 3/4 body framing from waist-up" not in text
    assert "no plastic skin" not in text
    assert "3/4 body walking shot" in text
