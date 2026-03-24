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

    def _canonical_outfit_sentence(self, context: Dict[str, Any], scene: DayScene | None, legacy_summary: str) -> str:
        canonical = str(context.get("outfit_sentence") or "").strip()
        if canonical:
            return self.prompt_composer._normalize_outfit_sentence_for_prompt(canonical, scene, context)

        struct = context.get("outfit_struct") or {}
        structured_sentence = str(struct.get("outfit_sentence") or struct.get("sentence") or "").strip() if isinstance(struct, dict) else ""
        if structured_sentence:
            return self.prompt_composer._normalize_outfit_sentence_for_prompt(structured_sentence, scene, context)

        cleaned_legacy = str(legacy_summary or "").strip()
        if cleaned_legacy:
            return self.prompt_composer._normalize_outfit_sentence_for_prompt(cleaned_legacy, scene, context)

        if scene is not None:
            return self.prompt_composer._contextual_outfit_fallback_sentence(scene, context)
        return self.prompt_composer._contextual_outfit_fallback_sentence(
            DayScene(block="", location=str(context.get("city") or ""), description="daily moment", mood="calm", time_of_day="day"),
            context,
        )

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
        canonical_outfit_sentence = self._canonical_outfit_sentence(context, scenes[0] if scenes else None, outfit_summary)
        if canonical_outfit_sentence:
            outfit_summary = canonical_outfit_sentence

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
                "outfit": self._safe(canonical_outfit_sentence),
                "outfit_summary": self._safe(canonical_outfit_sentence),
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
                "wardrobe_context": self._safe(canonical_outfit_sentence),
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

            photo_package = self.prompt_composer.compose_package(context, scene, canonical_outfit_sentence, 'photo', outfit_item_ids)
            video_package = self.prompt_composer.compose_package(context, scene, canonical_outfit_sentence, 'video', outfit_item_ids)
            story_package = self.prompt_composer.compose_package(context, scene, canonical_outfit_sentence, 'story', outfit_item_ids)

            photo_prompt_text = photo_package["final_prompt"]
            video_prompt_text = video_package["final_prompt"]
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

        tone_profile = self._select_caption_tone(context, scenes)
        post_caption = self._build_behavior_caption(context, scenes, city, day_type)

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
                f"habit={getattr(behavior, 'habit', getattr(behavior, 'selected_habit', ''))}",
                f"place_anchor={getattr(behavior, 'place_anchor', getattr(behavior, 'familiar_place_anchor', ''))}",
                f"social_context={getattr(behavior, 'social_context_hint', '')}",
            ],
            prompt_packages=prompt_packages,
        )

    def _build_behavior_caption(self, context: Dict[str, Any], scenes: List[DayScene], city: str, day_type: str) -> str:
        behavior = context.get("behavioral_context")
        if behavior is None:
            final_scene = scenes[-1] if scenes else None
            if final_scene is None:
                return "A quiet daily moment."
            moment = str(getattr(final_scene, "scene_moment", "") or getattr(final_scene, "description", "") or "A quiet daily moment.").strip()
            visual_focus = str(getattr(final_scene, "visual_focus", "") or "").strip()
            if visual_focus:
                return f"{moment}. {visual_focus}."
            return moment

        emotional_arc = str(getattr(behavior, "emotional_arc", "routine") or "routine")
        habit = str(getattr(behavior, "habit", getattr(behavior, "selected_habit", "none")) or "none")
        place_anchor = str(getattr(behavior, "place_anchor", getattr(behavior, "familiar_place_anchor", "")) or "")
        self_presentation = str(getattr(behavior, "self_presentation", "relaxed") or "relaxed")
        final_scene = scenes[-1] if scenes else None
        mood = str(getattr(final_scene, "mood", "calm") or "calm")

        arc_line = {
            "arrival": f"New place, slower breath, and a little time to take {city} in.",
            "routine": "Keeping the day simple and steady.",
            "reflection": "One of those quieter days that feels better when nothing is rushed.",
            "transition": "Everything feels a little in-between before the next move.",
            "departure": "Almost ready to go, just not in a hurry yet.",
        }.get(emotional_arc, "Keeping the day grounded.")
        habit_line = {
            "coffee_moment": "Coffee first always makes the rest of the day feel more possible.",
            "window_pause": "Needed a small pause by the window before continuing.",
            "packing": "Packing in small steps is still the easiest way to calm the day down.",
            "slow_walk": "A slow walk helped everything settle into place.",
            "none": "Some days work best when I keep them simple.",
        }.get(habit, "Some days work best when I keep them simple.")
        day_line = {
            "work_day": "Workday rhythm, but softer at the edges.",
            "travel_day": "Travel day logic: keep the bag close and the pace gentle.",
            "airport_transfer": "In transit again, trying to make the waiting feel lighter.",
            "day_off": "Off-duty and keeping the pace kind.",
            "layover_day": "A small pocket of time between places.",
        }.get(day_type, "Letting the day stay uncomplicated.")
        place_line = {
            "hotel_window": "The hotel window has become the easiest reset point.",
            "kitchen_corner": "The kitchen corner felt like enough of a world this morning.",
            "terminal_gate": "The gate was quieter than expected today.",
            "cafe_corner": "A cafe corner can fix more than it should.",
        }.get(place_anchor, "")
        tone_line = f"{self_presentation.capitalize()} energy, {mood} mood."

        lines = [arc_line, habit_line, day_line]
        if place_line:
            lines.append(place_line)
        lines.append(tone_line)
        return " ".join(line for line in lines if line).strip()

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
