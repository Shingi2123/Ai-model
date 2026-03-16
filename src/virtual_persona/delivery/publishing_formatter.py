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

TIMEZONE_ALIASES = {
    "asia/pavlodar": "Asia/Almaty",
}


def _normalize_timezone(tz_name: str) -> str:
    key = (tz_name or "").strip()
    return TIMEZONE_ALIASES.get(key.lower(), key)



def _convert_time_for_user(target_date, hhmm: str, from_tz: str, to_tz: str) -> str:
    try:
        source_tz = ZoneInfo(_normalize_timezone(from_tz))
        target_tz = ZoneInfo(_normalize_timezone(to_tz))
        local_dt = datetime.fromisoformat(f"{target_date.isoformat()}T{hhmm}:00").replace(tzinfo=source_tz)
        return local_dt.astimezone(target_tz).strftime("%H:%M")
    except Exception:
        return hhmm


def _post_header_emoji(content_type: str) -> str:
    return CONTENT_EMOJI.get(content_type.lower(), "✍️")


def _short_text(text: str, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _resolve_item_timezone(item: PublishingPlanItem, persona_timezone: str) -> str:
    return item.post_timezone or persona_timezone


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
        f"🕒 Таймзона пользователя: {user_timezone}\n\n"
        f"🧭 День: {package.day_type}\n"
        f"🎭 Фаза: {narrative_phase}"
    )


def format_plan_items(items: Iterable[PublishingPlanItem], package: DailyPackage, persona_timezone: str, user_timezone: str) -> str:
    rows: List[str] = []
    for i, item in enumerate(items, start=1):
        source_timezone = _resolve_item_timezone(item, persona_timezone)
        local_time = item.post_time
        user_time = _convert_time_for_user(package.date, item.post_time, source_timezone, user_timezone)
        emoji = _post_header_emoji(item.content_type)
        rows.append(
            f"{SECTION_DIVIDER}\n\n"
            f"{emoji} POST #{i}\n"
            f"🕘 Персонаж: {local_time} ({source_timezone})\n"
            f"🕘 Вы: {user_time} ({user_timezone})\n"
            f"🌐 Платформа: {item.platform} • 🎬 {item.content_type.title()}\n"
            f"🎯 Moment: {_short_text(item.scene_moment, 120)}\n"
            f"📝 Подпись: {_short_text(item.short_caption or item.caption_text, 140)}"
        )
    return "\n\n".join(rows) if rows else "Нет публикаций на сегодня."


def format_plan_message(package: DailyPackage, items: Iterable[PublishingPlanItem], persona_timezone: str, user_timezone: str) -> str:
    body = format_plan_items(items, package, persona_timezone, user_timezone)
    return f"{format_plan_header(package, persona_timezone, user_timezone)}\n\n{body}"


def filter_plan_items(items: list[PublishingPlanItem], command: str) -> list[PublishingPlanItem]:
    cmd = command.strip().lower()
    if cmd in {"/today", "/plan", "/captions", "/moments"}:
        return items
    if cmd == "/photo":
        return [i for i in items if i.content_type in {"photo", "carousel"}]
    if cmd == "/video":
        return [i for i in items if i.content_type in {"video", "reel"}]
    return items


def _format_detailed_prompt(items: list[PublishingPlanItem], content_filter: set[str] | None = None) -> str:
    filtered = [i for i in items if content_filter is None or i.content_type in content_filter]
    if not filtered:
        return "Нет подходящих публикаций."

    def _render(item: PublishingPlanItem, idx: int) -> str:
        base = (
            f"🧠 #{idx} {item.platform} / {item.content_type.title()}\n"
            f"🎯 {item.scene_moment}\n\n"
            f"✍️ Caption:\n{item.caption_text}\n\n"
            f"📝 Short caption:\n{item.short_caption or item.caption_text}\n\n"
            f"🖼 Prompt:\n{item.prompt_text}"
        )
        details = [base]
        if getattr(item, "negative_prompt", ""):
            details.append(f"🚫 Negative prompt:\n{item.negative_prompt}")
        if getattr(item, "shot_archetype", ""):
            details.append(f"📷 Shot archetype: {item.shot_archetype}")
        if getattr(item, "platform_intent", ""):
            details.append(f"🎯 Platform intent: {item.platform_intent}")
        if getattr(item, "identity_mode", ""):
            details.append(f"🧬 Identity mode: {item.identity_mode}")
        if getattr(item, "reference_pack_type", ""):
            details.append(f"🧩 Reference pack: {item.reference_pack_type}")
        if getattr(item, "face_similarity_score", None) is not None:
            details.append(f"🪞 Face similarity: {item.face_similarity_score}")
        return "\n\n".join(details)

    return "\n\n".join(_render(item, idx) for idx, item in enumerate(filtered, start=1))

def format_command_message(package: DailyPackage, items: list[PublishingPlanItem], command: str, persona_timezone: str, user_timezone: str) -> str:
    cmd = command.strip().lower()
    if cmd in {"/today", "/plan"}:
        return format_plan_message(package, items, persona_timezone, user_timezone)
    if cmd == "/photo":
        return _format_detailed_prompt(items, {"photo", "carousel"})
    if cmd == "/video":
        return _format_detailed_prompt(items, {"video", "reel"})
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
            f"persona_timezone={persona_timezone}\n"
            f"user_timezone={user_timezone}\n"
            f"narrative_phase={getattr(life_state, 'narrative_phase', 'routine_stability') if life_state else 'routine_stability'}\n"
            f"energy_state={getattr(life_state, 'energy_state', 'medium') if life_state else 'medium'}\n"
            f"timeline_phase={getattr(life_state, 'rhythm_state', 'stable') if life_state else 'stable'}\n"
            f"moment_signature={first.moment_signature if first else ''}"
        )
    return format_plan_message(package, items, persona_timezone, user_timezone)
