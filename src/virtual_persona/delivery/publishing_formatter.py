from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
from zoneinfo import ZoneInfo

from virtual_persona.models.domain import DailyPackage, PublishingPlanItem


CONTENT_EMOJI = {
    "photo": "📸",
    "carousel": "📸",
    "video": "📹",
    "reel": "📹",
    "stories": "📱",
    "story": "📱",
    "text": "✍️",
}

SECTION_DIVIDER = "━━━━━━━━━━━━━━━━━━"
TELEGRAM_MAX_LEN = 4096


def _convert_time_for_user(target_date, hhmm: str, from_tz: str, to_tz: str) -> str:
    try:
        local_dt = datetime.fromisoformat(f"{target_date.isoformat()}T{hhmm}:00").replace(tzinfo=ZoneInfo(from_tz))
        return local_dt.astimezone(ZoneInfo(to_tz)).strftime("%H:%M")
    except Exception:
        return hhmm


def _post_header_emoji(content_type: str) -> str:
    return CONTENT_EMOJI.get(content_type.lower(), "✍️")


def split_for_telegram(text: str, max_len: int = TELEGRAM_MAX_LEN) -> List[str]:
    if len(text) <= max_len:
        return [text]

    parts: List[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            parts.append(current)
            current = ""
        while len(block) > max_len:
            parts.append(block[:max_len])
            block = block[max_len:]
        current = block

    if current:
        parts.append(current)
    return parts


def format_plan_header(package: DailyPackage, persona_timezone: str, user_timezone: str) -> str:
    narrative_phase = getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability"
    return (
        f"📅 План публикаций — {package.date.strftime('%d %B')}\n\n"
        f"📍 Город персонажа: {package.city}\n"
        f"🕒 Таймзона персонажа: {persona_timezone}\n"
        f"🕒 Ваше время: {user_timezone}\n\n"
        f"🧭 День: {package.day_type}\n"
        f"🎭 Фаза: {narrative_phase}"
    )


def format_plan_items(items: Iterable[PublishingPlanItem], package: DailyPackage, persona_timezone: str, user_timezone: str) -> str:
    rows: List[str] = []
    for i, item in enumerate(items, start=1):
        local_time = item.post_time
        user_time = _convert_time_for_user(package.date, item.post_time, persona_timezone, user_timezone)
        emoji = _post_header_emoji(item.content_type)
        rows.append(
            f"{SECTION_DIVIDER}\n\n"
            f"{emoji} POST #{i}\n\n"
            f"🕘 Время персонажа: {local_time}\n"
            f"🕘 Ваше время: {user_time}\n\n"
            f"🌐 Платформа: {item.platform}\n"
            f"🎬 Тип контента: {item.content_type.title()}\n\n"
            f"🎯 Момент\n{item.scene_moment}\n\n"
            f"🧠 Prompt\n{item.prompt_text}\n\n"
            f"📝 Подпись\n{item.caption_text}\n\n"
            f"🏷 Теги\n{item.day_type} | {item.activity_type} | {item.scene_moment_type} | {item.visual_focus}"
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
        return "\n\n".join(
            f"📝 #{idx}\n{item.short_caption or item.caption_text}" for idx, item in enumerate(items, start=1)
        ) or "Нет caption'ов."
    if cmd == "/moments":
        return "\n\n".join(f"🎯 #{idx}\n{item.scene_moment}" for idx, item in enumerate(items, start=1)) or "Нет scene moments."
    if cmd == "/debug":
        first = items[0] if items else None
        life_state = package.life_state
        return (
            "🛠 DEBUG\n"
            f"city={package.city}\n"
            f"day_type={package.day_type}\n"
            f"narrative_phase={getattr(life_state, 'narrative_phase', 'routine_stability') if life_state else 'routine_stability'}\n"
            f"energy_state={getattr(life_state, 'energy_state', 'medium') if life_state else 'medium'}\n"
            f"timeline_phase={getattr(life_state, 'rhythm_state', 'stable') if life_state else 'stable'}\n"
            f"moment_signature={first.moment_signature if first else ''}"
        )
    return format_plan_message(package, items, persona_timezone, user_timezone)
