from __future__ import annotations

from datetime import datetime, date

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.formatter import package_to_markdown
from virtual_persona.delivery.telegram_bot import TelegramDelivery
from virtual_persona.delivery.telegram_delivery_service import TelegramDeliveryService
from virtual_persona.llm.provider import OpenAIProvider, TemplateFallbackProvider
from virtual_persona.models.domain import DailyPackage
from virtual_persona.narrative.life_narrative_engine import LifeNarrativeEngine
from virtual_persona.pipeline.content_generator import ContentGenerator
from virtual_persona.pipeline.context_builder import ContextBuilder
from virtual_persona.pipeline.continuity_checker import ContinuityChecker
from virtual_persona.pipeline.daily_planner import DailyPlanner
from virtual_persona.pipeline.asset_evolution_engine import AssetEvolutionEngine
from virtual_persona.pipeline.activity_evolution_engine import ActivityEvolutionEngine
from virtual_persona.pipeline.life_diversity_engine import LifeDiversityEngine
from virtual_persona.pipeline.scene_activity_engine import SceneActivityExpansionEngine
from virtual_persona.pipeline.story_arc_engine import StoryArcEngine
from virtual_persona.pipeline.scene_moment_engine import SceneMomentGenerator
from virtual_persona.pipeline.publishing_plan_engine import PublishingPlanEngine
from virtual_persona.pipeline.world_expansion_engine import WorldExpansionEngine
from virtual_persona.pipeline.wardrobe_brain import WardrobeBrain
from virtual_persona.services.wardrobe import WardrobeManager
from virtual_persona.storage.state_store import build_state_store


class PipelineOrchestrator:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.state = build_state_store(settings)
        self.context_builder = ContextBuilder(settings, self.state)
        self.planner = DailyPlanner(self.state)
        self.wardrobe = WardrobeManager(self.state)
        self.asset_engine = AssetEvolutionEngine(self.state)
        self.scene_activity_engine = SceneActivityExpansionEngine(self.state)
        self.life_narrative_engine = LifeNarrativeEngine(self.state)
        self.story_arc_engine = StoryArcEngine(self.state)
        self.world_expansion_engine = WorldExpansionEngine(self.state)
        self.activity_evolution_engine = ActivityEvolutionEngine(self.state)
        self.diversity_engine = LifeDiversityEngine(self.state)
        self.wardrobe_brain = WardrobeBrain(self.state)
        self.scene_moment_engine = SceneMomentGenerator(self.state)
        self.checker = ContinuityChecker()
        self.delivery = TelegramDelivery(settings)
        self.publishing_plan_engine = PublishingPlanEngine(self.state)
        self.telegram_delivery_service = TelegramDeliveryService(settings, self.state)

        if settings.llm_provider.lower() == "openai" and settings.llm_api_key and settings.llm_model:
            llm = OpenAIProvider(settings.llm_api_key, settings.llm_model)
        else:
            llm = TemplateFallbackProvider()
        self.content_generator = ContentGenerator(llm, self.state)

    def generate_day(self, target_date: date | None = None, override_city: str | None = None) -> DailyPackage:
        context = self.context_builder.build(target_date=target_date, override_city=override_city)

        narrative_context = self.life_narrative_engine.build_context(context["date"], context)
        context["narrative_context"] = narrative_context
        if context.get("life_state"):
            context["life_state"].narrative_phase = narrative_context.narrative_phase
            context["life_state"].energy_state = narrative_context.energy_state
            context["life_state"].rhythm_state = narrative_context.rhythm_state
            context["life_state"].novelty_pressure = narrative_context.novelty_pressure
            context["life_state"].recovery_need = narrative_context.recovery_need

        context["story_arc"] = self.story_arc_engine.run(context)
        context["diversity_metrics"] = self.diversity_engine.analyze(lookback_days=7)

        self.world_expansion_engine.run(context)
        self.activity_evolution_engine.run(context)

        generated_scenes, _ = self.scene_activity_engine.ensure_candidates(context)
        scenes = self.planner.build_day(context)
        if not scenes and generated_scenes:
            scenes = generated_scenes

        scene_memory = self.state.load_scene_memory() if hasattr(self.state, "load_scene_memory") else []
        activity_memory = self.state.load_activity_memory() if hasattr(self.state, "load_activity_memory") else []
        location_memory = self.state.load_location_memory() if hasattr(self.state, "load_location_memory") else []
        filtered = self.life_narrative_engine.variation_controller.filter_scenes(
            day_type=context["day_type"],
            city=context["city"],
            scenes=scenes,
            scene_memory=scene_memory,
            activity_memory=activity_memory,
            location_memory=location_memory,
        )
        if filtered:
            scenes = filtered

        outfit = self.wardrobe.select_outfit(
            temp_c=context["weather"].temp_c,
            condition=context["weather"].condition,
            preferred_style=context["character"].style.preferred[0],
            today=context["date"],
            day_type=context["day_type"],
            city=context["city"],
            occasion=context["day_type"],
        )
        scenes = self.scene_moment_engine.generate(context, scenes)
        content = self.content_generator.generate(context, scenes, outfit.summary, outfit.item_ids)
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
            life_state=context.get("life_state"),
        )

        publishing_plan = self.publishing_plan_engine.generate(package)

        self.wardrobe.persist()
        self.wardrobe_brain.apply_daily_strategy(context, outfit.item_ids)
        self.state.save_content_package(package)
        self.state.append_history(package)
        if hasattr(self.state, "append_content_moment_memory"):
            for scene in package.scenes:
                self.state.append_content_moment_memory(
                    {
                        "date": package.date.isoformat(),
                        "city": package.city,
                        "day_type": package.day_type,
                        "scene_moment": getattr(scene, "scene_moment", ""),
                        "scene_moment_type": getattr(scene, "scene_moment_type", ""),
                        "moment_signature": getattr(scene, "moment_signature", ""),
                        "visual_focus": getattr(scene, "visual_focus", ""),
                        "scene_source": getattr(scene, "scene_source", ""),
                    }
                )
        self.state.append_daily_calendar(package)
        if hasattr(self.state, "append_life_state"):
            self.state.append_life_state(package)
        self.asset_engine.run(package)
        self.state.ensure_city_exists(package)
        self.state.save_run_log("success", f"Generated package for {package.date} in {package.city}")
        if publishing_plan:
            self.telegram_delivery_service.send_daily_plan(package, publishing_plan)
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
