from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from virtual_persona.llm.provider import BaseLLMProvider
from virtual_persona.models.domain import DayScene, GeneratedContent


class ContentGenerator:
    def __init__(self, provider: BaseLLMProvider, template_path: str = "config/prompt_templates.example.json") -> None:
        with Path(template_path).open("r", encoding="utf-8") as f:
            self.templates = json.load(f)
        self.provider = provider

    def generate(self, context: Dict, scenes: List[DayScene], outfit_summary: str) -> GeneratedContent:
        char = context["character"]
        weather = context["weather"]
        city = context["city"]

        photo_prompts = []
        video_prompts = []
        story_lines = []
        for scene in scenes:
            mapping = {
                "character_name": char.name,
                "appearance_anchor": f"long {char.appearance.hair_color} hair, {char.appearance.eye_color} eyes, fair skin with freckles",
                "scene_description": scene.description,
                "city": city,
                "weather_description": f"{weather.condition}, {weather.temp_c}C",
                "lighting": self._lighting_from_scene(scene.time_of_day),
                "outfit_summary": outfit_summary,
                "day_mood": scene.mood,
                "short_story": scene.description,
                "time_of_day": scene.time_of_day,
                "story_line": scene.description,
            }
            photo_prompts.append(self.provider.generate(self.templates["photo_prompt"].format(**mapping)))
            video_prompts.append(self.provider.generate(self.templates["video_prompt"].format(**mapping)))
            story_lines.append(self.templates["story_caption"].format(**mapping))

        post = self.templates["post_caption"].format(
            city=city,
            day_mood=scenes[-1].mood,
            short_story=" → ".join(scene.description for scene in scenes),
        )

        return GeneratedContent(
            post_caption=self.provider.generate(post),
            story_lines=story_lines,
            photo_prompts=photo_prompts,
            video_prompts=video_prompts,
            publish_windows=["08:30", "13:00", "19:30"],
            creative_notes=["Keep visual continuity of face/hair unchanged.", "Disclose virtual AI character in profile/post context."],
        )

    @staticmethod
    def _lighting_from_scene(time_of_day: str) -> str:
        return {
            "morning": "soft morning light",
            "afternoon": "neutral daylight",
            "evening": "golden hour to warm ambient",
            "night": "city lights and interior ambient",
        }.get(time_of_day, "natural soft light")
