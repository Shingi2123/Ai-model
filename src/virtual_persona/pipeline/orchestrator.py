from __future__ import annotations

from datetime import datetime, date

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.formatter import package_to_markdown
from virtual_persona.delivery.telegram_bot import TelegramDelivery
from virtual_persona.llm.provider import OpenAIProvider, TemplateFallbackProvider
from virtual_persona.models.domain import DailyPackage
from virtual_persona.pipeline.content_generator import ContentGenerator
from virtual_persona.pipeline.context_builder import ContextBuilder
from virtual_persona.pipeline.continuity_checker import ContinuityChecker
from virtual_persona.pipeline.daily_planner import DailyPlanner
from virtual_persona.services.wardrobe import WardrobeManager
from virtual_persona.storage.state_store import build_state_store


class PipelineOrchestrator:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.state = build_state_store(settings)
        self.context_builder = ContextBuilder(settings, self.state)
        self.planner = DailyPlanner()
        self.wardrobe = WardrobeManager()
        self.checker = ContinuityChecker()
        self.delivery = TelegramDelivery(settings)

        if settings.llm_provider.lower() == "openai" and settings.llm_api_key and settings.llm_model:
            llm = OpenAIProvider(settings.llm_api_key, settings.llm_model)
        else:
            llm = TemplateFallbackProvider()
        self.content_generator = ContentGenerator(llm)

    def generate_day(self, target_date: date | None = None, override_city: str | None = None) -> DailyPackage:
        context = self.context_builder.build(target_date=target_date, override_city=override_city)
        scenes = self.planner.build_day(context)
        outfit = self.wardrobe.select_outfit(
            temp_c=context["weather"].temp_c,
            condition=context["weather"].condition,
            preferred_style=context["character"].style.preferred[0],
            today=context["date"],
        )
        content = self.content_generator.generate(context, scenes, outfit.summary)
        issues = self.checker.run(context, scenes, outfit)

        package = DailyPackage(
            generated_at=datetime.utcnow(),
            date=context["date"],
            city=context["city"],
            day_type=context["day_type"],
            summary=" → ".join(scene.description for scene in scenes),
            weather=context["weather"],
            sun=context["sun"],
            outfit=outfit,
            scenes=scenes,
            content=content,
            continuity_issues=issues,
        )

        self.wardrobe.persist()
        self.state.save_content_package(package)
        self.state.append_history(package)
        self.state.append_daily_calendar(package)
        self.state.ensure_city_exists(package)
        self.state.save_run_log("success", f"Generated package for {package.date} in {package.city}")
        return package

    def send_latest(self, package: DailyPackage) -> bool:
        payload_md = package_to_markdown(package)
        sent = self.delivery.send_message(payload_md)
        if not sent:
            self.delivery.save_fallback(payload_md)
            self.state.save_run_log("warning", "Telegram delivery failed; fallback saved")
        else:
            self.state.save_run_log("success", "Telegram delivery succeeded")
        return sent

    def check_continuity(self, target_date: date | None = None) -> list:
        package = self.generate_day(target_date=target_date)
        return package.continuity_issues