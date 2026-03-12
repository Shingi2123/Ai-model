from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.formatter import package_to_markdown
from virtual_persona.delivery.publishing_formatter import format_command_message
from virtual_persona.pipeline.orchestrator import PipelineOrchestrator
from virtual_persona.services.daily_scheduler import DailySchedulerService
from virtual_persona.utils.logging import configure_logging


def cmd_generate_day(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    target = date.fromisoformat(args.date) if args.date else None
    if target and not args.force_regenerate and hasattr(orchestrator.state, "load_publishing_plan"):
        existing = orchestrator.state.load_publishing_plan(target.isoformat())
        if existing:
            print(f"Day {target.isoformat()} already exists; reusing frozen package.")
    if target and args.force_regenerate:
        print(f"Force regenerate enabled for {target.isoformat()}: existing day will be replaced.")
    package = orchestrator.generate_day(target_date=target, override_city=args.city, force_regenerate=args.force_regenerate)
    print(f"Generated package: {package.date} / {package.city}")


def cmd_check_continuity(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    issues = orchestrator.check_continuity(date.fromisoformat(args.date) if args.date else None)
    if not issues:
        print("No continuity issues.")
    for issue in issues:
        print(f"[{issue.level}] {issue.code}: {issue.message}")


def cmd_send_telegram(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    package = orchestrator.generate_day(target_date=date.today())
    command = args.command_filter or "/today"
    sent = orchestrator.telegram_delivery_service.send_command_view(package, package.publishing_plan, command)
    if not sent:
        persona_timezone = orchestrator.telegram_delivery_service._resolve_persona_timezone(package.city)
        text = format_command_message(package, package.publishing_plan, command, persona_timezone, orchestrator.settings.user_timezone)
        fallback = orchestrator.delivery.save_fallback(text)
        print(f"Telegram failed; saved fallback to {fallback}")
    else:
        print(f"Sent plan to Telegram ({command}).")




def cmd_run_daily(_: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    scheduler = DailySchedulerService(orchestrator, orchestrator.settings.telegram_delivery_time)
    print(f"Daily scheduler started (persona-local time {orchestrator.settings.telegram_delivery_time})")
    scheduler.run_forever()

def cmd_bootstrap(_: argparse.Namespace, __: PipelineOrchestrator) -> None:
    Path("data/state").mkdir(parents=True, exist_ok=True)
    Path("data/outputs").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    print("Bootstrap complete: data directories initialized.")


def cmd_test_run(_: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    package = orchestrator.generate_day()
    md = package_to_markdown(package)
    md_path = Path(f"data/outputs/{package.date.isoformat()}_package.md")
    md_path.write_text(md, encoding="utf-8")
    print(f"Test run complete. Markdown package saved to {md_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Virtual AI character consistency engine")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate-day")
    g.add_argument("--date", help="YYYY-MM-DD")
    g.add_argument("--city", help="Override city")
    g.add_argument("--force-regenerate", action="store_true", help="Regenerate even if day already exists")
    g.set_defaults(func=cmd_generate_day)

    c = sub.add_parser("check-continuity")
    c.add_argument("--date", help="YYYY-MM-DD")
    c.set_defaults(func=cmd_check_continuity)

    s = sub.add_parser("send-telegram")
    s.add_argument("--command-filter", choices=["/today", "/plan", "/photo", "/video", "/captions", "/moments", "/debug"], help="Filter view to send")
    s.set_defaults(func=cmd_send_telegram)

    b = sub.add_parser("bootstrap")
    b.set_defaults(func=cmd_bootstrap)

    t = sub.add_parser("test-run")
    t.set_defaults(func=cmd_test_run)

    d = sub.add_parser("run-daily")
    d.set_defaults(func=cmd_run_daily)

    return parser


def main() -> None:
    settings = AppSettings.from_env()
    configure_logging(settings.log_level)
    orchestrator = PipelineOrchestrator(settings)

    parser = build_parser()
    args = parser.parse_args()
    args.func(args, orchestrator)


if __name__ == "__main__":
    main()
