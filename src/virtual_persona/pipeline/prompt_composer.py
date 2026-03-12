from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PromptComposer:
    state_store: Any

    def load_blocks(self) -> Dict[str, str]:
        if self.state_store and hasattr(self.state_store, "load_prompt_blocks"):
            try:
                blocks = self.state_store.load_prompt_blocks() or {}
                if blocks:
                    return blocks
            except Exception:
                pass
        return {}

    def compose(self, context: Dict[str, Any], scene: Any, outfit_summary: str, content_type: str, outfit_item_ids: List[str] | None = None) -> str:
        blocks = self.load_blocks()
        life_state = context.get("life_state")
        narrative = context.get("narrative_context")
        story_arc = context.get("story_arc") or {}

        base_parts: List[str] = [
            blocks.get("identity_base", "Alina Volkova, 22 y.o. Russian-speaking flight attendant based in Prague."),
            blocks.get("visual_identity_rules", "Keep identity stable: same facial structure, hair, natural makeup."),
            blocks.get("realism_rules", "Photorealistic, natural skin texture, no glossy luxury influencer vibe."),
            blocks.get("continuity_rules", "Respect city/day continuity and realistic aviation routine."),
        ]

        scene_desc = getattr(scene, "scene_moment", "") or getattr(scene, "description", "daily lifestyle moment")
        scene_activity = getattr(scene, "activity", "")
        scene_source = getattr(scene, "scene_source", "") or getattr(scene, "source", "library")
        outfit_ids = ",".join(outfit_item_ids or [])
        scene_loc = getattr(scene, "location", context.get("city", "city"))
        visual_focus = getattr(scene, "visual_focus", "")
        moment_signature = getattr(scene, "moment_signature", "")
        moment_type = getattr(scene, "scene_moment_type", "")
        scene_mood = getattr(scene, "mood", "calm")
        continuity = context.get("continuity_context") or {}
        persona_voice = context.get("persona_voice") or {}
        city_ambience = self._city_ambience(str(context.get("city") or ""))
        scene_part = (
            f"Subject: recurring character identity preserved, same person as prior days. "
            f"Setting: {scene_loc} in {context.get('city')}. {city_ambience}. "
            f"Action: {scene_desc}; activity={scene_activity}. "
            f"Wardrobe: {outfit_summary}. Outfit item ids: {outfit_ids}. "
            f"Mood: {scene_mood}. Composition: focus on {visual_focus or 'natural focal detail'}, layered foreground/background, candid framing. "
            f"Lighting: realistic {self._lighting_hint(getattr(scene, 'time_of_day', 'day'))}. "
            f"Realism cues: no glamour overprocessing, plausible textures and weather response. "
            f"Continuity cues: arc_hint={continuity.get('arc_hint', 'stable_routine')}; previous_evening={continuity.get('previous_evening_moment', '')}; "
            f"moment_type={moment_type}; signature={moment_signature}; scene_source={scene_source}. "
            f"Persona voice cues: restraint={persona_voice.get('restraint', 0.7)}, reflection={persona_voice.get('reflection', 0.65)}, self_irony={persona_voice.get('self_irony', 0.3)}."
        )

        if life_state:
            scene_part += (
                f". Day type: {life_state.day_type}. Season: {life_state.season}. "
                f"Fatigue: {life_state.fatigue_level}/10"
            )
        if narrative:
            scene_part += (
                f". Narrative phase: {getattr(narrative, 'narrative_phase', 'routine_stability')}."
                f" Energy: {getattr(narrative, 'energy_state', 'medium')}."
                f" Rhythm: {getattr(narrative, 'rhythm_state', 'stable')}."
                f" Novelty pressure: {getattr(narrative, 'novelty_pressure', 0)}"
            )
        if story_arc:
            scene_part += (
                f". Story arc: {story_arc.get('arc_type', '')}."
                f" Arc title: {story_arc.get('title', '')}."
                f" Arc progress: {story_arc.get('progress', 0)}"
            )

        recent_outfits = context.get("recent_outfit_memory") or []
        if recent_outfits:
            last_outfit = recent_outfits[-1]
            scene_part += f". Recent outfit memory: {last_outfit.get('item_ids', '')}"

        recent_scenes = context.get("recent_scene_memory") or []
        if recent_scenes:
            top_scene = recent_scenes[0]
            scene_part += f". Scene continuity: last scene {top_scene.get('scene_id', '')} used {top_scene.get('last_used', '')}"

        recent_activities = context.get("recent_activity_memory") or []
        if recent_activities:
            top_activity = recent_activities[0]
            scene_part += f". Activity continuity: {top_activity.get('activity_id', '')} on {top_activity.get('last_used', '')}"

        type_rules = {
            "photo": blocks.get("photo_base_rules", "Natural lifestyle photo, soft light, believable composition."),
            "video": blocks.get("video_base_rules", "Short lifestyle video, subtle motion, documentary realism."),
            "caption": blocks.get("caption_style_rules", "Soft, concise, human tone, no over-poetic wording."),
            "story": blocks.get("story_style_rules", "Short and warm, like real IG stories."),
        }

        return " ".join([part for part in [*base_parts, type_rules.get(content_type, ""), scene_part] if part])

    @staticmethod
    def _lighting_hint(time_of_day: str) -> str:
        return {
            "early_morning": "cool early morning light",
            "morning": "soft morning daylight",
            "late_morning": "clean late-morning daylight",
            "noon": "bright overhead daylight",
            "afternoon": "neutral afternoon light",
            "golden_hour": "warm directional golden hour light",
            "evening": "warm evening ambient light",
            "night": "mixed city and practical interior light",
        }.get(str(time_of_day or "").lower(), "natural soft light")

    @staticmethod
    def _city_ambience(city: str) -> str:
        normalized = city.strip().lower()
        known = {
            "paris": "Haussmann facades, compact sidewalk cafes, layered warm street glow",
            "prague": "historic stone facades, tram rhythm, river-side muted palette",
            "rome": "textured warm walls, scooters and piazza flow, afternoon contrast",
            "london": "brick streets, overcast diffusion, restrained business-casual crowd",
        }
        return known.get(normalized, "city-specific rhythm, local architecture and transport cues")
