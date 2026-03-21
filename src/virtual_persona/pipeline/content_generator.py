from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any

from virtual_persona.llm.provider import BaseLLMProvider
from virtual_persona.models.domain import DayScene, GeneratedContent
from virtual_persona.pipeline.prompt_composer import PromptComposer
from virtual_persona.pipeline.provider_prompt_formatter import ReferenceAwarePromptFormatter


class ContentGenerator:
    def __init__(
        self,
        provider: BaseLLMProvider,
        state_store=None,
        template_path: str = "config/prompt_templates.example.json",
    ) -> None:
        self.provider = provider
        self.state_store = state_store
        self.template_path = template_path
        self.templates = self._load_templates()
        self.prompt_composer = PromptComposer(state_store)
        self.prompt_formatter = ReferenceAwarePromptFormatter()

    def _load_templates(self) -> Dict[str, str]:
        if self.state_store and hasattr(self.state_store, "load_prompt_templates"):
            try:
                templates = self.state_store.load_prompt_templates() or {}
                if templates:
                    return templates
            except Exception:
                pass

        with Path(self.template_path).open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _safe(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value)

    def _get_template(self, primary_key: str, fallback_key: str = "") -> str:
        if primary_key in self.templates:
            return self.templates[primary_key]
        if fallback_key and fallback_key in self.templates:
            return self.templates[fallback_key]
        return ""

    def generate(self, context: Dict, scenes: List[DayScene], outfit_summary: str, outfit_item_ids: List[str] | None = None) -> GeneratedContent:
        char = context["character"]
        weather = context["weather"]
        city = context["city"]
        day_type = context["day_type"]
        narrative = context.get("narrative_context")
        behavior = context.get("behavioral_context")
        daily_behavior = getattr(behavior, "daily_state", None)

        photo_prompts: List[str] = []
        video_prompts: List[str] = []
        story_lines: List[str] = []
        prompt_packages: List[Dict[str, Any]] = []

        weather_text = f"{weather.condition}, {weather.temp_c}C"
        short_story = " → ".join((scene.scene_moment or scene.description) for scene in scenes)
        outfit_item_ids = outfit_item_ids or []

        for scene in scenes:
            scene_description = scene.scene_moment or scene.description
            mood = scene.mood
            time_of_day = scene.time_of_day
            location = scene.location
            lighting = self._lighting_from_scene(time_of_day)

            mapping = {
                "character_name": self._safe(char.name),
                "age": self._safe(getattr(char, "age", 22)),
                "city": self._safe(city),
                "country": "",
                "day_type": self._safe(day_type),
                "scene_description": self._safe(scene_description),
                "mood": self._safe(mood),
                "time_block": self._safe(time_of_day),
                "time_of_day": self._safe(time_of_day),
                "location": self._safe(location),
                "weather": self._safe(weather_text),
                "weather_description": self._safe(weather_text),
                "temperature": self._safe(weather.temp_c),
                "outfit": self._safe(outfit_summary),
                "outfit_summary": self._safe(outfit_summary),
                "outfit_item_ids": self._safe(",".join(outfit_item_ids)),
                "activity": self._safe(getattr(scene, "activity", "")),
                "scene_source": self._safe(getattr(scene, "scene_source", getattr(scene, "source", "library"))),
                "scene_moment": self._safe(getattr(scene, "scene_moment", scene_description)),
                "scene_moment_type": self._safe(getattr(scene, "scene_moment_type", "")),
                "moment_signature": self._safe(getattr(scene, "moment_signature", "")),
                "moment_reason": self._safe(getattr(scene, "moment_reason", "")),
                "visual_focus": self._safe(getattr(scene, "visual_focus", "")),
                "lighting": self._safe(lighting),
                "visual_style": "realistic lifestyle content",
                "activity_context": self._safe(scene_description),
                "continuity_hints": self._safe(getattr(scene, "moment_signature", "")),
                "location_context": self._safe(city),
                "wardrobe_context": self._safe(outfit_summary),
                "mood_context": self._safe(mood),
                "time_context": self._safe(time_of_day),
                "short_story": self._safe(scene_description),
                "story_line": self._safe(scene_description),
                "narrative_phase": self._safe(getattr(narrative, "narrative_phase", "routine_stability") if narrative else "routine_stability"),
                "energy_state": self._safe(getattr(narrative, "energy_state", "medium") if narrative else "medium"),
                "emotional_arc": self._safe(getattr(behavior, "emotional_arc", "")),
                "behavior_habit": self._safe(getattr(behavior, "selected_habit", "")),
                "behavior_habit_family": self._safe(getattr(behavior, "habit_family", "")),
                "familiar_place_anchor": self._safe(getattr(behavior, "familiar_place_anchor", "")),
                "familiar_place_label": self._safe(getattr(behavior, "familiar_place_label", "")),
                "recurring_objects": self._safe(", ".join(getattr(behavior, "recurring_objects", []) or [])),
                "self_presentation_mode": self._safe(getattr(daily_behavior, "self_presentation_mode", "") if daily_behavior else ""),
                "social_presence_mode": self._safe(getattr(daily_behavior, "social_presence_mode", "") if daily_behavior else ""),
                "transition_hint": self._safe(getattr(behavior, "transition_hint", "")),
            }

            # фото-промпт
            if location in ("airport", "aircraft", "airport terminal"):
                photo_template = self._get_template("photo_prompt_airport", "photo_prompt")
            elif "hotel" in location:
                photo_template = self._get_template("photo_prompt_hotel", "photo_prompt")
            elif location in ("home", "bedroom", "living_room", "home_kitchen"):
                photo_template = self._get_template("photo_prompt_home", "photo_prompt")
            else:
                photo_template = self._get_template("photo_prompt_city", "photo_prompt")

            if not photo_template:
                photo_template = (
                    "Realistic lifestyle photo of {character_name} in {city}, "
                    "{scene_description}, outfit: {outfit_summary}, weather: {weather_description}, "
                    "lighting: {lighting}, mood: {mood}."
                )

            # видео-промпт
            video_template = self._get_template("video_prompt_reel", "video_prompt")
            if not video_template:
                video_template = (
                    "Short realistic lifestyle video of {character_name} in {city}, "
                    "{scene_description}, outfit: {outfit_summary}, mood: {mood}, "
                    "time of day: {time_of_day}."
                )

            # сторис
            story_template = self._get_template("story_text_soft", "story_caption")
            if not story_template:
                story_template = "{story_line}"

            photo_package = self.prompt_composer.compose_package(context, scene, outfit_summary, 'photo', outfit_item_ids)
            video_package = self.prompt_composer.compose_package(context, scene, outfit_summary, 'video', outfit_item_ids)
            story_package = self.prompt_composer.compose_package(context, scene, outfit_summary, 'story', outfit_item_ids)

            photo_prompt_text = photo_package["final_prompt"]
            if scene_description and scene_description not in photo_prompt_text:
                photo_prompt_text = f"{scene_description}. {photo_prompt_text}"
            video_prompt_text = video_package["final_prompt"]
            if scene_description and scene_description not in video_prompt_text:
                video_prompt_text = f"{scene_description}. {video_prompt_text}"
            story_text = f"{story_package['final_prompt']} {self._safe_format(story_template, mapping)}"

            photo_prompts.append(photo_prompt_text)
            video_prompts.append(video_prompt_text)
            story_lines.append(self.provider.generate(story_text))
            prompt_packages.append({
                "scene_index": len(prompt_packages),
                "scene_moment": scene_description,
                "photo": photo_package,
                "video": {**video_package, "video_prompt_package": {"subject_identity": video_package.get("identity_anchor", ""), "motion": video_package.get("video_motion", ""), "camera_motion": video_package.get("video_camera_motion", ""), "scene_continuity": video_package.get("continuity_block", ""), "tempo": "calm social pace", "micro_expression_constraints": "keep habitual expression signature"}},
                "story": story_package,
            })

        post_template = self._get_template("caption_instagram_medium", "post_caption")
        if not post_template:
            post_template = "{city} diary • {day_mood}. {short_story}"

        post_mapping = {
            "city": self._safe(city),
            "country": "",
            "day_type": self._safe(day_type),
            "day_mood": self._safe(scenes[-1].mood if scenes else "calm"),
            "scene_description": self._safe(short_story),
            "scene_moment": self._safe(scenes[-1].scene_moment if scenes else short_story),
            "visual_focus": self._safe(scenes[-1].visual_focus if scenes else ""),
            "short_story": self._safe(short_story),
            "mood": self._safe(scenes[-1].mood if scenes else "calm"),
            "weather": self._safe(weather_text),
            "outfit": self._safe(outfit_summary),
            "time_block": self._safe(scenes[-1].time_of_day if scenes else "day"),
            "time_of_day": self._safe(scenes[-1].time_of_day if scenes else "day"),
            "location": self._safe(scenes[-1].location if scenes else city),
            "emotional_arc": self._safe(getattr(behavior, "emotional_arc", "")),
            "behavior_habit": self._safe(getattr(behavior, "selected_habit", "")),
            "behavior_habit_family": self._safe(getattr(behavior, "habit_family", "")),
            "familiar_place_anchor": self._safe(getattr(behavior, "familiar_place_anchor", "")),
            "familiar_place_label": self._safe(getattr(behavior, "familiar_place_label", "")),
        }

        tone_profile = self._select_caption_tone(context, scenes)
        opening_guard = ", ".join(getattr(behavior, "caption_opening_guard", []) or [])
        transition_hint = self._safe(getattr(behavior, "transition_hint", ""))
        social_hint = self._safe(getattr(behavior, "social_context_hint", ""))
        caption_prompt = (
            f"{self.prompt_composer.compose(context, scenes[-1] if scenes else None, outfit_summary, 'caption', outfit_item_ids)} "
            f"Tone profile: {tone_profile}. Emotional arc={post_mapping.get('emotional_arc', '')}. Habit hint={post_mapping.get('behavior_habit', '')}. "
            f"Familiar place anchor={post_mapping.get('familiar_place_anchor', '')}. Visual focus={post_mapping.get('visual_focus', '')}. "
            f"Transition hint={transition_hint}. Social context={social_hint}. Avoid caption openings similar to: {opening_guard}. "
            "Avoid generic AI phrasing, keep natural social media voice, no literal prompt retelling. Keep the voice restrained, lightly reflective, recognizably the same person across days, and never overly literary or dramatic. "
            f"{self._safe_format(post_template, post_mapping)}"
        )
        post_caption = self.provider.generate(caption_prompt)

        return GeneratedContent(
            post_caption=post_caption,
            story_lines=story_lines,
            photo_prompts=photo_prompts,
            video_prompts=video_prompts,
            publish_windows=["08:30", "13:00", "19:30"],
            creative_notes=[
                "Keep visual continuity of face and hair unchanged.",
                "Character lifestyle must remain realistic and coherent.",
                f"caption_tone={tone_profile}",
                f"emotional_arc={getattr(behavior, 'emotional_arc', '')}",
                f"habit={getattr(behavior, 'selected_habit', '')}",
                f"habit_family={getattr(behavior, 'habit_family', '')}",
                f"social_context={getattr(behavior, 'social_context_hint', '')}",
            ],
            prompt_packages=prompt_packages,
        )

    @staticmethod
    def _select_caption_tone(context: Dict[str, Any], scenes: List[DayScene]) -> str:
        day_type = str(context.get("day_type") or "")
        voice = context.get("persona_voice") or {}
        behavior = context.get("behavioral_context")
        daily_behavior = getattr(behavior, "daily_state", None)
        reflection = float(voice.get("reflection", 0.65))
        self_irony = float(voice.get("self_irony", 0.3))
        if day_type in {"travel_day", "airport_transfer"}:
            base = "observational_travel"
        elif day_type in {"work_day"}:
            base = "grounded_workday"
        elif day_type in {"day_off", "weekend_day"}:
            base = "cozy_diary"
        else:
            base = "quiet_lifestyle"
        if any("evening" in (s.time_of_day or "") for s in scenes) and reflection > 0.6:
            base += "+reflective"
        if self_irony > 0.45:
            base += "+light_irony"
        if daily_behavior and getattr(daily_behavior, "caption_voice_mode", ""):
            base += f"+{daily_behavior.caption_voice_mode}"
        return base

    @staticmethod
    def _lighting_from_scene(time_of_day: str) -> str:
        return {
            "early_morning": "soft early morning light",
            "morning": "soft morning light",
            "late_morning": "clear late morning daylight",
            "noon": "bright midday light",
            "afternoon": "neutral daylight",
            "golden_hour": "golden hour warm light",
            "evening": "warm evening ambient light",
            "night": "city lights and interior ambient",
        }.get(time_of_day, "natural soft light")

    @staticmethod
    def _safe_format(template: str, mapping: Dict[str, Any]) -> str:
        class _SafeDict(dict):
            def __missing__(self, key):
                return ""

        return template.format_map(_SafeDict(mapping))
