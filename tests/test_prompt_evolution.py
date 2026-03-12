from virtual_persona.pipeline.prompt_composer import PromptComposer


class DummyState:
    def load_prompt_blocks(self):
        return {}


class Scene:
    description = "Morning walk"
    activity = "city_walk"
    source = "generated"
    location = "city center"
    mood = "curious"


class LifeState:
    day_type = "day_off"
    season = "spring"
    fatigue_level = 3


class Narrative:
    narrative_phase = "creative_phase"
    energy_state = "high"
    rhythm_state = "dynamic"
    novelty_pressure = 0.7


def test_prompt_includes_story_arc_context():
    composer = PromptComposer(DummyState())
    context = {
        "city": "Prague",
        "life_state": LifeState(),
        "narrative_context": Narrative(),
        "story_arc": {"arc_type": "creative_phase", "title": "Creative month", "progress": 40},
    }

    prompt = composer.compose(context, Scene(), "soft casual", "photo", ["top_1"])

    assert "Story arc" in prompt
    assert "creative_phase" in prompt
    assert "city_walk" in prompt


def test_prompt_has_structured_visual_blocks_and_continuity_cues():
    composer = PromptComposer(DummyState())
    context = {
        "city": "Paris",
        "life_state": LifeState(),
        "narrative_context": Narrative(),
        "story_arc": {"arc_type": "creative_phase", "title": "Creative month", "progress": 40},
        "continuity_context": {"arc_hint": "arrival_and_adaptation", "previous_evening_moment": "hotel check-in"},
        "persona_voice": {"restraint": 0.8, "reflection": 0.7, "self_irony": 0.2},
    }

    prompt = composer.compose(context, Scene(), "soft casual", "photo", ["top_1"])

    assert "Subject:" in prompt
    assert "Setting:" in prompt
    assert "Wardrobe:" in prompt
    assert "Continuity cues:" in prompt
    assert "Haussmann" in prompt
