from types import SimpleNamespace

import pytest

from virtual_persona.models.domain import BehaviorState
from virtual_persona.pipeline.outfit_generator import ManualOutfitValidationError, OutfitGenerator


def _scene(**overrides):
    base = {
        "location": "city street",
        "description": "Morning walk through the city",
        "scene_moment": "Morning walk through the city",
        "activity": "walking",
        "time_of_day": "morning",
        "mood": "calm",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _context(**overrides):
    base = {
        "city": "Paris",
        "day_type": "day_off",
        "weather": SimpleNamespace(temp_c=17, condition="cloudy"),
    }
    base.update(overrides)
    return base


def test_generator_builds_contextual_realistic_airport_outfit():
    generator = OutfitGenerator()
    behavior = BehaviorState(
        energy_level="medium",
        social_mode="light_public",
        emotional_arc="transition",
        habit="packing",
        place_anchor="terminal_gate",
        objects=["carry_on", "bag"],
        self_presentation="transitional",
    )

    outfit = generator.generate(
        outfit_summary="",
        scene=_scene(location="airport terminal", description="Walking to the gate", scene_moment="Walking to the gate"),
        context=_context(day_type="travel_day", behavior_context=None, behavioral_context=behavior),
    )

    assert "carry on" not in outfit
    assert "bag" in outfit
    assert "sneakers" in outfit or "boots" in outfit
    assert "jacket" in outfit or "coat" in outfit or "layer" in outfit
    assert "." not in outfit


def test_generator_supports_bold_mode_without_explicit_language():
    generator = OutfitGenerator()

    outfit = generator.generate(
        outfit_summary="",
        scene=_scene(location="hotel room", description="Quiet hotel evening", scene_moment="Quiet hotel evening", time_of_day="evening"),
        context=_context(style_intensity="bold", outfit_style="bold_minimal", weather=SimpleNamespace(temp_c=24, condition="clear")),
    )

    assert "fitted" in outfit or "open neckline" in outfit or "body lines" in outfit
    assert "sexy" not in outfit.lower()
    assert "lingerie" not in outfit.lower()


def test_manual_override_validation_rejects_cyrillic_and_periods():
    generator = OutfitGenerator()

    with pytest.raises(ManualOutfitValidationError):
        generator.validate_manual_outfit("мягкий кардиган, джинсы")

    with pytest.raises(ManualOutfitValidationError):
        generator.validate_manual_outfit("soft knit top, jeans.")


def test_manual_override_is_returned_as_is_when_valid():
    generator = OutfitGenerator()
    scene = _scene(outfit_override="soft knit top, straight jeans, white sneakers, small shoulder bag")

    outfit = generator.generate(outfit_summary="", scene=scene, context=_context())
    bundle = generator.generate_bundle(outfit_summary="", scene=scene, context=_context())

    assert outfit == "soft knit top, straight jeans, white sneakers, small shoulder bag"
    assert bundle.outfit_sentence == outfit
