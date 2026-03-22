from virtual_persona.llm.provider import TemplateFallbackProvider
from virtual_persona.models.domain import BehaviorState, DayScene
from virtual_persona.pipeline.content_generator import ContentGenerator


class DummyState:
    def load_prompt_templates(self):
        return {}

    def load_prompt_blocks(self):
        return {}


class Character:
    name = "Alina"
    age = 22


class Weather:
    condition = "cloudy"
    temp_c = 12


class Narrative:
    narrative_phase = "transition_phase"
    energy_state = "medium"


def test_behavior_influences_caption_and_prompt():
    generator = ContentGenerator(TemplateFallbackProvider(), DummyState())
    behavior = BehaviorState(
        energy_level="low",
        social_mode="alone",
        emotional_arc="transition",
        habit="coffee_moment",
        place_anchor="kitchen_corner",
        objects=["coffee_cup", "bag"],
        self_presentation="relaxed",
    )
    scene = DayScene(
        block="morning",
        location="home kitchen",
        description="Quiet kitchen pause",
        mood="calm",
        time_of_day="morning",
        activity="waiting",
    )
    scene.scene_moment = "Coffee before leaving home"
    scene.visual_focus = "coffee cup in hand"

    content = generator.generate(
        {
            "character": Character(),
            "weather": Weather(),
            "city": "Paris",
            "day_type": "travel_day",
            "narrative_context": Narrative(),
            "behavioral_context": behavior,
            "character_profile": {},
            "persona_voice": {},
        },
        [scene],
        "cream cardigan, denim",
        ["top_1"],
    )

    assert "Coffee first" in content.post_caption
    assert "in-between" in content.post_caption
    assert "holding cup naturally" in content.photo_prompts[0].lower()
    assert "coffee cup" in content.photo_prompts[0].lower()
    assert "bag" in content.photo_prompts[0].lower()
