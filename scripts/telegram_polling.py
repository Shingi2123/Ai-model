from __future__ import annotations

"""Minimal Telegram bot command bridge.

Commands:
/generate_day
/show_today
/show_history
/regenerate
/set_city <City>
/help
"""

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from virtual_persona.config.settings import AppSettings
from virtual_persona.pipeline.orchestrator import PipelineOrchestrator

settings = AppSettings.from_env()
orchestrator = PipelineOrchestrator(settings)


async def generate_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    package = orchestrator.generate_day()
    await update.message.reply_text(f"Generated: {package.date} in {package.city}")


async def show_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = Path(f"data/outputs/{date.today().isoformat()}_package.json")
    if today.exists():
        await update.message.reply_text(today.read_text(encoding="utf-8")[:3500])
    else:
        await update.message.reply_text("No package for today yet.")


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    path = Path("data/state/content_history.json")
    if path.exists():
        history = json.loads(path.read_text(encoding="utf-8"))
        await update.message.reply_text("\n".join(f"{h['date']} — {h['city']}" for h in history[-10:]))
    else:
        await update.message.reply_text("History is empty.")


async def regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    package = orchestrator.generate_day()
    await update.message.reply_text(f"Regenerated package for {package.date}")


async def set_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /set_city <City>")
        return
    city = " ".join(context.args)
    package = orchestrator.generate_day(override_city=city)
    await update.message.reply_text(f"Generated with override city: {package.city}")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(__doc__ or "help")


def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("generate_day", generate_day))
    app.add_handler(CommandHandler("show_today", show_today))
    app.add_handler(CommandHandler("show_history", show_history))
    app.add_handler(CommandHandler("regenerate", regenerate))
    app.add_handler(CommandHandler("set_city", set_city))
    app.add_handler(CommandHandler("help", help_cmd))
    app.run_polling()


if __name__ == "__main__":
    main()
