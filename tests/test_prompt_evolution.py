import pytest

from virtual_persona.pipeline.prompt_composer import PromptComposer, PromptValidationError
from virtual_persona.models.domain import BehaviorState


class DummyState:
    def load_prompt_blocks(self):
        return {}


class Scene:
    description = "Morning walk"
    activity = "city_walk"
    source = "generated"
    scene_source = "generated"
    location = "city street"
    mood = "curious"
    time_of_day = "morning"
    visual_focus = "coffee cup in hand"
    scene_moment = "Morning mirror selfie before heading out"
    scene_moment_type = "diary_mirror"
    moment_signature = "sig-1"


class LifeState:
    day_type = "day_off"
    season = "spring"
    fatigue_level = 3


class Narrative:
    narrative_phase = "creative_phase"
    energy_state = "high"
    rhythm_state = "dynamic"
    novelty_pressure = 0.7


BASE_CONTEXT = {
    "city": "Paris",
    "day_type": "day_off",
    "life_state": LifeState(),
    "narrative_context": Narrative(),
    "story_arc": {"arc_type": "creative_phase", "title": "Creative month", "progress": 40},
    "continuity_context": {
        "arc_hint": "arrival_and_adaptation",
        "previous_evening_moment": "hotel check-in",
        "camera_behavior_memory": {
            "preferred_shot_archetypes": ["candid_handheld", "friend_shot"],
            "average_camera_distance": "1.1m",
            "preferred_framing_style": "eye-level",
            "selfie_frequency": "rare",
            "candid_frequency": "frequent",
        },
    },
    "persona_voice": {"restraint": 0.8, "reflection": 0.7, "self_irony": 0.2},
    "character_profile": {
        "display_name": "Alina Volkova",
        "age": "22",
        "appearance_hair_color": "light chestnut",
        "appearance_eye_color": "green",
        "appearance_face_shape": "soft oval",
        "appearance_body_type": "slim natural build",
        "makeup_profile": "natural dewy",
        "skin_realism_profile": "natural skin texture",
        "signature_appearance_cues": "freckles and soft brows",
        "device_profile": "iPhone 16 Pro natural color profile",
        "recurring_phone_device": "graphite iPhone-class device with clear case",
        "primary_device_profile": {
            "device_class": "premium smartphone",
            "front_camera_behavior": "arm-length front camera with mild distortion",
            "rear_camera_behavior": "rear camera handheld realism",
            "processing_style": "natural contrast with mild HDR",
            "expected_lens_character": "24mm equivalent wide lens",
            "screen_mirror_visibility_rules": "mirror selfie keeps same phone silhouette",
            "night_indoor_limitations": "mild grain in dim interiors",
            "phone_shape": "graphite rounded rectangle with clear case",
        },
        "face_signature": "soft straight brows, medium-full lips, balanced eye spacing, rounded cheek contour",
        "face_shape": "soft oval",
        "nose_bridge": "straight",
        "cheekbone_softness": "soft",
        "lip_fullness": "medium-full",
        "brow_style": "natural straight",
        "favorite_locations": "kitchen window corner, favorite cafe table",
        "recurring_spaces": "living room sofa, hallway mirror",
        "camera_behavior_memory": {
            "preferred_shot_archetypes": ["candid_handheld", "friend_shot"],
            "average_camera_distance": "1.1m",
            "preferred_framing_style": "eye-level",
            "selfie_frequency": "rare",
            "candid_frequency": "frequent",
        },
    },
}


def _compose(scene=None, outfit_summary="cream cardigan + denim"):
    composer = PromptComposer(DummyState())
    return composer.compose_package(BASE_CONTEXT, scene or Scene(), outfit_summary, "photo", ["top_1"])


def test_prompt_package_keeps_required_metadata_and_canonical_version():
    package = _compose()

    for key in [
        "identity_anchor",
        "body_anchor",
        "scene_action",
        "wardrobe_block",
        "camera_context",
        "realism_block",
        "continuity_block",
        "negative_prompt",
        "final_prompt",
    ]:
        assert package.get(key)

    assert package["prompt_format_version"] == "v6"


def test_positive_prompt_uses_exact_six_block_canonical_format():
    package = _compose()
    blocks = [block.strip() for block in package["final_prompt"].split("\n\n") if block.strip()]

    assert len(blocks) == 6
    assert blocks[0].startswith("Identity: ")
    assert blocks[2].startswith("Scene: ")
    assert blocks[3].startswith("Outfit: ")
    assert blocks[4].startswith("Environment: ")
    assert blocks[5].startswith("Mood: ")


def test_identity_block_is_stable_for_same_character_input():
    package_a = _compose()
    package_b = _compose()
    identity_a = package_a["final_prompt"].split("\n\n")[0]
    identity_b = package_b["final_prompt"].split("\n\n")[0]

    assert identity_a == identity_b


def test_travel_walk_prompt_uses_fixed_framing_and_no_alternatives():
    scene = Scene()
    scene.scene_moment = "Slow walk through a nearly empty terminal with carry-on"
    scene.description = "Walking through the airport terminal before boarding"
    scene.location = "airport terminal"
    scene.activity = "walking"
    scene.visual_focus = "carry-on suitcase and shoulder bag"

    package = _compose(scene, "cream trench coat, denim, white sneakers")
    blocks = [block.strip() for block in package["final_prompt"].split("\n\n") if block.strip()]
    lowered = package["final_prompt"].lower()

    assert package["framing_mode"] == "3/4 body walking shot"
    assert blocks[1] == "3/4 body walking shot"
    assert "waist-up" not in lowered
    assert "half-body" not in lowered
    assert "full body" not in lowered


def test_scene_block_contains_action_and_context_only():
    scene = Scene()
    scene.scene_moment = "Walking through the airport terminal before boarding"
    scene.description = "Walking through the airport terminal before boarding"
    scene.location = "airport terminal"
    scene.activity = "walking"
    scene.visual_focus = "carry-on suitcase"
    scene.mood = "curious"

    package = _compose(scene)
    scene_block = package["final_prompt"].split("\n\n")[2].lower()

    assert scene_block.startswith("scene: ")
    assert "outfit:" not in scene_block
    assert "lighting" not in scene_block
    assert "mood" not in scene_block
    assert "curious" not in scene_block


def test_outfit_block_contains_only_clothing_items():
    package = _compose(outfit_summary="cream trench coat, cream trench coat, denim, white sneakers")
    outfit_block = package["final_prompt"].split("\n\n")[3]

    lowered = outfit_block.lower()

    assert outfit_block.startswith("Outfit: ")
    assert "lighting" not in lowered
    assert "mood" not in lowered
    assert "white sneakers" in lowered or "comfortable sneakers" in lowered
    assert "denim" in lowered or "trousers" in lowered or "jeans" in lowered
    assert "bag" in lowered or "carry on" in lowered or "accessor" not in lowered


def test_environment_block_contains_realism_depth_and_light_only():
    scene = Scene()
    scene.location = "airport terminal"
    scene.scene_moment = "Airport walk before boarding"

    package = _compose(scene)
    environment_block = package["final_prompt"].split("\n\n")[4].lower()

    assert environment_block.startswith("environment: ")
    assert "photorealistic" in environment_block
    assert "depth" in environment_block
    assert "perspective" in environment_block
    assert "light" in environment_block
    assert "walking" not in environment_block


def test_mood_block_uses_controlled_emotional_vocabulary_only():
    scene = Scene()
    scene.mood = "focused"

    package = _compose(scene)
    mood_block = package["final_prompt"].split("\n\n")[5]

    assert mood_block == "Mood: composed focus."


def test_positive_prompt_contains_only_english_ascii_letters_from_scene_payload():
    package = _compose()
    assert not PromptComposer.CYRILLIC_RE.search(package["final_prompt"])


def test_positive_prompt_excludes_negative_phrases_and_synthetic_junk():
    package = _compose()
    lowered = package["final_prompt"].lower()

    banned = [
        "no plastic skin",
        "no identity drift",
        "no duplicate people",
        "no distorted limbs",
        "beautiful young woman",
        "8k",
        "highly detailed",
        "perfect lighting",
    ]

    for phrase in banned:
        assert phrase not in lowered


def test_positive_prompt_has_no_duplicate_blocks_or_repeated_words():
    package = _compose(outfit_summary="cream cardigan, cream cardigan, denim")
    prompt = package["final_prompt"]

    assert prompt.count("\n\n") == 5
    assert "cream cardigan, cream cardigan" not in prompt.lower()
    assert "walking walking" not in prompt.lower()


def test_prompt_mode_reflects_actual_prompt_length():
    package = _compose()

    expected = PromptComposer._prompt_mode(package["final_prompt"])
    assert package["prompt_mode"] == expected


def test_outfit_fallback_adds_missing_shoes_when_summary_is_incomplete():
    package = _compose(outfit_summary="cream cardigan, denim")
    outfit_block = package["final_prompt"].split("\n\n")[3].lower()

    assert "cardigan" in outfit_block or "layer" in outfit_block
    assert "denim" in outfit_block
    assert "sneakers" in outfit_block or "boots" in outfit_block or "sandals" in outfit_block or "shoes" in outfit_block


def test_empty_outfit_uses_default_outfit_instead_of_blank_block():
    package = _compose(outfit_summary=".")
    outfit_block = package["final_prompt"].split("\n\n")[3]

    assert outfit_block.startswith("Outfit: ")
    assert outfit_block != "Outfit: ."


def test_compose_package_uses_canonical_outfit_sentence_from_context_without_rebuilding(monkeypatch):
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["outfit_sentence"] = "soft knit top, relaxed straight trousers, comfortable sneakers, small crossbody bag; slightly relaxed fit with natural drape"
    context["outfit_struct"] = {
        "top": "soft knit top",
        "bottom": "relaxed straight trousers",
        "shoes": "comfortable sneakers",
        "accessories": "small crossbody bag",
        "fit": "slightly relaxed fit with natural drape",
        "outfit_sentence": context["outfit_sentence"],
    }

    def _fail_generate_bundle(*args, **kwargs):
        raise AssertionError("compose_package should use canonical outfit_sentence from context")

    monkeypatch.setattr(composer.outfit_generator, "generate_bundle", _fail_generate_bundle)

    package = composer.compose_package(context, Scene(), "ignored summary", "photo", ["top_1"])

    assert package["outfit_sentence"] == context["outfit_sentence"]
    assert package["outfit_summary"] == context["outfit_sentence"]
    assert package["final_prompt"].split("\n\n")[3] == f"Outfit: {context['outfit_sentence']}."


def test_canonical_outfit_sentence_wins_over_legacy_summary_in_final_prompt(monkeypatch):
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["outfit_sentence"] = "soft knit top, relaxed straight trousers, comfortable sneakers, small crossbody bag; slightly relaxed fit with natural drape"
    legacy_summary = "old glossy trench summary, old glossy trench summary, pointed heels"

    def _fail_generate_bundle(*args, **kwargs):
        raise AssertionError("legacy summary must not rebuild prompt outfit when canonical outfit_sentence already exists")

    monkeypatch.setattr(composer.outfit_generator, "generate_bundle", _fail_generate_bundle)

    package = composer.compose_package(context, Scene(), legacy_summary, "photo", ["top_1"])
    prompt = package["final_prompt"].lower()

    assert "old glossy trench summary" not in prompt
    assert "pointed heels" not in prompt
    assert context["outfit_sentence"] in package["final_prompt"]


@pytest.mark.parametrize("placeholder", ["placeholder", "outfit", "same outfit", "n/a"])
def test_placeholder_outfit_uses_safe_fallback(placeholder: str):
    package = _compose(outfit_summary=placeholder)
    outfit_block = package["final_prompt"].split("\n\n")[3].lower()

    assert outfit_block.startswith("outfit: ")
    assert outfit_block != "outfit: ."
    assert "placeholder" not in outfit_block
    assert "same outfit" not in outfit_block


def test_manual_outfit_override_is_inserted_without_regeneration():
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["outfit_override"] = "soft fitted knit dress, light cardigan, flat slides, small overnight bag"

    package = composer.compose_package(context, Scene(), "ignored summary", "photo", ["dress_1"])
    outfit_block = package["final_prompt"].split("\n\n")[3]

    assert outfit_block == "Outfit: soft fitted knit dress, light cardigan, flat slides, small overnight bag."


def test_invalid_manual_outfit_override_raises_validation_error():
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["outfit_override"] = "мягкий свитер"

    with pytest.raises(PromptValidationError, match="Manual outfit override"):
        composer.compose_package(context, Scene(), "ignored summary", "photo", ["top_1"])


def test_bold_style_intensity_keeps_realistic_attractive_silhouette():
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["style_intensity"] = "bold"
    context["outfit_style"] = "bold_minimal"
    scene = Scene()
    scene.location = "hotel room"
    scene.scene_moment = "Quiet evening in a hotel room before sleep"
    scene.description = "Quiet evening in a hotel room"
    scene.time_of_day = "evening"

    package = composer.compose_package(context, scene, "", "photo", ["dress_1"])
    outfit_block = package["final_prompt"].split("\n\n")[3].lower()

    assert "fitted" in outfit_block or "body lines" in outfit_block or "open neckline" in outfit_block
    assert "lingerie" not in outfit_block
    assert "sexy" not in outfit_block


def test_airport_outfit_fallback_stays_travel_ready_and_contextual():
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["behavioral_context"] = BehaviorState(
        energy_level="medium",
        social_mode="light_public",
        emotional_arc="transition",
        habit="packing",
        place_anchor="terminal_gate",
        objects=["carry_on", "bag"],
        self_presentation="transitional",
    )
    scene = Scene()
    scene.location = "airport terminal"
    scene.activity = "walking"
    scene.scene_moment = "Walking to the gate before boarding"
    scene.description = "Walking to the gate before boarding"

    package = composer.compose_package(context, scene, ".", "photo", ["top_1"])
    outfit_block = package["final_prompt"].split("\n\n")[3].lower()

    assert "carry on" in outfit_block
    assert "jacket" in outfit_block or "layer" in outfit_block or "coat" in outfit_block
    assert "sneakers" in outfit_block or "boots" in outfit_block


def test_validate_prompt_rejects_cyrillic():
    composer = PromptComposer(DummyState())
    with pytest.raises(PromptValidationError, match="Cyrillic detected in prompt"):
        composer._validate_canonical_prompt(
            "Identity: Овальная face.\n\nmirror selfie head-and-shoulders shot\n\nScene: morning routine.\n\nOutfit: knit top, jeans, white sneakers.\n\nEnvironment: photorealistic room; accurate perspective.\n\nMood: calm ease.",
            Scene(),
            BASE_CONTEXT,
        )


def test_validate_prompt_rejects_empty_outfit_placeholder():
    composer = PromptComposer(DummyState())
    with pytest.raises(PromptValidationError, match="Outfit block is empty"):
        composer._validate_canonical_prompt(
            "Identity: soft oval face.\n\nmirror selfie head-and-shoulders shot\n\nScene: morning routine.\n\nOutfit: .\n\nEnvironment: photorealistic room; accurate perspective.\n\nMood: calm ease.",
            Scene(),
            BASE_CONTEXT,
        )


def test_behavior_influences_prompt_with_movement_mood_and_objects():
    composer = PromptComposer(DummyState())
    context = dict(BASE_CONTEXT)
    context["behavioral_context"] = BehaviorState(
        energy_level="low",
        social_mode="light_public",
        emotional_arc="transition",
        habit="coffee_moment",
        place_anchor="terminal_gate",
        objects=["coffee_cup", "carry_on", "bag"],
        self_presentation="transitional",
    )
    scene = Scene()
    scene.scene_moment = "Coffee at the gate before boarding"
    scene.description = "Quiet pause before boarding"
    scene.location = "airport terminal"
    scene.activity = "waiting"

    package = composer.compose_package(context, scene, "cream cardigan + denim", "photo", ["top_1"])
    prompt = package["final_prompt"].lower()

    assert "natural pause moment" in prompt or "still posture" in prompt
    assert "holding cup naturally" in prompt
    assert "coffee cup" in prompt
    assert "carry on" in prompt
    assert "bag" in prompt
    assert "checking the boarding screen occasionally" in prompt
    assert "transitional mood" in prompt
    assert "soft background people only" in prompt
    assert composer._find_duplicate_clauses(package["final_prompt"]) == []
