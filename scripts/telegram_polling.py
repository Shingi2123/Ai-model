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

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import BadRequest
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
    normalize_plan_items,
    parse_callback,
    serialize_context,
)
from virtual_persona.pipeline.orchestrator import PipelineOrchestrator

settings = AppSettings.from_env()
orchestrator = PipelineOrchestrator(settings)
GET_PLAN_BUTTON = "📅 Получить план на сегодня"
logger = logging.getLogger(__name__)


def _inline_markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=callback) for label, callback in row] for row in rows]
    )


def _build_context(target_date: date, rows: list[dict], items: list):
    city = str(rows[0].get("city") or (items[0].city if items else "Unknown")) if rows or items else "Unknown"
    day_type = str(rows[0].get("day_type") or (items[0].day_type if items else "work_day")) if rows or items else "work_day"
    narrative_phase = (
        str(rows[0].get("narrative_phase") or (items[0].narrative_phase if items else "routine_stability"))
        if rows or items
        else "routine_stability"
    )
    persona_timezone = orchestrator.telegram_delivery_service._resolve_persona_timezone(city)
    return PlanScreenContext(
        target_date=target_date,
        city=city,
        day_type=day_type,
        narrative_phase=narrative_phase,
        persona_timezone=persona_timezone,
        user_timezone=settings.user_timezone,
    )


def _load_persisted_plan(target_date: date) -> tuple[PlanScreenContext, list]:
    rows = orchestrator.state.load_publishing_plan(target_date.isoformat()) if hasattr(orchestrator.state, "load_publishing_plan") else []
    items = normalize_plan_items([item_from_row(row, target_date) for row in rows])
    context = _build_context(target_date, rows, items)
    return context, items


def _ensure_today_plan() -> tuple[PlanScreenContext, list]:
    today = date.today()
    plan_context, items = _load_persisted_plan(today)
    if items:
        return plan_context, items

    package = orchestrator.generate_day(target_date=today)
    if package.publishing_plan:
        items = normalize_plan_items(package.publishing_plan)
        return _build_context(today, [], items), items

    plan_context, items = _load_persisted_plan(today)
    return plan_context, items


def _render_plan(context: PlanScreenContext, items: list):
    normalized = normalize_plan_items(items)
    return format_plan_screen(context, normalized), _inline_markup(build_plan_keyboard(normalized, context.target_date))


def _get_item_index(items: list, publication_id: str | None, post_index: int | None) -> int:
    normalized = normalize_plan_items(items)
    if publication_id:
        for idx, item in enumerate(normalized):
            if item.publication_id == publication_id:
                return idx
        raise IndexError("publication not found")
    if post_index is None:
        raise IndexError("post index is missing")
    if post_index < 0 or post_index >= len(normalized):
        raise IndexError("post index out of range")
    return post_index


def _render_post(context: PlanScreenContext, items: list, post_index: int):
    normalized = normalize_plan_items(items)
    item = normalized[post_index]
    return format_post_screen(context, item, post_index), _inline_markup(build_post_keyboard(context.target_date, item.publication_id))


def _render_detail(context: PlanScreenContext, items: list, post_index: int, view: str):
    normalized = normalize_plan_items(items)
    item = normalized[post_index]
    if view == "prompt":
        text = format_prompt_screen(item, post_index)
    elif view == "caption":
        text = format_caption_screen(item, post_index)
    else:
        text = format_moment_screen(item, post_index)
    return text, _inline_markup(build_detail_keyboard(context.target_date, item.publication_id))


def _log_plan_view(action: str, target_date: date, raw_rows: int, deduped_rows: int, session_restored: bool) -> None:
    logger.info(
        "telegram_plan_view date=%s source=publishing_plan rows=%s deduped_rows=%s session_restored=%s action=%s",
        target_date.isoformat(),
        raw_rows,
        deduped_rows,
        "yes" if session_restored else "no",
        action,
    )


def _load_today_package_and_plan():
    package = orchestrator.generate_day(target_date=date.today())
    plan = package.publishing_plan or orchestrator.publishing_plan_engine.generate(package)
    return package, plan


async def safe_edit_message(
    query,
    *,
    text: str,
    markup: InlineKeyboardMarkup,
    parse_mode: str | None = None,
) -> bool:
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return True
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            logger.info("telegram_plan_view unchanged action=callback data=%s", query.data)
            await query.answer("План уже актуален")
            return False
        raise


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
        plan_context, items = _ensure_today_plan()
        raw_rows = orchestrator.state.load_publishing_plan(plan_context.target_date.isoformat()) if hasattr(orchestrator.state, "load_publishing_plan") else []
        _log_plan_view("show_today", plan_context.target_date, len(raw_rows), len(items), session_restored=False)
        text, markup = _render_plan(plan_context, items)
        context.user_data["plan_screen"] = serialize_context(plan_context, items)
        await loading.edit_text(text=text, reply_markup=markup)
    except Exception as exc:
        logger.exception("telegram_plan_view failed action=show_today error=%s", exc)
        await loading.edit_text("⚠️ Не удалось получить план на сегодня. Попробуйте ещё раз.")


async def callback_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parsed = parse_callback(query.data or "")

    cached = context.user_data.get("plan_screen")
    cached_context = None
    cached_items = []
    if cached:
        try:
            cached_context, cached_items = deserialize_context(cached)
            cached_items = normalize_plan_items(cached_items)
        except Exception:
            cached_context, cached_items = None, []

    target_date = date.today()
    if parsed.target_date:
        try:
            target_date = date.fromisoformat(parsed.target_date)
        except ValueError:
            target_date = date.today()
    elif cached_context:
        target_date = cached_context.target_date

    session_restored = bool(cached_context)

    try:
        plan_context, plan_items = _load_persisted_plan(target_date)
        raw_rows = orchestrator.state.load_publishing_plan(target_date.isoformat()) if hasattr(orchestrator.state, "load_publishing_plan") else []
        _log_plan_view(parsed.view, target_date, len(raw_rows), len(plan_items), session_restored=session_restored)

        # For already-open card transitions, cached snapshot is preferred if valid, otherwise persisted recovery.
        items = cached_items if cached_items and cached_context and cached_context.target_date == target_date else plan_items
        if parsed.view == "plan":
            items = plan_items
            text, markup = _render_plan(plan_context, items)
            context.user_data["plan_screen"] = serialize_context(plan_context, items)
        elif parsed.view == "post":
            idx = _get_item_index(items, parsed.publication_id, parsed.post_index)
            text, markup = _render_post(plan_context, items, idx)
        elif parsed.view in {"prompt", "caption", "moment"}:
            idx = _get_item_index(items, parsed.publication_id, parsed.post_index)
            text, markup = _render_detail(plan_context, items, idx, parsed.view)
        else:
            text, markup = _render_plan(plan_context, plan_items)
            context.user_data["plan_screen"] = serialize_context(plan_context, plan_items)

        if not await safe_edit_message(query, text=text, markup=markup):
            return
        await query.answer()
    except Exception as exc:
        logger.exception("telegram_plan_view failed action=callback data=%s error=%s", query.data, exc)
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
