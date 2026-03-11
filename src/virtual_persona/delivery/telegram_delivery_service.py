from __future__ import annotations

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.publishing_formatter import (
    filter_plan_items,
    format_command_message,
    format_plan_message,
    split_for_telegram,
)
from virtual_persona.delivery.telegram_bot import TelegramDelivery
from virtual_persona.models.domain import DailyPackage, PublishingPlanItem


class TelegramDeliveryService:
    def __init__(self, settings: AppSettings, state_store=None) -> None:
        self.transport = TelegramDelivery(settings)
        self.state = state_store
        self.settings = settings

    def _resolve_persona_timezone(self, city: str) -> str:
        if self.state and hasattr(self.state, "load_cities"):
            for row in self.state.load_cities() or []:
                if str(row.get("city", "")).strip().lower() == city.strip().lower() and row.get("timezone"):
                    return str(row.get("timezone")).strip()
        return self.settings.timezone

    def send_daily_plan(self, package: DailyPackage, plan_items: list[PublishingPlanItem]) -> bool:
        persona_timezone = self._resolve_persona_timezone(package.city)
        message = format_plan_message(package, plan_items, persona_timezone, self.settings.user_timezone)
        sent = self._send_chunked(message)
        self._log_delivery(package.date.isoformat(), "auto", "success" if sent else "failed", "daily_plan")
        if not sent:
            self.transport.save_fallback(message, path=f"data/outputs/{package.date.isoformat()}_publishing_plan.md")
        return sent

    def send_command_view(self, package: DailyPackage, plan_items: list[PublishingPlanItem], command: str) -> bool:
        filtered = filter_plan_items(plan_items, command)
        persona_timezone = self._resolve_persona_timezone(package.city)
        message = format_command_message(package, filtered, command, persona_timezone, self.settings.user_timezone)
        sent = self._send_chunked(message)
        self._log_delivery(package.date.isoformat(), "manual", "success" if sent else "failed", command)
        return sent


    def _send_chunked(self, text: str) -> bool:
        parts = split_for_telegram(text)
        statuses = [self.transport.send_message(part) for part in parts]
        return all(statuses) if statuses else False

    def _log_delivery(self, target_date: str, delivery_type: str, status: str, details: str) -> None:
        if self.state and hasattr(self.state, "append_delivery_log"):
            self.state.append_delivery_log(
                {
                    "date": target_date,
                    "delivery_type": delivery_type,
                    "status": status,
                    "message_id": "",
                    "error": "" if status == "success" else "telegram_send_failed",
                    "details": details,
                }
            )
