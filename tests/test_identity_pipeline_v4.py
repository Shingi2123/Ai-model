<<<<<<< ours
<<<<<<< ours
import json

=======
>>>>>>> theirs
=======
>>>>>>> theirs
from virtual_persona.pipeline.identity import CharacterIdentityManager, default_identity_manifest
from virtual_persona.pipeline.prompt_composer import PromptComposer
from virtual_persona.pipeline.provider_prompt_formatter import ReferenceAwarePromptFormatter
from virtual_persona.pipeline.quality import CandidateRanker, SceneSanityChecker


class DummyState:
    def load_prompt_blocks(self):
        return {}


class Scene:
    description = "Morning coffee at kitchen table"
    activity = "breakfast"
    scene_source = "generated"
    location = "home kitchen"
    mood = "calm"
    time_of_day = "morning"
    scene_moment = "Mirror selfie before breakfast"
    moment_signature = "sig-v4"


def test_identity_anchor_and_body_anchor_present_with_fallback(tmp_path):
    mgr = CharacterIdentityManager(tmp_path / "identity")
    mgr.ensure_structure()
    pack = mgr.load_pack()

    anchor = mgr.identity_anchor({"character_profile": {}})
    body = mgr.body_anchor("seated_table_shot", {"character_profile": {}}, pack)

    assert "stable identity anchor" in anchor
    assert "preferred_reference=half_body_reference" in body
    assert "fallback" in body


def test_prompt_v4_uses_compact_mode_for_simple_selfie():
    composer = PromptComposer(DummyState())
    ctx = {"character_profile": {"appearance_face_shape": "soft oval"}}
    scene = Scene()
    pkg = composer.compose_package(ctx, scene, "tee", "photo", ["top_1"])

    assert pkg["prompt_mode"] == "compact"
    assert "identity_anchor" in pkg and pkg["identity_anchor"]
    assert "body_anchor" in pkg and pkg["body_anchor"]


def test_negative_prompt_layering_contains_shot_and_location_rules():
    composer = PromptComposer(DummyState())
    ctx = {"character_profile": {}}
    scene = Scene()
    pkg = composer.compose_package(ctx, scene, "tee", "photo", ["top_1"])

    assert "impossible reflection geometry" in pkg["negative_prompt"]
    assert "broken mug handle" in pkg["negative_prompt"]


def test_reference_aware_formatter_exports_provider_specific_strings():
    formatter = ReferenceAwarePromptFormatter()
    package = {
        "final_prompt": "base prompt",
        "negative_prompt": "bad hands",
        "reference_bundle": "face_ref",
        "video_motion": "walk",
        "video_camera_motion": "slow pan",
    }

    mj = formatter.format_for_provider(package, "midjourney")
    i2v = formatter.format_for_provider(package, "image_to_video")

    assert "--no bad hands" in mj
    assert "Motion: walk" in i2v


def test_quality_ranker_prefers_better_similarity_and_scene_logic():
    ranker = CandidateRanker()
    rows = [
        {"asset_id": "a", "face_similarity": 0.2, "scene_logic_score": 0.9, "artifact_flags": ""},
        {"asset_id": "b", "face_similarity": 0.8, "scene_logic_score": 0.8, "artifact_flags": ""},
    ]
    ranked = ranker.rank(rows)
    assert ranked[0]["asset_id"] == "b"


def test_scene_sanity_checker_exposes_rule_flags():
    checker = SceneSanityChecker()
    res = checker.evaluate({"shot_archetype": "seated_table_shot", "location": "kitchen"})
    assert "impossible seated geometry" in res["artifact_flags"]
    assert "broken mug handle" in res["artifact_flags"]


def test_default_identity_manifest_structure_contains_reference_pack():
    payload = default_identity_manifest()
    assert "character_dna" in payload
    assert "reference_pack" in payload
    assert "face_reference" in payload["reference_pack"]
<<<<<<< ours
<<<<<<< ours
    assert "reference_manifest" in payload
    assert "anchors" in payload["reference_manifest"]


def test_identity_pack_supports_reference_manifest_folder_mapping(tmp_path):
    root = tmp_path / "identity"
    for rel in [
        "references/base",
        "references/selfies",
        "references/body_consistency",
        "references/full_body",
        "references/wardrobe/lifestyle",
        "references/wardrobe/uniform",
        "references/angles",
        "references/expressions",
        "references/identity_lock",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    manifest = default_identity_manifest()
    (root / "character_identity_profile.json").write_text(json.dumps(manifest), encoding="utf-8")

    pack = CharacterIdentityManager(root).load_pack()

    assert pack.references["face_reference"] == "references/face_reference.jpg"
    assert pack.references["half_body_reference"] == "references/wardrobe/lifestyle/"
    assert pack.references["full_body_reference"] == "references/full_body/"
    assert pack.reference_types["selfie"]["primary_anchors"][0] == "references/selfies/"


def test_reference_selection_uses_generation_mode_and_shot_type(tmp_path):
    root = tmp_path / "identity"
    for rel in [
        "references/base",
        "references/selfies",
        "references/full_body",
        "references/body_consistency",
        "references/wardrobe/lifestyle",
        "references/identity_lock",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    manifest = default_identity_manifest()
    manifest["reference_pack"]["face_reference"] = ""
    manifest["reference_pack"]["full_body_reference"] = ""
    (root / "character_identity_profile.json").write_text(json.dumps(manifest), encoding="utf-8")

    mgr = CharacterIdentityManager(root)
    pack = mgr.load_pack()

    selfie = mgr.select_reference_bundle("front_selfie", "selfie_mode", pack)
    full_body = mgr.select_reference_bundle("friend_shot", "full-body_mode", pack)

    assert selfie["requested_type"] == "selfie"
    assert selfie["selected"] == "references/selfies/"
    assert full_body["requested_type"] == "full_body"
    assert full_body["selected"] == "references/full_body/"
=======
>>>>>>> theirs
=======
>>>>>>> theirs
