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
)
from virtual_persona.models.domain import PublishingPlanItem


logger = logging.getLogger(__name__)
SUMMARY_DIVIDER = "────────────────"


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


def short_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _is_missing_value(value: str | None) -> bool:
    normalized = (value or "").strip()
    return not normalized or normalized.lower() == "unknown"


def _format_compact_meta(context: PlanScreenContext) -> list[str]:
    lines: list[str] = []
    if not _is_missing_value(context.city):
        lines.append(f"📍 Город персонажа: {context.city}")
    lines.append(f"🕒 Таймзона персонажа: {context.persona_timezone}")
    lines.append(f"🕒 Таймзона пользователя: {context.user_timezone}")
    lines.append("")
    lines.append(f"🧭 День: {context.day_type}")
    lines.append(f"🎭 Фаза: {context.narrative_phase}")
    return lines


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header_lines = [f"📅 План публикаций — {context.target_date.strftime('%d %B')}"]
    header_lines.extend(_format_compact_meta(context))
    header = "\n".join(header_lines)

    if not items:
        return f"{header}\n\nПока нет запланированных постов на этот день."

    rows = []
    for idx, item in enumerate(items, start=1):
        source_tz = item.post_timezone or context.persona_timezone
        user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
        rows.append(
            "\n".join(
                [
                    SUMMARY_DIVIDER,
                    "",
                    f"{_post_header_emoji(item.content_type)} POST #{idx}",
                    f"🕒 Персонаж: {item.post_time} ({source_tz})",
                    f"🕒 Вы: {user_time} ({context.user_timezone})",
                    f"🌐 Платформа: {item.platform} • {item.content_type.title()}",
                    f"🎯 Момент: {short_text(item.scene_moment, 110)}",
                    f"✍️ Подпись: {short_text(item.short_caption or item.caption_text, 140)}",
                ]
            )
        )
    return f"{header}\n\n" + "\n\n".join(rows)


def format_post_screen(context: PlanScreenContext, item: PublishingPlanItem, post_index: int) -> str:
    source_tz = item.post_timezone or context.persona_timezone
    user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
    emoji = _post_header_emoji(item.content_type)
    return (
        f"{emoji} POST #{post_index + 1}\n\n"
        f"🌐 Платформа: {item.platform}\n"
        f"{emoji} Формат: {item.content_type.title()}\n"
        f"🕒 Персонаж: {item.post_time} ({source_tz})\n"
        f"🕒 Вы: {user_time} ({context.user_timezone})\n\n"
        f"🎯 Момент: {short_text(item.scene_moment, 220)}\n"
        f"✍️ Подпись: {short_text(item.short_caption or item.caption_text, 220)}"
    )


def _format_detail_header(item: PublishingPlanItem, post_index: int) -> str:
    return f"POST #{post_index + 1} — {item.platform} / {item.content_type.title()}"


def _display_value(value: str | None, fallback: str) -> str:
    return (value or "").strip() or fallback


def _format_field(label: str, value: str) -> str:
    return f"- {label}: {value}"


def _format_manual_generation_step(step: str | None) -> str:
    text = (step or "").strip()
    if not text:
        return "Прикрепите 2–3 основных референса. Если генерация уходит, добавьте 1 дополнительный."

    lowered = " ".join(text.lower().split())
    known_translations = {
        "attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting.": (
            "Прикрепите 2–3 основных референса. Если генерация начинает уходить, добавьте 1 дополнительный."
        ),
        "use the primary anchors first. add secondary anchors only if you need to reinforce angle, emotion, or body consistency.": (
            "Сначала используйте основные референсы. Дополнительные подключайте только если нужно усилить ракурс, эмоцию или консистентность тела."
        ),
        "attach the primary anchors listed below for generation.": (
            "Для генерации прикрепите основные референсы из списка ниже."
        ),
        "attach 2-3 primary anchors, add 1 secondary anchor only if needed.": (
            "Прикрепите 2–3 основных референса. Дополнительный добавляйте только при необходимости."
        ),
    }
    return known_translations.get(lowered, text)


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt_value, prompt_source, legacy_detected, prompt_format_version = resolve_canonical_prompt(item)
    prompt = (prompt_value or "").strip()
    if not prompt:
        prompt_meta = load_prompt_meta(item)
        prompt = str(prompt_meta.get("final_prompt") or "").strip()
        if prompt:
            prompt_source = "prompt_package_json.final_prompt_fallback"
    prompt = _display_value(prompt, "Нет сохранённого prompt для этого поста.")
    caption = _display_value(item.caption_text, "Нет сохранённой подписи.")
    short_caption = _display_value(item.short_caption or item.caption_text, "Нет короткой подписи.")
    negative = _display_value(item.negative_prompt, "No negative prompt.")
    shot_archetype = _display_value(item.shot_archetype, "Не задано")
    generation_mode = _display_value(item.generation_mode, "Не задано")
    framing_mode = _display_value(item.framing_mode, "Не задано")
    prompt_mode = _display_value(item.prompt_mode, "Не задано")
    identity_mode = _display_value(item.identity_mode, "Не задано")
    reference_type = _display_value(item.reference_type or item.reference_pack_type, "Не задано")
    primary_anchors = _display_value(format_reference_aliases(item.primary_anchors), "Нет основных референсов")
    secondary_anchors = _display_value(format_reference_aliases(item.secondary_anchors), "Нет дополнительных референсов")
    manual_generation_step = _format_manual_generation_step(item.manual_generation_step)

    logger.info(
        "telegram_detail_render publication_id=%s prompt_source=%s prompt_format_version=%s legacy_prompt_detected=%s caption=%r short_caption=%r reference_type=%r generation_mode=%r identity_mode=%r framing_mode=%r",
        item.publication_id,
        prompt_source,
        prompt_format_version or "unknown",
        "yes" if legacy_detected else "no",
        item.caption_text,
        item.short_caption,
        item.reference_type or item.reference_pack_type,
        item.generation_mode,
        item.identity_mode,
        item.framing_mode,
    )

    generation_block = "\n".join(
        [
            _format_field("Тип кадра", shot_archetype),
            _format_field("Фрейминг", framing_mode),
            _format_field("Тип референсов", reference_type),
            _format_field("Режим генерации", generation_mode),
        ]
    )
    references_block = "\n".join(
        [
            _format_field("Основные", primary_anchors),
            _format_field("Дополнительные", secondary_anchors),
            _format_field("Как использовать", manual_generation_step),
        ]
    )
    extra_block = "\n".join(
        [
            _format_field("Платформа", item.platform),
            _format_field("Prompt mode", prompt_mode),
            _format_field("Identity mode", identity_mode),
        ]
    )

    return (
        f"📌 {_format_detail_header(item, post_index)}\n\n"
        "🎯 Генерация\n"
        f"{generation_block}\n\n"
        "🧠 Референсы\n"
        f"{references_block}\n\n"
        "🖼 Prompt\n"
        "```\n"
        f"{prompt}\n"
        "```\n\n"
        "🚫 Negative prompt\n"
        "```\n"
        f"{negative}\n"
        "```\n\n"
        "✍️ Подпись\n"
        "```\n"
        f"{caption}\n"
        "```\n\n"
        "📝 Короткая подпись\n"
        "```\n"
        f"{short_caption}\n"
        "```\n\n"
        "⚙️ Дополнительно\n"
        f"{extra_block}"
    )


def format_caption_screen(item: PublishingPlanItem, post_index: int) -> str:
    caption = (item.caption_text or item.short_caption or "").strip()
    body = caption if caption else "Для этого поста пока нет сохранённой подписи."
    return f"{_format_detail_header(item, post_index)}\n\nПодпись:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "Для этого поста пока нет сохранённого момента."
    return f"{_format_detail_header(item, post_index)}\n\nМомент:\n{body}"


def plan_item_key(item: PublishingPlanItem) -> str:
    if item.publication_id:
        return f"publication_id:{item.publication_id}"
    return "|".join([item.date.isoformat(), item.platform, item.content_type, item.scene_moment, item.post_time])


def normalize_plan_items(items: list[PublishingPlanItem]) -> list[PublishingPlanItem]:
    ordered = sorted(
        items,
        key=lambda item: (item.post_time, item.platform, item.content_type, item.publication_id or "", item.scene_moment),
    )
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
        rows.append([(f"📸 Пост {idx + 1}", f"p:{day}:{item.publication_id}")])
    rows.append([("🔄 Обновить", f"plan:{day}")])
    return rows


def build_post_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [
        [("🖼 Prompt", f"pv:{day}:{publication_id}:prompt"), ("✍️ Подпись", f"pv:{day}:{publication_id}:caption")],
        [("🎯 Момент", f"pv:{day}:{publication_id}:moment")],
        [("⬅️ К плану", f"back:plan:{day}")],
    ]


def build_detail_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [[("⬅️ К посту", f"back:post:{day}:{publication_id}"), ("⬅️ К плану", f"back:plan:{day}")]]


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
                "prompt_type": item.prompt_type,
                "prompt_text": item.prompt_text,
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
