from __future__ import annotations

import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from virtual_persona.pipeline.orchestrator import PipelineOrchestrator


class DailySchedulerService:
    def __init__(self, orchestrator: PipelineOrchestrator, delivery_time: str) -> None:
        self.orchestrator = orchestrator
        self.delivery_time = delivery_time
        self._last_run_date: date | None = None

    def _resolve_persona_timezone(self, city: str) -> str:
        state = self.orchestrator.state
        if hasattr(state, "load_cities"):
            for row in state.load_cities() or []:
                if str(row.get("city", "")).strip().lower() == city.strip().lower() and row.get("timezone"):
                    return str(row.get("timezone")).strip()
        return self.orchestrator.settings.timezone

    def _current_city(self) -> str:
        context = self.orchestrator.context_builder.build(target_date=date.today())
        return str(context.get("city") or self.orchestrator.settings.default_city)

    def run_once(self) -> bool:
        city = self._current_city()
        persona_timezone = self._resolve_persona_timezone(city)
        persona_now = datetime.now(ZoneInfo(persona_timezone))
        now_hhmm = persona_now.strftime("%H:%M")
        if now_hhmm != self.delivery_time:
            return False
        if self._last_run_date == persona_now.date():
            return False

        package = self.orchestrator.generate_day(target_date=persona_now.date(), override_city=city)
        sent = self.orchestrator.telegram_delivery_service.send_daily_plan(package, package.publishing_plan)
        self._last_run_date = persona_now.date()
        return sent

    def run_forever(self, sleep_seconds: int = 30) -> None:
        while True:
            self.run_once()
            time.sleep(sleep_seconds)
