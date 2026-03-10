from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any

from virtual_persona.llm.provider import BaseLLMProvider
from virtual_persona.models.domain import DayScene, GeneratedContent


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

    def generate(self, context: Dict, scenes: List[DayScene], outfit_summary: str) -> GeneratedContent:
        char = context["character"]
        weather = context["weather"]
        city = context["city"]
        day_type = context["day_type"]

        photo_prompts: List[str] = []
        video_prompts: List[str] = []
        story_lines: List[str] = []

        weather_text = f"{weather.condition}, {weather.temp_c}C"
        short_story = " → ".join(scene.description for scene in scenes)

        for scene in scenes:
            scene_description = scene.description
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
                "lighting": self._safe(lighting),
                "visual_style": "realistic lifestyle content",
                "activity_context": self._safe(scene_description),
                "location_context": self._safe(city),
                "wardrobe_context": self._safe(outfit_summary),
                "mood_context": self._safe(mood),
                "time_context": self._safe(time_of_day),
                "short_story": self._safe(scene_description),
                "story_line": self._safe(scene_description),
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

            photo_prompt_text = photo_template.format(**mapping)
            video_prompt_text = video_template.format(**mapping)
            story_text = story_template.format(**mapping)

            photo_prompts.append(self.provider.generate(photo_prompt_text))
            video_prompts.append(self.provider.generate(video_prompt_text))
            story_lines.append(story_text)

        post_template = self._get_template("caption_instagram_medium", "post_caption")
        if not post_template:
            post_template = "{city} diary • {day_mood}. {short_story}"

        post_mapping = {
            "city": self._safe(city),
            "country": "",
            "day_type": self._safe(day_type),
            "day_mood": self._safe(scenes[-1].mood if scenes else "calm"),
            "scene_description": self._safe(short_story),
            "short_story": self._safe(short_story),
            "mood": self._safe(scenes[-1].mood if scenes else "calm"),
            "weather": self._safe(weather_text),
            "outfit": self._safe(outfit_summary),
            "time_block": self._safe(scenes[-1].time_of_day if scenes else "day"),
            "time_of_day": self._safe(scenes[-1].time_of_day if scenes else "day"),
            "location": self._safe(scenes[-1].location if scenes else city),
        }

        post_caption = self.provider.generate(post_template.format(**post_mapping))

        return GeneratedContent(
            post_caption=post_caption,
            story_lines=story_lines,
            photo_prompts=photo_prompts,
            video_prompts=video_prompts,
            publish_windows=["08:30", "13:00", "19:30"],
            creative_notes=[
                "Keep visual continuity of face and hair unchanged.",
                "Character lifestyle must remain realistic and coherent.",
            ],
        )

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