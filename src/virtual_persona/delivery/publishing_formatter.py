from __future__ import annotations

from typing import Iterable, List

from virtual_persona.models.domain import DailyPackage, PublishingPlanItem


def format_plan_header(package: DailyPackage) -> str:
    narrative_phase = getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability"
    return (
        f"План публикаций на {package.date.isoformat()}\n"
        f"Город: {package.city} | День: {package.day_type} | Фаза: {narrative_phase}"
    )


def format_plan_items(items: Iterable[PublishingPlanItem]) -> str:
    rows: List[str] = []
    for i, item in enumerate(items, start=1):
        rows.append(
            f"{i}. {item.post_time} • {item.platform} • {item.content_type}\n"
            f"Момент: {item.scene_moment}\n"
            f"Prompt: {item.prompt_text}\n"
            f"Caption: {item.caption_text}"
        )
    return "\n\n".join(rows) if rows else "Нет публикаций на сегодня."


def format_plan_message(package: DailyPackage, items: Iterable[PublishingPlanItem]) -> str:
    body = format_plan_items(items)
    return f"{format_plan_header(package)}\n\n{body}"


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


def format_command_message(package: DailyPackage, items: list[PublishingPlanItem], command: str) -> str:
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
            f"outfit_ids={', '.join(outfit)}\nstory_arc={package.summary}"
        )
    return format_plan_message(package, items)
