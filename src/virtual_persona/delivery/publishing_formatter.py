from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
from zoneinfo import ZoneInfo

from virtual_persona.models.domain import DailyPackage, PublishingPlanItem


CONTENT_EMOJI = {
    "photo": "📸",
    "carousel": "🖼️",
    "video": "🎬",
    "reel": "🎞️",
    "stories": "📱",
    "story": "📱",
}


def _convert_time_for_user(target_date, hhmm: str, from_tz: str, to_tz: str) -> str:
    try:
        local_dt = datetime.fromisoformat(f"{target_date.isoformat()}T{hhmm}:00").replace(tzinfo=ZoneInfo(from_tz))
        return local_dt.astimezone(ZoneInfo(to_tz)).strftime("%H:%M")
    except Exception:
        return hhmm


def format_plan_header(package: DailyPackage, persona_timezone: str, user_timezone: str) -> str:
    narrative_phase = getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability"
    return (
        "План публикаций на сегодня\n\n"
        f"City: {package.city}\n"
        f"Local timezone: {persona_timezone}\n"
        f"User timezone: {user_timezone}\n"
        f"Day type: {package.day_type}\n"
        f"Narrative phase: {narrative_phase}"
    )


def format_plan_items(items: Iterable[PublishingPlanItem], package: DailyPackage, persona_timezone: str, user_timezone: str) -> str:
    rows: List[str] = []
    for i, item in enumerate(items, start=1):
        local_time = item.post_time
        user_time = _convert_time_for_user(package.date, item.post_time, persona_timezone, user_timezone)
        content_label = item.content_type.title()
        emoji = CONTENT_EMOJI.get(item.content_type.lower(), "📝")
        rows.append(
            f"{i}️⃣ {item.platform} {content_label} {emoji}\n\n"
            f"Scene:\n{item.scene_moment}\n\n"
            f"Публикация (местное время):\n{local_time}\n\n"
            f"Ваше время:\n{user_time}\n\n"
            f"Prompt:\n{item.prompt_text}\n\n"
            f"Caption:\n{item.caption_text}"
        )
    return "\n\n".join(rows) if rows else "Нет публикаций на сегодня."


def format_plan_message(package: DailyPackage, items: Iterable[PublishingPlanItem], persona_timezone: str, user_timezone: str) -> str:
    body = format_plan_items(items, package, persona_timezone, user_timezone)
    return f"{format_plan_header(package, persona_timezone, user_timezone)}\n\n{body}"


def filter_plan_items(items: list[PublishingPlanItem], command: str) -> list[PublishingPlanItem]:
    cmd = command.strip().lower()
    if cmd in {"/today", "/plan"}:
        return items
    if cmd == "/photo":
        return [i for i in items if i.content_type in {"photo", "carousel"}]
    if cmd == "/video":
        return [i for i in items if i.content_type in {"video", "reel"}]
    if cmd == "/captions":
        return items
    if cmd == "/moments":
        return items
    return items


def format_command_message(package: DailyPackage, items: list[PublishingPlanItem], command: str, persona_timezone: str, user_timezone: str) -> str:
    cmd = command.strip().lower()
    if cmd == "/captions":
        return "\n\n".join(f"{idx}. {item.short_caption or item.caption_text}" for idx, item in enumerate(items, start=1)) or "Нет caption'ов."
    if cmd == "/moments":
        return "\n".join(f"{idx}. {item.scene_moment}" for idx, item in enumerate(items, start=1)) or "Нет scene moments."
    if cmd == "/debug":
        first = items[0] if items else None
        outfit = first.outfit_ids if first else []
        return (
            f"DEBUG\ncity={package.city}\nday_type={package.day_type}\n"
            f"narrative_phase={getattr(package.life_state, 'narrative_phase', 'routine_stability') if package.life_state else 'routine_stability'}\n"
            f"persona_timezone={persona_timezone}\nuser_timezone={user_timezone}\n"
            f"outfit_ids={', '.join(outfit)}\nstory_arc={package.summary}"
        )
    return format_plan_message(package, items, persona_timezone, user_timezone)
