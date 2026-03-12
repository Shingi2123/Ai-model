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
    prompt = (item.prompt_text or "").strip()
    body = prompt if prompt else "⚠️ Для этого поста пока нет сохранённого prompt."
    return f"{_format_detail_header(item, post_index)}\n\n🖼 Промпт:\n{body}"


def format_caption_screen(item: PublishingPlanItem, post_index: int) -> str:
    caption = (item.caption_text or item.short_caption or "").strip()
    body = caption if caption else "⚠️ Для этого поста пока нет сохранённой подписи."
    return f"{_format_detail_header(item, post_index)}\n\n✍️ Подпись:\n{body}"


def format_moment_screen(item: PublishingPlanItem, post_index: int) -> str:
    moment = (item.scene_moment or "").strip()
    body = moment if moment else "⚠️ Для этого поста пока нет сохранённого moment."
    return f"{_format_detail_header(item, post_index)}\n\n🧠 Момент:\n{body}"


def build_plan_keyboard(items_count: int) -> list[list[tuple[str, str]]]:
    rows = []
    for idx in range(items_count):
        rows.append([(f"POST {idx + 1}", f"p:{idx}")])
    rows.append([("🔄 Обновить", "plan:today")])
    return rows


def build_post_keyboard(post_index: int) -> list[list[tuple[str, str]]]:
    return [
        [("🖼 Промпт", f"pv:{post_index}:prompt"), ("✍️ Подпись", f"pv:{post_index}:caption")],
        [("🧠 Момент", f"pv:{post_index}:moment")],
        [("⬅️ К плану", "back:plan")],
    ]


def build_detail_keyboard(post_index: int) -> list[list[tuple[str, str]]]:
    return [[("⬅️ К посту", f"back:post:{post_index}"), ("⬅️ К плану", "back:plan")]]


def parse_callback(data: str) -> ParsedCallback:
    if data == "plan:today" or data == "back:plan":
        return ParsedCallback(view="plan")
    if data.startswith("p:"):
        return ParsedCallback(view="post", post_index=int(data.split(":", 1)[1]))
    if data.startswith("back:post:"):
        return ParsedCallback(view="post", post_index=int(data.split(":")[-1]))
    if data.startswith("pv:"):
        _, post_index, view_name = data.split(":", 2)
        return ParsedCallback(view=view_name, post_index=int(post_index))
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
        caption_text=str(row.get("caption_text", "")),
        short_caption=str(row.get("short_caption", "")),
        post_timezone=str(row.get("post_timezone", "")),
        delivery_status=str(row.get("delivery_status", "planned")),
        notes=str(row.get("notes", "")),
    )
