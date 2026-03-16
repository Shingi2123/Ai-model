from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


IDENTITY_ROOT = Path("data/character_identity")


@dataclass
class IdentityPack:
    root: Path
    manifest: Dict[str, Any] = field(default_factory=dict)
    references: Dict[str, str] = field(default_factory=dict)
    missing_required: List[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.missing_required


class CharacterIdentityManager:
    REQUIRED_REFERENCE_KEYS = ["face_reference", "half_body_reference", "full_body_reference"]
    OPTIONAL_REFERENCE_KEYS = [
        "expressions_pack",
        "angles_pack",
        "lighting_neutral_reference",
        "style_neutral_reference",
        "walking_pose_reference",
        "seated_pose_reference",
    ]

    def __init__(self, root: Path | str = IDENTITY_ROOT) -> None:
        self.root = Path(root)

    def ensure_structure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        refs_dir = self.root / "references"
        refs_dir.mkdir(parents=True, exist_ok=True)

    def load_pack(self) -> IdentityPack:
        self.ensure_structure()
        manifest_path = self.root / "character_identity_profile.json"
        manifest = self._read_json(manifest_path, fallback={})

        refs = manifest.get("reference_pack") if isinstance(manifest.get("reference_pack"), dict) else {}
        refs = {k: str(v) for k, v in refs.items()}
        missing = [key for key in self.REQUIRED_REFERENCE_KEYS if not refs.get(key)]
        return IdentityPack(root=self.root, manifest=manifest, references=refs, missing_required=missing)

    @staticmethod
    def _read_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return fallback

    def identity_anchor(self, context: Dict[str, Any], pack: IdentityPack | None = None) -> str:
        pack = pack or self.load_pack()
        profile = (pack.manifest.get("character_dna") if isinstance(pack.manifest, dict) else {}) or {}
        character_profile = context.get("character_profile") or {}

        age = profile.get("age") or character_profile.get("age") or "22"
        face_type = profile.get("face_type") or character_profile.get("appearance_face_shape") or "soft oval face"
        jawline = profile.get("jawline") or "gentle defined jawline"
        nose = profile.get("nose") or "straight natural nose"
        eyes = profile.get("eyes") or character_profile.get("appearance_eye_color") or "calm almond eyes"
        lips = profile.get("lips") or "natural medium lips"
        skin = profile.get("skin_tone") or character_profile.get("skin_realism_profile") or "natural skin texture"
        freckles = profile.get("freckles") or "subtle or absent freckles"
        hair = profile.get("hair") or character_profile.get("appearance_hair_color") or "light chestnut medium-length hair"
        makeup = profile.get("makeup") or character_profile.get("makeup_profile") or "soft everyday makeup"

        return (
            "stable identity anchor: recurring same woman; "
            f"age={age}; face={face_type}; jawline={jawline}; nose={nose}; eyes={eyes}; lips={lips}; "
            f"skin={skin}; freckles={freckles}; hair={hair}; makeup={makeup}; "
            "preserve same face geometry and recognizable proportions across generations."
        )

    def body_anchor(self, shot_archetype: str, context: Dict[str, Any], pack: IdentityPack | None = None) -> str:
        pack = pack or self.load_pack()
        profile = (pack.manifest.get("character_dna") if isinstance(pack.manifest, dict) else {}) or {}
        character_profile = context.get("character_profile") or {}

        body_type = profile.get("body_type") or character_profile.get("appearance_body_type") or "slim natural build"
        height = profile.get("estimated_height") or "average height"
        shoulders = profile.get("shoulder_set") or "natural shoulder posture"
        posture = profile.get("posture") or "relaxed upright posture"

        if shot_archetype in {"close_portrait", "front_selfie", "mirror_selfie"}:
            preferred_ref = "face_reference"
            cue = "close-up framing preserves habitual expression and neck/shoulder proportions"
        elif shot_archetype in {"seated_table_shot", "waist_up", "friend_shot"}:
            preferred_ref = "half_body_reference"
            cue = "waist-up framing keeps stable torso length and arm proportions"
        else:
            preferred_ref = "full_body_reference"
            cue = "full-body framing keeps leg length, shoulder width and stance balance consistent"

        if not pack.references.get(preferred_ref):
            cue += "; fallback to available identity references and DNA cues"

        return (
            f"body consistency anchor: body_type={body_type}; estimated_height={height}; shoulder_set={shoulders}; posture={posture}; "
            f"preferred_reference={preferred_ref}; {cue}."
        )


def default_identity_manifest() -> Dict[str, Any]:
    return {
        "version": 1,
        "character_dna": {
            "age": "22",
            "estimated_height": "167cm",
            "body_type": "slim natural build",
            "face_type": "soft oval",
            "jawline": "softly defined",
            "nose": "straight natural",
            "eyes": "green almond",
            "lips": "medium natural",
            "skin_tone": "light neutral",
            "freckles": "subtle",
            "hair": "light chestnut medium length",
            "hairstyle": "natural loose",
            "shoulder_set": "relaxed",
            "posture": "natural upright",
            "wardrobe_style": "casual urban",
            "makeup": "light natural",
            "accessories": "minimal everyday",
            "visual_vibe": "grounded candid lifestyle",
        },
        "reference_pack": {
            "face_reference": "references/face_reference.jpg",
            "half_body_reference": "",
            "full_body_reference": "",
            "expressions_pack": "",
            "angles_pack": "",
            "lighting_neutral_reference": "",
            "style_neutral_reference": "",
            "walking_pose_reference": "",
            "seated_pose_reference": "",
        },
    }
