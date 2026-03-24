from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from virtual_persona.delivery.publishing_formatter import _convert_time_for_user, _post_header_emoji
from virtual_persona.delivery.publishing_plan_normalizer import (
    format_reference_aliases,
    item_from_payload,
    load_prompt_meta,
    resolve_canonical_prompt,
    resolve_prompt_mode,
    resolve_prompt_style_version,
)
from virtual_persona.models.domain import PublishingPlanItem
from virtual_persona.pipeline.prompt_composer import PromptComposer


logger = logging.getLogger(__name__)
SUMMARY_DIVIDER = "----------------"

UI_TRANSLATIONS = {
    "Prompt": "🖼 Промпт",
    "Caption": "✍️ Подпись",
    "Short caption": "Короткая подпись",
    "Moment": "🎯 Момент",
    "Back to plan": "⬅️ К плану",
    "Back to post": "⬅️ К посту",
    "Refresh": "🔄 Обновить",
    "Generation": "🎯 Генерация",
    "References": "🧷 Референсы",
    "Shot type": "Тип кадра",
    "Framing": "Фрейминг",
    "Reference type": "Тип референсов",
    "Generation mode": "Режим генерации",
    "Primary": "Основные",
    "Secondary": "Дополнительные",
    "How to use": "Как использовать",
    "Behavior": "🧠 Поведение",
    "Energy": "Энергия",
    "Social": "Социальность",
    "Emotional arc": "🎭 Эмоциональная фаза",
    "Habit": "🔁 Привычка",
    "Place": "📍 Место",
    "Objects": "🎒 Объекты",
    "Self": "👤 Подача",
    "Extra": "⚙️ Дополнительно",
    "Platform": "Платформа",
    "Prompt mode": "Режим промпта",
    "Identity mode": "Режим идентичности",
    "City": "📍 Город",
    "Persona TZ": "🕒 Часовой пояс персонажа",
    "User TZ": "🕒 Ваш часовой пояс",
    "Day type": "📆 Тип дня",
    "Phase": "📊 Фаза",
    "Format": "Формат",
    "Persona": "🕒 Персонаж",
    "You": "🕒 Вы",
}

CONTENT_TYPE_TRANSLATIONS = {
    "photo": "Фото",
    "carousel": "Карусель",
    "video": "Видео",
    "reel": "Рилс",
    "stories": "Сторис",
    "story": "Сторис",
    "text": "Текст",
}

RU_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


@dataclass
class PlanScreenContext:
    target_date: date
    city: str
    day_type: str
    narrative_phase: str
    persona_timezone: str
    user_timezone: str


@dataclass
class ParsedCallback:
    view: str
    target_date: str | None = None
    publication_id: str | None = None
    post_index: int | None = None


def ui_label(key: str) -> str:
    return UI_TRANSLATIONS.get(key, key)


def short_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _is_missing_value(value: str | None) -> bool:
    normalized = (value or "").strip()
    return not normalized or normalized.lower() == "unknown"


def _format_ru_date(value: date) -> str:
    return f"{value.day} {RU_MONTHS_GENITIVE[value.month]}"


def _content_type_label(content_type: str | None) -> str:
    normalized = (content_type or "").strip().lower()
    return CONTENT_TYPE_TRANSLATIONS.get(normalized, (content_type or "Пост").strip() or "Пост")


def _display_value(value: str | None, fallback: str) -> str:
    return (value or "").strip() or fallback


def _format_ui_field(label: str, value: str) -> str:
    return f"- {ui_label(label)}: {value}"


def _format_compact_meta(context: PlanScreenContext) -> list[str]:
    lines: list[str] = []
    if not _is_missing_value(context.city):
        lines.append(f"{ui_label('City')}: {context.city}")
    lines.append(f"{ui_label('Persona TZ')}: {context.persona_timezone}")
    lines.append(f"{ui_label('User TZ')}: {context.user_timezone}")
    lines.append("")
    lines.append(f"{ui_label('Day type')}: {context.day_type}")
    lines.append(f"{ui_label('Phase')}: {context.narrative_phase}")
    return lines


def _parse_behavior_state(value: str | None) -> dict[str, str]:
    parsed = {"energy": "", "social": "", "arc": "", "habit": "", "place": "", "objects": "", "self": ""}
    for chunk in str(value or "").split(";"):
        if "=" not in chunk:
            continue
        key, raw = chunk.split("=", 1)
        normalized = key.strip().lower()
        if normalized in parsed:
            parsed[normalized] = raw.strip()
    return parsed


def _post_title(item: PublishingPlanItem, post_index: int) -> str:
    emoji = _post_header_emoji(item.content_type)
    return f"{emoji} ПОСТ #{post_index + 1} — {item.platform} / {_content_type_label(item.content_type)}"


def _detail_post_title(item: PublishingPlanItem, post_index: int) -> str:
    return f"ПОСТ #{post_index + 1}"


def _format_generation_block(item: PublishingPlanItem) -> str:
    shot_archetype = _display_value(item.shot_archetype, "Не задано")
    framing_mode = _display_value(item.framing_mode, "Не задано")
    reference_type = _display_value(item.reference_type or item.reference_pack_type, "Не задано")
    generation_mode = _display_value(item.generation_mode, "Не задано")
    return "\n".join(
        [
            ui_label("Generation"),
            _format_ui_field("Shot type", shot_archetype),
            _format_ui_field("Framing", framing_mode),
            _format_ui_field("Reference type", reference_type),
            _format_ui_field("Generation mode", generation_mode),
        ]
    )


def _format_manual_generation_step(step: str | None) -> str:
    text = (step or "").strip()
    if not text:
        return "Прикрепите 2-3 основных референса. Добавьте 1 дополнительный только если генерация начинает плыть."
    lowered = " ".join(text.lower().split())
    known_translations = {
        "attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting.": "Прикрепите 2-3 основных референса. Добавьте 1 дополнительный, только если генерация начинает плыть.",
        "use the primary anchors first. add secondary anchors only if you need to reinforce angle, emotion, or body consistency.": "Сначала используйте основные референсы. Дополнительные подключайте только если нужно усилить ракурс, эмоцию или консистентность тела.",
        "attach the primary anchors listed below for generation.": "Прикрепите перечисленные ниже основные референсы.",
        "attach 2-3 primary anchors, add 1 secondary anchor only if needed.": "Прикрепите 2-3 основных референса. Добавьте 1 дополнительный только при необходимости.",
    }
    return known_translations.get(lowered, text)


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header_lines = [f"📅 План на {_format_ru_date(context.target_date)}"]
    header_lines.extend(_format_compact_meta(context))
    header = "\n".join(header_lines)
    if not items:
        return f"{header}\n\nВ этот день пока нет запланированных постов."
    rows = []
    for idx, item in enumerate(items, start=1):
        source_tz = item.post_timezone or context.persona_timezone
        user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
        rows.append(
            "\n".join(
                [
                    SUMMARY_DIVIDER,
                    "",
                    f"{_post_header_emoji(item.content_type)} ПОСТ #{idx}",
                    f"{ui_label('Persona')}: {item.post_time} ({source_tz})",
                    f"{ui_label('You')}: {user_time} ({context.user_timezone})",
                    f"{ui_label('Platform')}: {item.platform} • {_content_type_label(item.content_type)}",
                    f"{ui_label('Moment')}: {short_text(item.scene_moment, 110)}",
                    f"{ui_label('Caption')}: {short_text(item.short_caption or item.caption_text, 140)}",
                ]
            )
        )
    return f"{header}\n\n" + "\n\n".join(rows)


def format_post_screen(context: PlanScreenContext, item: PublishingPlanItem, post_index: int) -> str:
    source_tz = item.post_timezone or context.persona_timezone
    user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
    behavior = _parse_behavior_state(item.behavior_state)
    energy = behavior["energy"] or "medium"
    social = behavior["social"] or item.social_presence_mode or "alone"
    emotional_arc = behavior["arc"] or item.emotional_arc or "routine"
    habit = behavior["habit"] or item.habit or item.habit_used or "none"
    place = behavior["place"] or item.place_anchor or item.familiar_place_anchor or "kitchen_corner"
    objects = behavior["objects"] or item.objects or item.recurring_objects_in_scene or "none"
    self_presentation = behavior["self"] or item.self_presentation or item.self_presentation_mode or "relaxed"

    behavior_block = "\n".join(
        [
            f"{ui_label('Behavior')}:",
            f"{ui_label('Energy')}: {energy}",
            f"{ui_label('Social')}: {social}",
        ]
    )

    return "\n".join(
        [
            _post_title(item, post_index),
            "",
            f"{ui_label('Persona')}: {item.post_time} ({source_tz})",
            f"{ui_label('You')}: {user_time} ({context.user_timezone})",
            "",
            f"{ui_label('Moment')}: {short_text(item.scene_moment, 220)}",
            f"{ui_label('Caption')}: {short_text(item.short_caption or item.caption_text, 220)}",
            "",
            _format_generation_block(item),
            "",
            behavior_block,
            "",
            f"{ui_label('Emotional arc')}:",
            emotional_arc,
            "",
            f"{ui_label('Habit')}:",
            habit,
            "",
            f"{ui_label('Place')}:",
            place,
            "",
            f"{ui_label('Objects')}:",
            short_text(objects, 80),
            "",
            f"{ui_label('Self')}:",
            self_presentation,
        ]
    )


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt_value, prompt_source, legacy_detected, prompt_style_version = resolve_canonical_prompt(item)
    prompt = (prompt_value or "").strip()
    if not prompt:
        prompt = str(item.prompt_text or "").strip()
        if prompt:
            prompt_source = "prompt_text"
    if not prompt:
        prompt_meta = load_prompt_meta(item)
        prompt = str(prompt_meta.get("final_prompt") or "").strip()
        if prompt:
            prompt_source = "prompt_package_json.final_prompt_fallback"
            prompt_style_version = resolve_prompt_style_version(item, prompt_meta=prompt_meta)
    prompt = _display_value(prompt, "Промпт для этого поста не сохранён.")
    caption = _display_value(item.caption_text, "Подпись не сохранена.")
    short_caption = _display_value(item.short_caption or item.caption_text, "Короткая подпись не сохранена.")
    negative = _display_value(item.negative_prompt, "Негативный промпт не сохранён.")
    prompt_mode = _display_value(item.prompt_mode, "Не задано")
    identity_mode = _display_value(item.identity_mode, "Не задано")
    primary_anchors = _display_value(format_reference_aliases(item.primary_anchors), "Нет основных референсов")
    secondary_anchors = _display_value(format_reference_aliases(item.secondary_anchors), "Нет дополнительных референсов")
    manual_generation_step = _format_manual_generation_step(item.manual_generation_step)
    prompt_mode = _display_value(resolve_prompt_mode(item, resolved_prompt=prompt), prompt_mode)
    prompt_style_version = prompt_style_version or item.prompt_style_version or ""
    prompt_style_diagnostics = PromptComposer.prompt_style_diagnostics(
        prompt,
        prompt_style_version=prompt_style_version,
    )

    logger.info(
        "telegram_detail_render publication_id=%s prompt_source=%s prompt_style_version=%s legacy_prompt_detected=%s telegram_prompt_text=%r",
        item.publication_id,
        prompt_source,
        prompt_style_version or "unknown",
        "yes" if legacy_detected else "no",
        prompt,
    )
    if prompt_style_diagnostics.get("has_legacy_content"):
        logger.warning(
            "legacy_style_prompt_detected_in_ui publication_id=%s prompt_style_version=%s signatures=%s telegram_prompt_text=%r",
            item.publication_id,
            prompt_style_version or "unknown",
            ", ".join(prompt_style_diagnostics.get("legacy_signatures", []) or []) or "-",
            prompt,
        )
    if prompt_style_version and prompt_style_version != PromptComposer.expected_prompt_style_version():
        logger.warning(
            "telegram_prompt_style_version_warning publication_id=%s prompt_style_version=%s expected=%s",
            item.publication_id,
            prompt_style_version,
            PromptComposer.expected_prompt_style_version(),
        )

    references_block = "\n".join(
        [
            ui_label("References"),
            _format_ui_field("Primary", primary_anchors),
            _format_ui_field("Secondary", secondary_anchors),
            _format_ui_field("How to use", manual_generation_step),
        ]
    )
    extra_block = "\n".join(
        [
            f"{ui_label('Extra')}:",
            _format_ui_field("Platform", item.platform),
            _format_ui_field("Prompt mode", prompt_mode),
            _format_ui_field("Identity mode", identity_mode),
        ]
    )

    return (
        f"{ui_label('Prompt')} для {_detail_post_title(item, post_index)}\n\n"
        f"{_post_title(item, post_index)}\n\n"
        f"{_format_generation_block(item)}\n\n"
        f"{references_block}\n\n"
        f"{ui_label('Prompt')}\n```\n"
        f"{prompt}\n"
        "```\n\n"
        "Негативный промпт\n```\n"
        f"{negative}\n"
        "```\n\n"
        f"{ui_label('Caption')}\n```\n"
        f"{caption}\n"
        "```\n\n"
        f"{ui_label('Short caption')}\n```\n"
        f"{short_caption}\n"
        f"```\n\n{extra_block}"
    )


def format_caption_screen(item: PublishingPlanItem, post_index: int) -> str:
    caption = (item.caption_text or item.short_caption or "").strip()
    body = caption if caption else "Сохранённой подписи для этого поста пока нет."
    return f"{_post_title(item, post_index)}\n\n{ui_label('Caption')}:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "Сохранённого момента для этого поста пока нет."
    return f"{_post_title(item, post_index)}\n\n{ui_label('Moment')}:\n{body}"


def plan_item_key(item: PublishingPlanItem) -> str:
    if item.publication_id:
        return f"publication_id:{item.publication_id}"
    return "|".join([item.date.isoformat(), item.platform, item.content_type, item.scene_moment, item.post_time])


def normalize_plan_items(items: list[PublishingPlanItem]) -> list[PublishingPlanItem]:
    ordered = sorted(items, key=lambda item: (item.post_time, item.platform, item.content_type, item.publication_id or "", item.scene_moment))
    unique: list[PublishingPlanItem] = []
    seen: set[str] = set()
    for item in ordered:
        key = plan_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        if not item.publication_id:
            item.publication_id = key
        unique.append(item)
    return unique


def build_plan_keyboard(items: list[PublishingPlanItem], target_date: date) -> list[list[tuple[str, str]]]:
    rows = []
    day = target_date.isoformat()
    for idx, item in enumerate(items):
        rows.append([(f"Пост {idx + 1}", f"p:{day}:{item.publication_id}")])
    rows.append([(ui_label("Refresh"), f"plan:{day}")])
    return rows


def build_post_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [
        [(ui_label("Prompt"), f"pv:{day}:{publication_id}:prompt"), (ui_label("Caption"), f"pv:{day}:{publication_id}:caption")],
        [(ui_label("Moment"), f"pv:{day}:{publication_id}:moment")],
        [(ui_label("Back to plan"), f"back:plan:{day}")],
    ]


def build_detail_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [[(ui_label("Back to post"), f"back:post:{day}:{publication_id}"), (ui_label("Back to plan"), f"back:plan:{day}")]]


def parse_callback(data: str) -> ParsedCallback:
    if data == "plan:today" or data == "back:plan":
        return ParsedCallback(view="plan")
    if data.startswith("plan:"):
        return ParsedCallback(view="plan", target_date=data.split(":", 1)[1])
    if data.startswith("p:"):
        _, raw = data.split(":", 1)
        parts = raw.split(":")
        if len(parts) == 1:
            return ParsedCallback(view="post", post_index=int(parts[0]))
        return ParsedCallback(view="post", target_date=parts[0], publication_id=parts[1])
    if data.startswith("back:post:"):
        parts = data.split(":")
        if len(parts) == 3:
            return ParsedCallback(view="post", post_index=int(parts[-1]))
        return ParsedCallback(view="post", target_date=parts[2], publication_id=parts[3])
    if data.startswith("back:plan:"):
        return ParsedCallback(view="plan", target_date=data.split(":", 2)[2])
    if data.startswith("pv:"):
        parts = data.split(":")
        if len(parts) == 3:
            _, post_index, view_name = parts
            return ParsedCallback(view=view_name, post_index=int(post_index))
        _, target_date, publication_id, view_name = parts
        return ParsedCallback(view=view_name, target_date=target_date, publication_id=publication_id)
    raise ValueError(f"Unknown callback data: {data}")


def serialize_context(context: PlanScreenContext, items: list[PublishingPlanItem]) -> dict:
    return {
        "target_date": context.target_date.isoformat(),
        "city": context.city,
        "day_type": context.day_type,
        "narrative_phase": context.narrative_phase,
        "persona_timezone": context.persona_timezone,
        "user_timezone": context.user_timezone,
        "items": [
            {
                "publication_id": item.publication_id,
                "date": item.date.isoformat(),
                "platform": item.platform,
                "post_time": item.post_time,
                "content_type": item.content_type,
                "city": item.city,
                "day_type": item.day_type,
                "narrative_phase": item.narrative_phase,
                "scene_moment": item.scene_moment,
                "scene_source": item.scene_source,
                "scene_moment_type": item.scene_moment_type,
                "moment_signature": item.moment_signature,
                "visual_focus": item.visual_focus,
                "activity_type": item.activity_type,
                "outfit_ids": item.outfit_ids,
                "outfit_sentence": item.outfit_sentence,
                "outfit_struct_json": item.outfit_struct_json,
                "outfit_summary": item.outfit_summary,
                "prompt_type": item.prompt_type,
                "prompt_text": item.prompt_text,
                "prompt_style_version": item.prompt_style_version,
                "negative_prompt": item.negative_prompt,
                "prompt_package_json": item.prompt_package_json,
                "shot_archetype": item.shot_archetype,
                "platform_intent": item.platform_intent,
                "generation_mode": item.generation_mode,
                "framing_mode": item.framing_mode,
                "prompt_mode": item.prompt_mode,
                "identity_mode": item.identity_mode,
                "reference_type": item.reference_type,
                "reference_pack_type": item.reference_pack_type,
                "primary_anchors": item.primary_anchors,
                "secondary_anchors": item.secondary_anchors,
                "manual_generation_step": item.manual_generation_step,
                "caption": item.caption_text,
                "caption_text": item.caption_text,
                "short_caption": item.short_caption,
                "post_timezone": item.post_timezone,
                "delivery_status": item.delivery_status,
                "emotional_arc": item.emotional_arc,
                "habit_used": item.habit_used,
                "habit_family": item.habit_family,
                "recurring_habit_summary": item.recurring_habit_summary,
                "familiar_place_anchor": item.familiar_place_anchor,
                "familiar_place_label": item.familiar_place_label,
                "familiar_place_family": item.familiar_place_family,
                "familiarity_score": item.familiarity_score,
                "recurring_objects_in_scene": item.recurring_objects_in_scene,
                "object_presence_mode": item.object_presence_mode,
                "self_presentation_mode": item.self_presentation_mode,
                "social_presence_mode": item.social_presence_mode,
                "transition_hint_used": item.transition_hint_used,
                "transition_context": item.transition_context,
                "caption_voice_mode": item.caption_voice_mode,
                "action_family": item.action_family,
                "emotional_tone_family": item.emotional_tone_family,
                "social_context_hint": item.social_context_hint,
                "social_presence_detail": item.social_presence_detail,
                "caption_voice_constraints": item.caption_voice_constraints,
                "day_behavior_summary": item.day_behavior_summary,
            }
            for item in items
        ],
    }


def deserialize_context(raw: dict) -> tuple[PlanScreenContext, list[PublishingPlanItem]]:
    context = PlanScreenContext(
        target_date=date.fromisoformat(raw["target_date"]),
        city=raw["city"],
        day_type=raw["day_type"],
        narrative_phase=raw["narrative_phase"],
        persona_timezone=raw["persona_timezone"],
        user_timezone=raw["user_timezone"],
    )
    items = [
        item_from_payload(
            row,
            context.target_date,
            default_city=context.city,
            default_day_type=context.day_type,
            default_narrative_phase=context.narrative_phase,
        )
        for row in raw.get("items", [])
    ]
    return context, items


def item_from_row(row: dict, fallback_date: date) -> PublishingPlanItem:
    return item_from_payload(row, fallback_date)
