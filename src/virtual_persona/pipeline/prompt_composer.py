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

        base_parts: List[str] = [
            blocks.get("identity_base", "Alina Volkova, 22 y.o. Russian-speaking flight attendant based in Prague."),
            blocks.get("visual_identity_rules", "Keep identity stable: same facial structure, hair, natural makeup."),
            blocks.get("realism_rules", "Photorealistic, natural skin texture, no glossy luxury influencer vibe."),
            blocks.get("continuity_rules", "Respect city/day continuity and realistic aviation routine."),
        ]

        scene_desc = getattr(scene, "description", "daily lifestyle moment")
        scene_activity = getattr(scene, "activity", "")
        scene_source = getattr(scene, "source", "library")
        outfit_ids = ",".join(outfit_item_ids or [])
        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_mood = getattr(scene, "mood", "calm")
        scene_part = (
            f"Scene: {scene_desc}. Location: {scene_loc}. Mood: {scene_mood}. "
            f"Activity: {scene_activity}. Scene source: {scene_source}. "
            f"Outfit: {outfit_summary}. Outfit items: {outfit_ids}. City: {context.get('city')}"
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
