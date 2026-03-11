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

    def compose(self, context: Dict[str, Any], scene: Any, outfit_summary: str, content_type: str) -> str:
        blocks = self.load_blocks()
        life_state = context.get("life_state")

        base_parts: List[str] = [
            blocks.get("identity_base", "Alina Volkova, 22 y.o. Russian-speaking flight attendant based in Prague."),
            blocks.get("visual_identity_rules", "Keep identity stable: same facial structure, hair, natural makeup."),
            blocks.get("realism_rules", "Photorealistic, natural skin texture, no glossy luxury influencer vibe."),
            blocks.get("continuity_rules", "Respect city/day continuity and realistic aviation routine."),
        ]

        scene_desc = getattr(scene, "description", "daily lifestyle moment")
        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_mood = getattr(scene, "mood", "calm")
        scene_part = f"Scene: {scene_desc}. Location: {scene_loc}. Mood: {scene_mood}. Outfit: {outfit_summary}. City: {context.get('city')}"

        if life_state:
            scene_part += (
                f". Day type: {life_state.day_type}. Season: {life_state.season}. "
                f"Fatigue: {life_state.fatigue_level}/10"
            )

        type_rules = {
            "photo": blocks.get("photo_base_rules", "Natural lifestyle photo, soft light, believable composition."),
            "video": blocks.get("video_base_rules", "Short lifestyle video, subtle motion, documentary realism."),
            "caption": blocks.get("caption_style_rules", "Soft, concise, human tone, no over-poetic wording."),
            "story": blocks.get("story_style_rules", "Short and warm, like real IG stories."),
        }

        return " ".join([part for part in [*base_parts, type_rules.get(content_type, ""), scene_part] if part])
