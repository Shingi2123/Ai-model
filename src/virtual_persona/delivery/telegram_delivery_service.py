from __future__ import annotations

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.publishing_formatter import (
    filter_plan_items,
    format_command_message,
    format_plan_message,
)
from virtual_persona.delivery.telegram_bot import TelegramDelivery
from virtual_persona.models.domain import DailyPackage, PublishingPlanItem


class TelegramDeliveryService:
    def __init__(self, settings: AppSettings, state_store=None) -> None:
        self.transport = TelegramDelivery(settings)
        self.state = state_store

    def send_daily_plan(self, package: DailyPackage, plan_items: list[PublishingPlanItem]) -> bool:
        message = format_plan_message(package, plan_items)
        sent = self.transport.send_message(message)
        self._log_delivery(package.date.isoformat(), "auto", "success" if sent else "failed", "daily_plan")
        if not sent:
            self.transport.save_fallback(message, path=f"data/outputs/{package.date.isoformat()}_publishing_plan.md")
        return sent

    def send_command_view(self, package: DailyPackage, plan_items: list[PublishingPlanItem], command: str) -> bool:
        filtered = filter_plan_items(plan_items, command)
        message = format_command_message(package, filtered, command)
        sent = self.transport.send_message(message)
        self._log_delivery(package.date.isoformat(), "manual", "success" if sent else "failed", command)
        return sent

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
