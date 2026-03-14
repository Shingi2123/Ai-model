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
        "appearance_body_type": "slim",
        "makeup_profile": "natural dewy",
        "skin_realism_profile": "real pores",
        "signature_appearance_cues": "freckles and soft brows",
        "device_profile": "iPhone 16 Pro natural color profile",
        "recurring_phone_device": "graphite iPhone-class device with clear case",
        "face_signature": "soft straight brows, medium-full lips, balanced eye spacing, rounded cheek contour",
        "face_shape": "soft oval",
        "nose_bridge": "straight",
        "cheekbone_softness": "soft",
        "lip_fullness": "medium-full",
        "brow_style": "natural straight",
        "favorite_locations": "kitchen window corner, favorite café table",
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
        "camera_behavior_memory",
        "face_consistency",
        "device_identity",
        "favorite_locations",
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
    assert "impossible reflection geometry" in package["negative_prompt"]
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


def test_face_consistency_signature_appears_in_prompt():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "cream cardigan", "photo", ["top_1"])

    assert "face consistency signature" in package["face_consistency"]
    assert "balanced eye spacing" in package["final_prompt"]


def test_device_identity_is_consistent_for_selfie_and_mirror_and_mirror_geometry_present():
    composer = PromptComposer(DummyState())

    mirror_scene = Scene()
    mirror_scene.scene_moment = "Mirror selfie in hallway before leaving"
    mirror_scene.scene_moment_type = "diary_mirror"
    mirror_package = composer.compose_package(BASE_CONTEXT, mirror_scene, "cream cardigan", "photo", ["top_1"])

    selfie_scene = Scene()
    selfie_scene.scene_moment = "Front selfie while waiting for coffee"
    selfie_scene.scene_moment_type = "selfie"
    selfie_package = composer.compose_package(BASE_CONTEXT, selfie_scene, "cream cardigan", "photo", ["top_1"])

    assert "graphite iPhone-class device with clear case" in mirror_package["device_identity"]
    assert "graphite iPhone-class device with clear case" in selfie_package["device_identity"]
    assert "phone visible in reflection" in mirror_package["camera_context"]


def test_candid_friend_shot_has_observer_and_handheld_realism():
    composer = PromptComposer(DummyState())
    scene = Scene()
    scene.scene_moment = "Candid frame while crossing the street"
    scene.scene_moment_type = "street_candid"

    package = composer.compose_package(BASE_CONTEXT, scene, "cream cardigan", "photo", ["top_1"])

    assert package["shot_archetype"] in {"candid_handheld", "friend_shot"}
    assert "handheld" in package["camera_context"].lower() or "observer" in package["camera_context"].lower()
    assert "handheld motion" in package["camera_physics"]


def test_negative_prompt_changes_by_archetype_and_scene():
    composer = PromptComposer(DummyState())

    mirror_scene = Scene()
    mirror_scene.scene_moment = "Mirror selfie in hotel room"
    mirror_scene.location = "hotel room"
    mirror_package = composer.compose_package(BASE_CONTEXT, mirror_scene, "tee", "photo", ["tee_1"])

    candid_scene = Scene()
    candid_scene.scene_moment = "Street candid near tram stop"
    candid_scene.location = "city street"
    candid_scene.scene_moment_type = "street_candid"
    candid_package = composer.compose_package(BASE_CONTEXT, candid_scene, "tee", "photo", ["tee_1"])

    assert "impossible reflection geometry" in mirror_package["negative_prompt"]
    assert "impossible reflection geometry" not in candid_package["negative_prompt"]
    assert "impossible pedestrian scale" in candid_package["negative_prompt"]


def test_platform_intent_changes_behavior_mode_and_polish_cues():
    composer = PromptComposer(DummyState())

    feed_pkg = composer.compose_package(BASE_CONTEXT, Scene(), "tee", "photo", ["tee_1"], platform_intent="instagram_feed")
    story_pkg = composer.compose_package(BASE_CONTEXT, Scene(), "tee", "story", ["tee_1"], platform_intent="story_lifestyle")

    assert "behavior_mode=instagram_feed" in feed_pkg["platform_intent"]
    assert "behavior_mode=story_lifestyle" in story_pkg["platform_intent"]
    assert feed_pkg["platform_intent"] != story_pkg["platform_intent"]


def test_favorite_location_memory_can_surface_in_prompt():
    composer = PromptComposer(DummyState())
    scene = Scene()
    scene.location = "kitchen window corner"

    package = composer.compose_package(BASE_CONTEXT, scene, "tee", "photo", ["tee_1"])

    assert "favorite location memory" in package["favorite_locations"]
    assert "kitchen window corner" in package["favorite_locations"]


def test_required_realism_blocks_are_structurally_present_and_anti_generic_constraints_enabled():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "tee", "photo", ["tee_1"])

    for key in [
        "camera_behavior_memory",
        "camera_physics",
        "sensor_realism",
        "smartphone_behavior",
        "micro_imperfections",
        "face_consistency",
        "favorite_locations",
        "anti_generic_constraints",
    ]:
        assert package.get(key)
    assert "fashion catalog mood" in package["anti_generic_constraints"]


def test_prompt_v3_layers_include_camera_behavior_fields_and_face_cues():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "tee", "photo", ["tee_1"])

    assert "preferred_shot_archetypes" in package["camera_behavior_memory"]
    assert "average_camera_distance" in package["camera_behavior_memory"]
    assert "selfie_frequency" in package["camera_behavior_memory"]
    assert "face_shape" in package["face_consistency"]
    assert "nose_bridge" in package["face_consistency"]


def test_favorite_location_memory_includes_favorites_and_recurring_spaces():
    composer = PromptComposer(DummyState())
    package = composer.compose_package(BASE_CONTEXT, Scene(), "tee", "photo", ["tee_1"])

    assert "favorite_locations=" in package["favorite_locations"]
    assert "recurring_spaces=" in package["favorite_locations"]
