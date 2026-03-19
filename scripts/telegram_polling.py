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
from types import SimpleNamespace

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
from virtual_persona.storage.state_store import TelegramStateView


settings = AppSettings.from_env()
orchestrator = PipelineOrchestrator(settings, mode="telegram")
if not isinstance(orchestrator.state, TelegramStateView):
    raise RuntimeError(
        "telegram_polling must run with TelegramStateView (lightweight state); "
        f"got {type(orchestrator.state).__name__}"
    )

GET_PLAN_BUTTON = "📅 Получить план на сегодня"
logger = logging.getLogger(__name__)
MISSING_PLAN_MESSAGE = (
    "📭 План на сегодня ещё не подготовлен.\n\n"
    "Сначала выполните генерацию дня отдельно, затем снова откройте план.\n\n"
    "Что делать:\n"
    "1. Запустить generate-day\n"
    "2. При необходимости отправить план через send-telegram\n"
    "3. Вернуться в бота и нажать «Получить план на сегодня»\n\n"
    "Рекомендуемая команда:\n"
    "python main.py generate-day"
)


def _inline_markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=callback) for label, callback in row] for row in rows]
    )


def _build_context(target_date: date, rows: list[dict], items: list):
    city = str(rows[0].get("city") or (items[0].city if items else "")) if rows or items else ""
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


def _is_today(target_date: date) -> bool:
    return target_date == date.today()


def _load_plan_or_generate(target_date: date, *, auto_generate_if_missing: bool = False) -> tuple[PlanScreenContext, list]:
    context, items = _load_persisted_plan(target_date)
    if items or not auto_generate_if_missing:
        return context, items

    package = orchestrator.generate_day(target_date=target_date)
    regenerated_context, regenerated_items = _load_persisted_plan(target_date)
    if regenerated_items:
        return regenerated_context, regenerated_items

    generated_items = normalize_plan_items(package.publishing_plan or [])
    return _build_context(target_date, [], generated_items), generated_items


def _ensure_today_plan() -> tuple[PlanScreenContext, list]:
    today = date.today()
    return _load_persisted_plan(today)


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


def _log_plan_lookup(target_date: date, items: list) -> None:
    if items:
        logger.info("telegram_polling plan lookup: found existing plan for %s", target_date.isoformat())
        return
    logger.info("telegram_polling autogenerate disabled in UI flow")
    logger.info(
        "telegram_polling plan lookup: no plan found for %s, returning missing-plan message",
        target_date.isoformat(),
    )


def _render_missing_plan(context: PlanScreenContext):
    return MISSING_PLAN_MESSAGE, _inline_markup(build_plan_keyboard([], context.target_date))


def _build_command_package(plan_context: PlanScreenContext):
    return SimpleNamespace(
        date=plan_context.target_date,
        city=plan_context.city or "Unknown",
        day_type=plan_context.day_type,
        life_state=SimpleNamespace(
            narrative_phase=plan_context.narrative_phase,
            energy_state="medium",
            rhythm_state="stable",
        ),
    )


def _load_plan_for_ui(target_date: date, *, action: str, session_restored: bool) -> tuple[PlanScreenContext, list, bool]:
    context, items = _load_persisted_plan(target_date)
    raw_rows = (
        orchestrator.state.load_publishing_plan(target_date.isoformat())
        if hasattr(orchestrator.state, "load_publishing_plan")
        else []
    )
    _log_plan_view(action, target_date, len(raw_rows), len(items), session_restored=session_restored)
    _log_plan_lookup(target_date, items)
    return context, items, bool(items)


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
        message = str(exc)
        if "Message is not modified" in message:
            logger.info("telegram_plan_view unchanged action=callback data=%s", query.data)
            return False
        if "Query is too old" in message or "query id is invalid" in message.lower():
            logger.info("telegram_plan_view stale_callback action=callback data=%s", query.data)
            return False
        raise


async def safe_answer_callback(query, text: str | None = None, *, show_alert: bool = False) -> bool:
    try:
        if text:
            await query.answer(text, show_alert=show_alert)
        else:
            await query.answer()
        return True
    except BadRequest as exc:
        message = str(exc)
        if "Query is too old" in message or "query id is invalid" in message.lower():
            logger.info("telegram_plan_view callback_answer_skipped data=%s reason=%s", query.data, message)
            return False
        raise


def _resolve_target_date(parsed, cached_context) -> date:
    if parsed.target_date:
        try:
            return date.fromisoformat(parsed.target_date)
        except ValueError:
            logger.warning("telegram_callback invalid_target_date data=%s", parsed.target_date)
    if cached_context:
        return cached_context.target_date
    return date.today()


def _load_cached_screen(context: ContextTypes.DEFAULT_TYPE):
    cached = context.user_data.get("plan_screen")
    if not cached:
        return None, []
    try:
        cached_context, cached_items = deserialize_context(cached)
        return cached_context, normalize_plan_items(cached_items)
    except Exception:
        logger.info("telegram_callback stale_cached_screen")
        return None, []


def _select_screen_items(*, parsed, target_date: date, cached_context, cached_items: list, plan_items: list) -> tuple[list, str]:
    if parsed.view == "plan":
        return plan_items, "publishing_plan"
    if plan_items:
        return plan_items, "publishing_plan"
    if cached_items and cached_context and cached_context.target_date == target_date:
        return cached_items, "serialized_callback_context"
    return plan_items, "publishing_plan"


def _render_callback_screen(*, parsed, plan_context: PlanScreenContext, items: list):
    if parsed.view == "plan":
        return _render_plan(plan_context, items), True
    if parsed.view == "post":
        idx = _get_item_index(items, parsed.publication_id, parsed.post_index)
        return _render_post(plan_context, items, idx), False
    if parsed.view in {"prompt", "caption", "moment"}:
        idx = _get_item_index(items, parsed.publication_id, parsed.post_index)
        return _render_detail(plan_context, items, idx, parsed.view), False
    return _render_plan(plan_context, items), True


async def generate_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    package = orchestrator.generate_day()
    await update.message.reply_text(f"Generated: {package.date} in {package.city}")


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = ReplyKeyboardMarkup([[GET_PLAN_BUTTON]], resize_keyboard=True)
    if context.user_data.get("started"):
        await update.message.reply_text("Я уже на связи. Нажмите кнопку, чтобы открыть план.", reply_markup=keyboard)
        return
    context.user_data["started"] = True
    await update.message.reply_text(
        "Привет! Я помогу работать с контент-планом через кнопки.\nНажмите кнопку ниже 👇",
        reply_markup=keyboard,
    )


async def show_today_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loading = await update.message.reply_text("⏳ Формирую план на сегодня...")
    try:
        plan_context, items, has_plan = _load_plan_for_ui(date.today(), action="show_today", session_restored=False)
        if has_plan:
            text, markup = _render_plan(plan_context, items)
            context.user_data["plan_screen"] = serialize_context(plan_context, items)
        else:
            text, markup = _render_missing_plan(plan_context)
        await loading.edit_text(text=text, reply_markup=markup)
    except Exception as exc:
        logger.exception("telegram_plan_view failed action=show_today error=%s", exc)
        await loading.edit_text("⚠️ Не удалось получить план на сегодня. Попробуйте ещё раз.")


async def callback_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        parsed = parse_callback(query.data or "")
        logger.debug("telegram_callback start view=%s data=%s", parsed.view, query.data)

        answer_ok = await safe_answer_callback(query)
        logger.debug("telegram_callback answer_callback %s view=%s", "ok" if answer_ok else "skipped", parsed.view)

        cached_context, cached_items = _load_cached_screen(context)
        target_date = _resolve_target_date(parsed, cached_context)
        session_restored = bool(cached_context)

        plan_context, plan_items, has_plan = _load_plan_for_ui(
            target_date,
            action=parsed.view,
            session_restored=session_restored,
        )
        logger.info(
            "telegram_callback plan_loaded date=%s rows=%s deduped_rows=%s",
            target_date.isoformat(),
            len(plan_items),
            len(plan_items),
        )

        items, items_source = _select_screen_items(
            parsed=parsed,
            target_date=target_date,
            cached_context=cached_context,
            cached_items=cached_items,
            plan_items=plan_items,
        )
        logger.info(
            "telegram_callback detail_source date=%s view=%s source=%s keys=%s",
            target_date.isoformat(),
            parsed.view,
            items_source,
            "caption_text,short_caption,reference_type,generation_mode,identity_mode,framing_mode",
        )

        if not has_plan and not items:
            (text, markup), should_cache = (_render_missing_plan(plan_context), False)
        else:
            (text, markup), should_cache = _render_callback_screen(parsed=parsed, plan_context=plan_context, items=items)
        if should_cache:
            context.user_data["plan_screen"] = serialize_context(plan_context, items)

        logger.debug("telegram_callback render_attempt view=%s", parsed.view)
        changed = await safe_edit_message(query, text=text, markup=markup)
        if not changed:
            logger.debug("telegram_callback render_unchanged view=%s", parsed.view)
            return
        logger.debug("telegram_callback render_success view=%s", parsed.view)
    except Exception as exc:
        logger.exception("telegram_callback fatal_error data=%s error=%s", query.data, exc)
        try:
            await safe_answer_callback(query, "Не удалось обработать действие. Нажмите «📅 Получить план на сегодня».", show_alert=True)
        except Exception:
            logger.exception("telegram_callback fatal_error_notify_failed data=%s", query.data)


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command = f"/{update.message.text.split()[0].lstrip('/').lower()}"
    plan_context, items, has_plan = _load_plan_for_ui(date.today(), action=command, session_restored=False)
    if not has_plan:
        await update.message.reply_text(MISSING_PLAN_MESSAGE)
        return
    package = _build_command_package(plan_context)
    filtered = filter_plan_items(items, command)
    text = format_command_message(package, filtered, command, plan_context.persona_timezone, settings.user_timezone)
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
    try:
        main()
    except KeyboardInterrupt:
        logger.info("telegram_polling stopped by user")
