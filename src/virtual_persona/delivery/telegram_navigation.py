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
    return compact[: limit - 1].rstrip() + "…"


def format_plan_screen(context: PlanScreenContext, items: list[PublishingPlanItem]) -> str:
    header = (
        f"📅 План публикаций — {context.target_date.strftime('%d %B')}\n\n"
        f"📍 Город персонажа: {context.city}\n"
        f"🕓 Таймзона персонажа: {context.persona_timezone}\n"
        f"🕓 Таймзона пользователя: {context.user_timezone}\n\n"
        f"📅 День: {context.day_type}\n"
        f"🎭 Фаза: {context.narrative_phase}"
    )

    if not items:
        return f"{header}\n\n⚠️ На сегодня нет публикаций."

    rows = []
    for idx, item in enumerate(items, start=1):
        source_tz = item.post_timezone or context.persona_timezone
        user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
        rows.append(
            f"POST #{idx} — {item.platform} / {item.content_type.title()} — {item.post_time} / {user_time}"
        )
    return f"{header}\n\n" + "\n".join(rows)


def format_post_screen(context: PlanScreenContext, item: PublishingPlanItem, post_index: int) -> str:
    source_tz = item.post_timezone or context.persona_timezone
    user_time = _convert_time_for_user(context.target_date, item.post_time, source_tz, context.user_timezone)
    emoji = _post_header_emoji(item.content_type)
    return (
        f"📌 POST #{post_index + 1}\n\n"
        f"📱 Платформа: {item.platform}\n"
        f"{emoji} Тип: {item.content_type.title()}\n"
        f"🕘 Персонаж: {item.post_time} ({source_tz})\n"
        f"🕘 Вы: {user_time} ({context.user_timezone})\n\n"
        f"🎯 Момент: {short_text(item.scene_moment, 220)}\n"
        f"✍️ Подпись: {short_text(item.short_caption or item.caption_text, 220)}"
    )


def _format_detail_header(item: PublishingPlanItem, post_index: int) -> str:
    return f"📌 POST #{post_index + 1} • {item.platform} / {item.content_type.title()}"


def format_prompt_screen(item: PublishingPlanItem, post_index: int) -> str:
    prompt = (item.prompt_text or "").strip() or "⚠️ Для этого поста пока нет сохранённого prompt."
    caption = (item.caption_text or "").strip() or "⚠️ Нет сохранённой подписи."
    short_caption = (item.short_caption or item.caption_text or "").strip() or "⚠️ Нет короткой подписи."
    negative = (item.negative_prompt or "").strip() or "⚠️ Нет negative prompt."
    shot_archetype = (item.shot_archetype or "").strip() or "⚠️ Не задан"
    platform_intent = (item.platform_intent or "").strip() or "⚠️ Не задан"
    return (
        f"{_format_detail_header(item, post_index)}\n\n"
        f"✍️ Caption:\n{caption}\n\n"
        f"📝 Short caption:\n{short_caption}\n\n"
        "🖼 Prompt (copy-ready):\n"
        "```\n"
        f"{prompt}\n"
        "```\n\n"
        "🚫 Negative prompt (copy-ready):\n"
        "```\n"
        f"{negative}\n"
        "```\n\n"
        f"📷 Shot archetype: {shot_archetype}\n"
        f"🎯 Platform intent: {platform_intent}"
    )


def format_caption_screen(item: PublishingPlanItem, post_index: int) -> str:
    caption = (item.caption_text or item.short_caption or "").strip()
    body = caption if caption else "⚠️ Для этого поста пока нет сохранённой подписи."
    return f"{_format_detail_header(item, post_index)}\n\n✍️ Подпись:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "⚠️ Для этого поста пока нет сохранённого moment."
    return f"{_format_detail_header(item, post_index)}\n\n🧠 Момент:\n{body}"


def plan_item_key(item: PublishingPlanItem) -> str:
    if item.publication_id:
        return f"publication_id:{item.publication_id}"
    return "|".join(
        [
            item.date.isoformat(),
            item.platform,
            item.content_type,
            item.scene_moment,
            item.post_time,
        ]
    )


def normalize_plan_items(items: list[PublishingPlanItem]) -> list[PublishingPlanItem]:
    ordered = sorted(
        items,
        key=lambda item: (
            item.post_time,
            item.platform,
            item.content_type,
            item.publication_id or "",
            item.scene_moment,
        ),
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
    rows.append([("🔄 Обновить", f"plan:{day}")])
    return rows


def build_post_keyboard(target_date: date, publication_id: str) -> list[list[tuple[str, str]]]:
    day = target_date.isoformat()
    return [
        [("🖼 Промпт", f"pv:{day}:{publication_id}:prompt"), ("✍️ Подпись", f"pv:{day}:{publication_id}:caption")],
        [("🧠 Момент", f"pv:{day}:{publication_id}:moment")],
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
                "shot_archetype": item.shot_archetype,
                "platform_intent": item.platform_intent,
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
        caption_text=str(row.get("caption_text", "")),
        short_caption=str(row.get("short_caption", "")),
        post_timezone=str(row.get("post_timezone", "")),
        delivery_status=str(row.get("delivery_status", "planned")),
        notes=str(row.get("notes", "")),
    )
