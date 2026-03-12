from __future__ import annotations

from datetime import datetime, date

from virtual_persona.config.settings import AppSettings
from virtual_persona.delivery.formatter import package_to_markdown
from virtual_persona.delivery.telegram_bot import TelegramDelivery
from virtual_persona.delivery.telegram_delivery_service import TelegramDeliveryService
from virtual_persona.llm.provider import OpenAIProvider, TemplateFallbackProvider
from virtual_persona.models.domain import DailyPackage, GeneratedContent, OutfitSelection, PublishingPlanItem, SunSnapshot, WeatherSnapshot
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
    def __init__(self, settings: AppSettings, mode: str = "full") -> None:
        self.settings = settings
        self.mode = mode
        self.state = build_state_store(settings, mode=mode)
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

    def _load_frozen_day(self, target_date: date) -> DailyPackage | None:
        if not hasattr(self.state, "load_publishing_plan"):
            return None
        rows = self.state.load_publishing_plan(target_date.isoformat()) or []
        if not rows:
            return None
        city = str(rows[0].get("city") or "Unknown")
        day_type = str(rows[0].get("day_type") or "work_day")
        scene_text = " | ".join(str(r.get("scene_moment") or "") for r in rows if r.get("scene_moment"))
        package = DailyPackage(
            generated_at=datetime.utcnow(),
            date=target_date,
            city=city,
            day_type=day_type,
            summary=scene_text or "Frozen daily package",
            weather=WeatherSnapshot(city=city, temp_c=0, condition="unknown", humidity=0, wind_speed=0, cloudiness=0, source="persisted"),
            sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow(), source="persisted"),
            outfit=OutfitSelection(item_ids=[], summary=""),
            scenes=[],
            content=GeneratedContent(post_caption="", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
        )
        package.publishing_plan = [
            PublishingPlanItem(
                publication_id=str(r.get("publication_id") or f"{target_date.isoformat()}-{idx+1:02d}"),
                date=target_date,
                platform=str(r.get("platform") or "Instagram"),
                post_time=str(r.get("post_time") or "09:30"),
                content_type=str(r.get("content_type") or "photo"),
                city=str(r.get("city") or city),
                day_type=str(r.get("day_type") or day_type),
                narrative_phase=str(r.get("narrative_phase") or "routine_stability"),
                scene_moment=str(r.get("scene_moment") or ""),
                scene_source=str(r.get("scene_source") or ""),
                scene_moment_type=str(r.get("scene_moment_type") or ""),
                moment_signature=str(r.get("moment_signature") or ""),
                visual_focus=str(r.get("visual_focus") or ""),
                activity_type=str(r.get("activity_type") or ""),
                outfit_ids=[x.strip() for x in str(r.get("outfit_ids") or "").split(",") if x.strip()],
                prompt_type=str(r.get("prompt_type") or ""),
                prompt_text=str(r.get("prompt_text") or ""),
                caption_text=str(r.get("caption_text") or ""),
                short_caption=str(r.get("short_caption") or ""),
                post_timezone=str(r.get("post_timezone") or "UTC"),
                publish_score=float(r.get("publish_score") or 0.0),
                selection_reason=str(r.get("selection_reason") or "selected_for_publication"),
                delivery_status=str(r.get("delivery_status") or "planned"),
                notes=str(r.get("notes") or ""),
            )
            for idx, r in enumerate(rows)
        ]
        return package

    def generate_day(self, target_date: date | None = None, override_city: str | None = None, force_regenerate: bool = False) -> DailyPackage:
        target = target_date or date.today()
        if not force_regenerate:
            frozen = self._load_frozen_day(target)
            if frozen is not None:
                self.state.save_run_log("info", f"day_generation mode=reuse date={target.isoformat()} rows={len(frozen.publishing_plan)}")
                return frozen

        context = self.context_builder.build(target_date=target, override_city=override_city)
        if hasattr(self.state, "reset_day_records"):
            self.state.reset_day_records(context["date"].isoformat())


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
                        "publish_score": getattr(scene, "publish_score", ""),
                        "publish_decision": getattr(scene, "publish_decision", ""),
                        "decision_reason": getattr(scene, "decision_reason", ""),
                    }
                )
        self.state.append_daily_calendar(package)
        if hasattr(self.state, "append_life_state"):
            self.state.append_life_state(package)
        self.asset_engine.run(package)
        self.state.ensure_city_exists(package)
        mode = "regenerate" if force_regenerate else "create"
        self.state.save_run_log("success", f"day_generation mode={mode} date={package.date.isoformat()} city={package.city} scenes={len(package.scenes)} posts={len(package.publishing_plan)}")
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
