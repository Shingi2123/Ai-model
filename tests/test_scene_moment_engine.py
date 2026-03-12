from datetime import date

from virtual_persona.models.domain import DayScene
from virtual_persona.pipeline.content_generator import ContentGenerator
from virtual_persona.pipeline.scene_moment_engine import SceneMomentGenerator


class DummyProvider:
    def generate(self, prompt: str) -> str:
        return prompt


class DummyState:
    def __init__(self, recent=None):
        self._recent = recent or []

    def load_prompt_templates(self):
        return {}

    def load_prompt_blocks(self):
        return {}

    def load_content_moment_memory(self):
        return self._recent


def build_context(day_type: str = "work_day"):
    return {
        "date": date(2026, 1, 10),
        "city": "Prague",
        "day_type": day_type,
        "recent_history": [],
        "recent_moment_memory": [],
        "character": type("C", (), {"name": "Alina", "age": 22})(),
        "weather": type("W", (), {"condition": "clear", "temp_c": 18})(),
        "narrative_context": type("N", (), {"narrative_phase": "work_focus_phase", "energy_state": "medium"})(),
        "story_arc": {"arc_type": "travel_phase", "title": "Flights", "progress": 30},
        "persona_voice": {"reflection": 0.8, "self_irony": 0.2},
    }


def test_scene_moment_generator_deduplicates_by_signature():
    scene = DayScene("morning", "airport terminal", "Early airport routine before flight", "focused", "morning")
    context = build_context("work_day")

    existing_sig = "work_day|airport terminal|morning|coffee_window_moment|coffee cup in hand, runway view through glass"
    context["recent_moment_memory"] = [{"date": "2026-01-09", "moment_signature": existing_sig}]

    generator = SceneMomentGenerator(DummyState())
    enriched = generator.generate_for_scene(context, scene)

    assert enriched.scene_moment
    assert enriched.moment_signature != existing_sig
    assert "terminal" in enriched.scene_moment.lower() or "airport" in enriched.scene_moment.lower()


def test_same_day_scene_can_produce_different_moment_with_memory_shift():
    base_scene = DayScene("morning", "airport terminal", "Early airport routine before flight", "focused", "morning")
    context = build_context("work_day")
    generator = SceneMomentGenerator(DummyState())

    first = generator.generate_for_scene(context, base_scene)

    next_scene = DayScene("morning", "airport terminal", "Early airport routine before flight", "focused", "morning")
    context["recent_moment_memory"] = [{"date": "2026-01-09", "moment_signature": first.moment_signature}]
    second = generator.generate_for_scene(context, next_scene)

    assert first.scene_moment != second.scene_moment


def test_content_generator_uses_scene_moment_instead_of_raw_scene_description():
    state = DummyState()
    generator = ContentGenerator(DummyProvider(), state_store=state)
    scene = DayScene(
        "morning",
        "airport terminal",
        "Early airport routine before flight",
        "focused",
        "morning",
        activity="pre_flight",
        scene_moment="Quiet coffee at the gate before boarding",
        scene_moment_type="gate_waiting_moment",
        scene_source="generated",
        moment_signature="sig-1",
        visual_focus="coffee cup and runway",
    )
    context = build_context("work_day")

    content = generator.generate(context, [scene], "navy coat and white shirt", ["coat_1"])

    assert "Quiet coffee at the gate before boarding" in content.photo_prompts[0]
    assert "Early airport routine before flight" not in content.photo_prompts[0]
    assert "coffee cup and runway" in content.post_caption


def test_moment_signature_normalization_keeps_stable_canonical_form():
    generator = SceneMomentGenerator(DummyState())

    normalized = generator.normalize_signature(" Work_Day | Airport Terminal | Morning | Gate waiting moment | Calm waiting at the gate!!! ")

    assert normalized == "work day|airport terminal|morning|gate waiting moment|calm waiting at gate"


def test_generate_prefers_archetype_diversity_inside_one_day():
    generator = SceneMomentGenerator(DummyState())
    context = build_context("travel_day")
    scenes = [
        DayScene("morning", "airport terminal", "a", "focused", "morning"),
        DayScene("day", "hotel room", "b", "calm", "day"),
        DayScene("evening", "city street", "c", "curious", "evening"),
    ]

    enriched = generator.generate(context, scenes)

    archetypes = [scene.scene_moment_type for scene in enriched]
    assert len(archetypes) == len(set(archetypes))


def test_content_generator_applies_persona_voice_tone_profile():
    state = DummyState()
    generator = ContentGenerator(DummyProvider(), state_store=state)
    scene = DayScene("morning", "city street", "Morning routine", "calm", "morning", scene_moment="morning city walk")
    context = build_context("travel_day")

    content = generator.generate(context, [scene], "beige coat", ["coat_1"])

    assert any(note.startswith("caption_tone=observational_travel") for note in content.creative_notes)
