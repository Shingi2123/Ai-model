from __future__ import annotations

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


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header = (
        f"Plan - {context.target_date.isoformat()}\n\n"
        f"City: {context.city}\n"
        f"Persona timezone: {context.persona_timezone}\n"
        f"Your timezone: {context.user_timezone}\n\n"
        f"Day type: {context.day_type}\n"
        f"Narrative phase: {context.narrative_phase}"
    )

    if not items:
        return f"{header}\n\nNo planned posts for this day."

    rows = []
    for idx, item in enumerate(items, start=1):
        source_tz = item.post_timezone or context.persona_timezone
        user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
        rows.append(f"POST #{idx} - {item.platform} / {item.content_type.title()} - {item.post_time} / {user_time}")
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


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt = _display_value(item.prompt_text, "Нет сохранённого промта для этого поста.")
    caption = _display_value(item.caption_text, "Нет сохранённой подписи.")
    short_caption = _display_value(item.short_caption or item.caption_text, "Нет короткой подписи.")
    negative = _display_value(item.negative_prompt, "No negative prompt.")
    shot_archetype = _display_value(item.shot_archetype, "Не задано")
    platform_intent = _display_value(item.platform_intent, "Не задано")
    generation_mode = _display_value(item.generation_mode, "Не задано")
    framing_mode = _display_value(item.framing_mode, "Не задано")
    prompt_mode = _display_value(item.prompt_mode, "Не задано")
    identity_mode = _display_value(item.identity_mode, "Не задано")
    reference_type = _display_value(item.reference_type or item.reference_pack_type, "Не задано")
    primary_anchors = _display_value(item.primary_anchors, "Нет основных референсов")
    secondary_anchors = _display_value(item.secondary_anchors, "Нет дополнительных референсов")
    manual_generation_step = _format_manual_generation_step(item.manual_generation_step)
    return (
        f"{_format_detail_header(item, post_index)}\n\n"
        "Технические параметры:\n"
        f"- Тип кадра: {shot_archetype}\n"
        f"- Режим генерации: {generation_mode}\n"
        f"- Фрейминг: {framing_mode}\n"
        f"- Режим промта: {prompt_mode}\n"
        f"- Режим identity: {identity_mode}\n"
        f"- Тип референсов: {reference_type}\n"
        f"- Платформенный режим: {platform_intent}\n\n"
        "Референсы для генерации:\n"
        f"- Основные референсы: {primary_anchors}\n"
        f"- Дополнительные референсы: {secondary_anchors}\n"
        f"- Как использовать: {manual_generation_step}\n\n"
        "Подпись (скопировать):\n"
        "```\n"
        f"{caption}\n"
        "```\n\n"
        "Короткая подпись (скопировать):\n"
        "```\n"
        f"{short_caption}\n"
        "```\n\n"
        "Промт (скопировать):\n"
        "```\n"
        f"{prompt}\n"
        "```\n\n"
        "Negative prompt (copy-ready):\n"
        "```\n"
        f"{negative}\n"
        "```"
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
        rows.append([(f"POST {idx + 1}", f"p:{day}:{item.publication_id}")])
    rows.append([("Refresh", f"plan:{day}")])
    return rows


def build_post_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [
        [("Prompt", f"pv:{day}:{publication_id}:prompt"), ("Caption", f"pv:{day}:{publication_id}:caption")],
        [("Moment", f"pv:{day}:{publication_id}:moment")],
        [("Back to plan", f"back:plan:{day}")],
    ]


def build_detail_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [[("Back to post", f"back:post:{day}:{publication_id}"), ("Back to plan", f"back:plan:{day}")]]


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
                "reference_type": item.reference_type,
                "primary_anchors": item.primary_anchors,
                "secondary_anchors": item.secondary_anchors,
                "manual_generation_step": item.manual_generation_step,
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
                publication_id=str(row.get("publication_id", "")),
                date=date.fromisoformat(str(row.get("date"))),
                platform=str(row.get("platform", "Instagram")),
                post_time=str(row.get("post_time", "09:30")),
                content_type=str(row.get("content_type", "photo")),
                city=str(row.get("city", context.city)),
                day_type=str(row.get("day_type", context.day_type)),
                narrative_phase=str(row.get("narrative_phase", context.narrative_phase)),
                scene_moment=str(row.get("scene_moment", "")),
                scene_source=str(row.get("scene_source", "")),
                scene_moment_type=str(row.get("scene_moment_type", "")),
                moment_signature=str(row.get("moment_signature", "")),
                visual_focus=str(row.get("visual_focus", "")),
                activity_type=str(row.get("activity_type", "")),
                outfit_ids=list(row.get("outfit_ids") or []),
                prompt_type=str(row.get("prompt_type", "")),
                prompt_text=str(row.get("prompt_text", "")),
                negative_prompt=str(row.get("negative_prompt", "")),
                shot_archetype=str(row.get("shot_archetype", "")),
                platform_intent=str(row.get("platform_intent", "")),
                generation_mode=str(row.get("generation_mode", "")),
                framing_mode=str(row.get("framing_mode", "")),
                prompt_mode=str(row.get("prompt_mode", "")),
                reference_type=str(row.get("reference_type", "")),
                primary_anchors=str(row.get("primary_anchors", "")),
                secondary_anchors=str(row.get("secondary_anchors", "")),
                manual_generation_step=str(row.get("manual_generation_step", "")),
                caption_text=str(row.get("caption_text", "")),
                short_caption=str(row.get("short_caption", "")),
                post_timezone=str(row.get("post_timezone", "")),
                delivery_status=str(row.get("delivery_status", "planned")),
                notes=str(row.get("notes", "")),
            )
        )
    return context, items


def item_from_row(row: dict, fallback_date: date) -> PublishingPlanItem:
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
    return PublishingPlanItem(
        publication_id=str(row.get("publication_id", "")),
        date=target_date,
        platform=str(row.get("platform", "Instagram")),
        post_time=str(row.get("post_time", "09:30")),
        content_type=str(row.get("content_type", "photo")),
        city=str(row.get("city", "")),
        day_type=str(row.get("day_type", "work_day")),
        narrative_phase=str(row.get("narrative_phase", "routine_stability")),
        scene_moment=str(row.get("scene_moment", "")),
        scene_source=str(row.get("scene_source", "")),
        scene_moment_type=str(row.get("scene_moment_type", "")),
        moment_signature=str(row.get("moment_signature", "")),
        visual_focus=str(row.get("visual_focus", "")),
        activity_type=str(row.get("activity_type", "")),
        outfit_ids=outfit_ids,
        prompt_type=str(row.get("prompt_type", "")),
        prompt_text=str(row.get("prompt_text", "")),
        negative_prompt=str(row.get("negative_prompt", "")),
        shot_archetype=str(row.get("shot_archetype", "")),
        platform_intent=str(row.get("platform_intent", "")),
        generation_mode=str(row.get("generation_mode", "")),
        framing_mode=str(row.get("framing_mode", "")),
        prompt_mode=str(row.get("prompt_mode", "")),
        reference_type=str(row.get("reference_type", "")),
        primary_anchors=str(row.get("primary_anchors", "")),
        secondary_anchors=str(row.get("secondary_anchors", "")),
        manual_generation_step=str(row.get("manual_generation_step", "")),
        caption_text=str(row.get("caption_text", "")),
        short_caption=str(row.get("short_caption", "")),
        post_timezone=str(row.get("post_timezone", "")),
        delivery_status=str(row.get("delivery_status", "planned")),
        notes=str(row.get("notes", "")),
    )
