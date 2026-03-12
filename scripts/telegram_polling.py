from __future__ import annotations

"""Telegram bot command bridge for publishing plan.

Commands:
/today
/plan
/photo
/video
/captions
/moments
/debug
/generate_day
/help
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.publishing_formatter import filter_plan_items, format_command_message, split_for_telegram
from virtual_persona.delivery.telegram_navigation import (
    PlanScreenContext,
    build_detail_keyboard,
    build_plan_keyboard,
    build_post_keyboard,
    deserialize_context,
    format_caption_screen,
    format_moment_screen,
    format_plan_screen,
    format_post_screen,
    format_prompt_screen,
    item_from_row,
    parse_callback,
    serialize_context,
)
from virtual_persona.pipeline.orchestrator import PipelineOrchestrator

settings = AppSettings.from_env()
orchestrator = PipelineOrchestrator(settings)
GET_PLAN_BUTTON = "📅 Получить план на сегодня"


def _inline_markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=callback) for label, callback in row] for row in rows]
    )


def _load_or_generate_today_plan() -> tuple[PlanScreenContext, list]:
    today = date.today()
    rows = orchestrator.state.load_publishing_plan(today.isoformat()) if hasattr(orchestrator.state, "load_publishing_plan") else []
    if rows:
        items = [item_from_row(row, today) for row in rows]
        city = str(rows[0].get("city") or (items[0].city if items else "Unknown"))
        day_type = str(rows[0].get("day_type") or "work_day")
        narrative_phase = str(rows[0].get("narrative_phase") or "routine_stability")
    else:
        package = orchestrator.generate_day(target_date=today)
        items = package.publishing_plan or orchestrator.publishing_plan_engine.generate(package)
        city = package.city
        day_type = package.day_type
        narrative_phase = (
            getattr(package.life_state, "narrative_phase", "routine_stability") if package.life_state else "routine_stability"
        )

    persona_timezone = orchestrator.telegram_delivery_service._resolve_persona_timezone(city)
    context = PlanScreenContext(
        target_date=today,
        city=city,
        day_type=day_type,
        narrative_phase=narrative_phase,
        persona_timezone=persona_timezone,
        user_timezone=settings.user_timezone,
    )
    return context, items


def _render_plan(context: PlanScreenContext, items: list):
    return format_plan_screen(context, items), _inline_markup(build_plan_keyboard(len(items)))


def _render_post(context: PlanScreenContext, items: list, post_index: int):
    item = items[post_index]
    return format_post_screen(context, item, post_index), _inline_markup(build_post_keyboard(post_index))


def _render_detail(context: PlanScreenContext, items: list, post_index: int, view: str):
    item = items[post_index]
    if view == "prompt":
        text = format_prompt_screen(item, post_index)
    elif view == "caption":
        text = format_caption_screen(item, post_index)
    else:
        text = format_moment_screen(item, post_index)
    return text, _inline_markup(build_detail_keyboard(post_index))


def _load_today_package_and_plan():
    package = orchestrator.generate_day(target_date=date.today())
    plan = package.publishing_plan or orchestrator.publishing_plan_engine.generate(package)
    return package, plan


async def generate_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    package = orchestrator.generate_day()
    await update.message.reply_text(f"Generated: {package.date} in {package.city}")


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = ReplyKeyboardMarkup([[GET_PLAN_BUTTON]], resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я помогу работать с контент-планом через кнопки.\nНажмите кнопку ниже 👇",
        reply_markup=keyboard,
    )


async def show_today_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("⏳ Формирую план на сегодня...")
    try:
        plan_context, items = _load_or_generate_today_plan()
        text, markup = _render_plan(plan_context, items)
        context.user_data["plan_screen"] = serialize_context(plan_context, items)
        await loading.edit_text(text=text, reply_markup=markup)
    except Exception:
        await loading.edit_text("⚠️ Не удалось получить план на сегодня. Попробуйте ещё раз.")


async def callback_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    cached = context.user_data.get("plan_screen")
    if not cached:
        await query.edit_message_text("⚠️ Сессия просмотра плана устарела. Нажмите «📅 Получить план на сегодня».")
        return

    try:
        plan_context, items = deserialize_context(cached)
        parsed = parse_callback(query.data or "")
        if parsed.view == "plan":
            text, markup = _render_plan(plan_context, items)
        elif parsed.view == "post" and parsed.post_index is not None:
            if parsed.post_index < 0 or parsed.post_index >= len(items):
                raise IndexError("post index out of range")
            text, markup = _render_post(plan_context, items, parsed.post_index)
        elif parsed.view in {"prompt", "caption", "moment"} and parsed.post_index is not None:
            if parsed.post_index < 0 or parsed.post_index >= len(items):
                raise IndexError("post index out of range")
            text, markup = _render_detail(plan_context, items, parsed.post_index, parsed.view)
        else:
            text, markup = _render_plan(plan_context, items)
        await query.edit_message_text(text=text, reply_markup=markup)
    except Exception:
        await query.edit_message_text("⚠️ Не удалось обработать действие. Нажмите «📅 Получить план на сегодня».")


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = f"/{update.message.text.split()[0].lstrip('/').lower()}"
    package, items = _load_today_package_and_plan()
    filtered = filter_plan_items(items, command)
    persona_timezone = orchestrator.telegram_delivery_service._resolve_persona_timezone(package.city)
    text = format_command_message(package, filtered, command, persona_timezone, settings.user_timezone)
    for part in split_for_telegram(text):
        await update.message.reply_text(part)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(__doc__ or "help")


def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("generate_day", generate_day))
    for command in ["today", "plan", "photo", "video", "captions", "moments", "debug"]:
        app.add_handler(CommandHandler(command, plan_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Regex(f"^{GET_PLAN_BUTTON}$"), show_today_plan))
    app.add_handler(CallbackQueryHandler(callback_nav))
    app.run_polling()


if __name__ == "__main__":
    main()
