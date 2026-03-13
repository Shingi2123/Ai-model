from virtual_persona.pipeline.prompt_composer import PromptComposer


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
    "continuity_context": {"arc_hint": "arrival_and_adaptation", "previous_evening_moment": "hotel check-in"},
    "persona_voice": {"restraint": 0.8, "reflection": 0.7, "self_irony": 0.2},
    "character_profile": {
        "display_name": "Alina Volkova",
        "age": "22",
        "appearance_hair_color": "light chestnut",
        "appearance_eye_color": "green",
        "appearance_face_shape": "soft oval",
        "appearance_body_type": "slim",
        "makeup_profile": "natural dewy",
        "skin_realism_profile": "real pores",
        "signature_appearance_cues": "freckles and soft brows",
        "device_profile": "iPhone 16 Pro natural color profile",
    },
}


def test_prompt_v2_contains_all_required_semantic_blocks():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan + denim", "photo", ["top_1"])

    for key in [
        "identity_core",
        "life_continuity_context",
        "scene_context",
        "wardrobe_context",
        "camera_context",
        "camera_physics",
        "sensor_realism",
        "smartphone_behavior",
        "micro_imperfections",
        "device_identity",
        "platform_intent",
        "composition_and_lighting",
        "realism_cues",
        "continuity_cues",
        "persona_voice_cues",
        "negative_prompt",
        "final_prompt",
    ]:
        assert package.get(key)


def test_camera_archetype_changes_camera_specific_cues():
    composer = PromptComposer(DummyState())

    scene_mirror = Scene()
    scene_mirror.scene_moment = "Mirror selfie in hotel room"
    mirror = composer.compose_package(BASE_CONTEXT, scene_mirror, "white tee", "photo", ["tee_1"])

    scene_candid = Scene()
    scene_candid.scene_moment = "Candid street frame during tram walk"
    scene_candid.scene_moment_type = "candid_street"
    candid = composer.compose_package(BASE_CONTEXT, scene_candid, "white tee", "photo", ["tee_1"])

    assert mirror["shot_archetype"] == "mirror_selfie"
    assert candid["shot_archetype"] in {"candid_handheld", "friend_shot"}
    assert mirror["camera_context"] != candid["camera_context"]


def test_mirror_selfie_has_phone_and_reflection_cues_and_negative_prompt_not_empty():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan", "photo", ["top_1"])

    assert "phone visible in reflection" in package["camera_context"]
    assert "broken mirror geometry" in package["negative_prompt"]
    assert package["negative_prompt"].strip()


def test_caption_prompt_does_not_inline_negative_prompt_block():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan", "caption", ["top_1"])

    assert "[negative_prompt]" not in package["final_prompt"]


def test_prompt_drops_degraded_generic_placeholders_in_final_prompt():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan", "photo", ["top_1"])

    lowered = package["final_prompt"].lower()
    assert "beautiful young woman" not in lowered
    assert "8k" not in lowered
    assert "highly detailed" not in lowered


def test_outfit_binding_and_continuity_cues_influence_final_prompt():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan + vintage denim", "photo", ["cardigan_1", "denim_1"])
    final_prompt = package["final_prompt"]

    assert "cream cardigan + vintage denim" in final_prompt
    assert "arrival_and_adaptation" in final_prompt
    assert "not fully unpacked luggage" in final_prompt
