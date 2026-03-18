from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from virtual_persona.delivery.publishing_formatter import _convert_time_for_user, _post_header_emoji
from virtual_persona.models.domain import PublishingPlanItem


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
        lines.append(f"📍 {context.city}")
    lines.append(f"🕒 {context.persona_timezone} -> {context.user_timezone}")
    lines.append(f"🧭 {context.day_type} • {context.narrative_phase}")
    return lines


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header_lines = [f"📅 Plan - {context.target_date.isoformat()}"]
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
                    f"📌 POST #{idx}",
                    f"- {item.platform} / {item.content_type.title()}",
                    f"- Persona: {item.post_time} ({source_tz})",
                    f"- You: {user_time} ({context.user_timezone})",
                    f"- Moment: {short_text(item.scene_moment, 90)}",
                ]
            )
        )
    return f"{header}\n\n" + "\n".join(rows)


def format_post_screen(context: PlanScreenContext, item: PublishingPlanItem, post_index: int) -> str:
    source_tz = item.post_timezone or context.persona_timezone
    user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
    emoji = _post_header_emoji(item.content_type)
    return (
        f"POST #{post_index + 1}\n\n"
        f"Platform: {item.platform}\n"
        f"{emoji} Type: {item.content_type.title()}\n"
        f"Persona time: {item.post_time} ({source_tz})\n"
        f"Your time: {user_time} ({context.user_timezone})\n\n"
        f"Moment: {short_text(item.scene_moment, 220)}\n"
        f"Caption: {short_text(item.short_caption or item.caption_text, 220)}"
    )


def _format_detail_header(item: PublishingPlanItem, post_index: int) -> str:
    return f"POST #{post_index + 1} - {item.platform} / {item.content_type.title()}"


def _display_value(value: str | None, fallback: str) -> str:
    return (value or "").strip() or fallback


def _format_field(label: str, value: str) -> str:
    return f"- {label}: {value}"


def _normalize_reference_aliases(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    aliases: list[str] = []
    seen: set[str] = set()
    for chunk in raw.replace(";", ",").split(","):
        token = chunk.strip().replace("\\", "/")
        if not token:
            continue
        token = token.rstrip("/")
        parts = [part for part in token.split("/") if part and part != "."]
        alias = parts[-1] if parts else token
        if alias.lower() == "refs" and len(parts) > 1:
            alias = parts[-2]
        if alias not in seen:
            seen.add(alias)
            aliases.append(alias)
    return ", ".join(aliases)


def _format_manual_generation_step(step: str | None) -> str:
    text = (step or "").strip()
    if not text:
        return "Приложите основные референсы из списка ниже."

    lowered = " ".join(text.lower().split())
    known_translations = {
        "attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting.": (
            "Прикрепите 2-3 основных референса. "
            "Если генерация начинает уходить, добавьте 1 дополнительный."
        ),
        "use the primary anchors first. add secondary anchors only if you need to reinforce angle, emotion, or body consistency.": (
            "Сначала используйте основные референсы. "
            "Дополнительные подключайте только если нужно усилить ракурс, эмоцию или тело."
        ),
        "attach the primary anchors listed below for generation.": (
            "Для генерации приложите основные референсы из списка ниже."
        ),
    }
    if lowered in known_translations:
        return known_translations[lowered]
    return text


def _stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _load_prompt_meta(row: dict) -> dict:
    raw = row.get("prompt_package_json")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _detail_value(row: dict, key: str, *, prompt_meta: dict | None = None, aliases: tuple[str, ...] = ()) -> str:
    candidates = (key,) + aliases
    for candidate in candidates:
        value = row.get(candidate)
        if value is not None and str(value).strip():
            return str(value)
    meta = prompt_meta or {}
    for candidate in candidates:
        value = meta.get(candidate)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _item_kwargs_from_row(row: dict, fallback_date: date, *, default_city: str = "", default_day_type: str = "work_day", default_narrative_phase: str = "routine_stability") -> dict:
    row_date = str(row.get("date", fallback_date.isoformat()))
    try:
        target_date = date.fromisoformat(row_date)
    except ValueError:
        target_date = fallback_date

    outfit_ids_raw = row.get("outfit_ids") or []
    if isinstance(outfit_ids_raw, str):
        outfit_ids = [x.strip() for x in outfit_ids_raw.split(",") if x.strip()]
    else:
        outfit_ids = list(outfit_ids_raw)

    prompt_meta = _load_prompt_meta(row)
    return {
        "publication_id": _stringify(row.get("publication_id", "")),
        "date": target_date,
        "platform": _stringify(row.get("platform", "Instagram")),
        "post_time": _stringify(row.get("post_time", "09:30")),
        "content_type": _stringify(row.get("content_type", "photo")),
        "city": _stringify(row.get("city", default_city)),
        "day_type": _stringify(row.get("day_type", default_day_type)),
        "narrative_phase": _stringify(row.get("narrative_phase", default_narrative_phase)),
        "scene_moment": _stringify(row.get("scene_moment", "")),
        "scene_source": _stringify(row.get("scene_source", "")),
        "scene_moment_type": _stringify(row.get("scene_moment_type", "")),
        "moment_signature": _stringify(row.get("moment_signature", "")),
        "visual_focus": _stringify(row.get("visual_focus", "")),
        "activity_type": _stringify(row.get("activity_type", "")),
        "outfit_ids": outfit_ids,
        "prompt_type": _stringify(row.get("prompt_type", "")),
        "prompt_text": _stringify(row.get("prompt_text", "")),
        "negative_prompt": _detail_value(row, "negative_prompt", prompt_meta=prompt_meta),
        "prompt_package_json": _stringify(row.get("prompt_package_json", "")),
        "shot_archetype": _detail_value(row, "shot_archetype", prompt_meta=prompt_meta),
        "platform_intent": _detail_value(row, "platform_intent", prompt_meta=prompt_meta),
        "generation_mode": _detail_value(row, "generation_mode", prompt_meta=prompt_meta),
        "framing_mode": _detail_value(row, "framing_mode", prompt_meta=prompt_meta),
        "prompt_mode": _detail_value(row, "prompt_mode", prompt_meta=prompt_meta),
        "reference_type": _detail_value(row, "reference_type", prompt_meta=prompt_meta, aliases=("reference_pack_type",)),
        "primary_anchors": _detail_value(row, "primary_anchors", prompt_meta=prompt_meta),
        "secondary_anchors": _detail_value(row, "secondary_anchors", prompt_meta=prompt_meta),
        "manual_generation_step": _detail_value(row, "manual_generation_step", prompt_meta=prompt_meta),
        "caption_text": _detail_value(row, "caption_text", prompt_meta=prompt_meta, aliases=("caption",)),
        "short_caption": _detail_value(row, "short_caption", prompt_meta=prompt_meta),
        "post_timezone": _stringify(row.get("post_timezone", "")),
        "publish_score": row.get("publish_score"),
        "selection_reason": _stringify(row.get("selection_reason", "")),
        "delivery_status": _stringify(row.get("delivery_status", "planned")),
        "notes": _stringify(row.get("notes", "")),
        "selected_image_path": _stringify(row.get("selected_image_path", "")),
        "clean_image_export_path": _stringify(row.get("clean_image_export_path", "")),
        "generation_diagnostics": _stringify(row.get("generation_diagnostics", "")),
        "identity_mode": _detail_value(row, "identity_mode", prompt_meta=prompt_meta),
        "reference_pack_type": _detail_value(row, "reference_pack_type", prompt_meta=prompt_meta, aliases=("reference_type",)),
        "face_similarity_score": row.get("face_similarity_score"),
    }


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt = _display_value(item.prompt_text, "Нет сохраненного prompt для этого поста.")
    caption = _display_value(item.caption_text, "Нет сохраненной подписи.")
    short_caption = _display_value(item.short_caption or item.caption_text, "Нет короткой подписи.")
    negative = _display_value(item.negative_prompt, "No negative prompt.")
    shot_archetype = _display_value(item.shot_archetype, "Не задано")
    generation_mode = _display_value(item.generation_mode, "Не задано")
    framing_mode = _display_value(item.framing_mode, "Не задано")
    prompt_mode = _display_value(item.prompt_mode, "Не задано")
    identity_mode = _display_value(item.identity_mode, "Не задано")
    reference_type = _display_value(item.reference_type or item.reference_pack_type, "Не задано")
    primary_anchors = _display_value(_normalize_reference_aliases(item.primary_anchors), "Нет основных референсов")
    secondary_anchors = _display_value(
        _normalize_reference_aliases(item.secondary_anchors),
        "Нет дополнительных референсов",
    )
    manual_generation_step = _format_manual_generation_step(item.manual_generation_step)

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
    body = caption if caption else "No saved caption for this post yet."
    return f"{_format_detail_header(item, post_index)}\n\nCaption:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "No saved scene moment for this post yet."
    return f"{_format_detail_header(item, post_index)}\n\nMoment:\n{body}"


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
        rows.append([(f"📌 Пост {idx + 1}", f"p:{day}:{item.publication_id}")])
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
    return [[("⬅️ К посту", f"back:post:{day}:{publication_id}"), ("📅 К плану", f"back:plan:{day}")]]


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
                "notes": item.notes,
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
    items = []
    for row in raw.get("items", []):
        items.append(
            PublishingPlanItem(
                **_item_kwargs_from_row(
                    row,
                    context.target_date,
                    default_city=context.city,
                    default_day_type=context.day_type,
                    default_narrative_phase=context.narrative_phase,
                )
            )
        )
    return context, items


def item_from_row(row: dict, fallback_date: date) -> PublishingPlanItem:
    return PublishingPlanItem(**_item_kwargs_from_row(row, fallback_date))
