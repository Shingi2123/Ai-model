from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.formatter import package_to_markdown
from virtual_persona.pipeline.orchestrator import PipelineOrchestrator
from virtual_persona.storage.state_store import LocalStateStore
from virtual_persona.utils.logging import configure_logging


def cmd_generate_day(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    target = date.fromisoformat(args.date) if args.date else None
    package = orchestrator.generate_day(target_date=target, override_city=args.city)
    print(f"Generated package: {package.date} / {package.city}")


def cmd_check_continuity(args: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    issues = orchestrator.check_continuity(date.fromisoformat(args.date) if args.date else None)
    if not issues:
        print("No continuity issues.")
    for issue in issues:
        print(f"[{issue.level}] {issue.code}: {issue.message}")


def cmd_send_telegram(_: argparse.Namespace, orchestrator: PipelineOrchestrator) -> None:
    today_path = Path(f"data/outputs/{date.today().isoformat()}_package.json")
    if not today_path.exists():
        raise FileNotFoundError("No generated package for today. Run generate-day first.")
    payload = json.loads(today_path.read_text(encoding="utf-8"))
    text = f"Daily package for {payload['date']} in {payload['city']}\n\n{payload['summary']}"
    sent = orchestrator.delivery.send_message(text)
    if not sent:
        fallback = orchestrator.delivery.save_fallback(text)
        print(f"Telegram failed; saved fallback to {fallback}")
    else:
        print("Sent to Telegram.")


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
    g.set_defaults(func=cmd_generate_day)

    c = sub.add_parser("check-continuity")
    c.add_argument("--date", help="YYYY-MM-DD")
    c.set_defaults(func=cmd_check_continuity)

    s = sub.add_parser("send-telegram")
    s.set_defaults(func=cmd_send_telegram)

    b = sub.add_parser("bootstrap")
    b.set_defaults(func=cmd_bootstrap)

    t = sub.add_parser("test-run")
    t.set_defaults(func=cmd_test_run)

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
