from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


IDENTITY_ROOT = Path("data/character_identity")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class IdentityPack:
    root: Path
    manifest: Dict[str, Any] = field(default_factory=dict)
    references: Dict[str, str] = field(default_factory=dict)
    reference_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
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
    DEFAULT_FOLDER_MAP = {
        "base": "references/base",
        "angles": "references/angles",
        "body_consistency": "references/body_consistency",
        "expressions": "references/expressions",
        "full_body": "references/full_body",
        "identity_lock": "references/identity_lock",
        "selfies": "references/selfies",
        "wardrobe_lifestyle": "references/wardrobe/lifestyle",
        "wardrobe_uniform": "references/wardrobe/uniform",
    }
    DEFAULT_REFERENCE_TYPE_MAP = {
        "face": {"primary": ["base", "identity_lock"], "secondary": ["angles", "expressions"]},
        "selfie": {"primary": ["selfies", "base"], "secondary": ["identity_lock", "angles"]},
        "full_body": {"primary": ["full_body", "body_consistency"], "secondary": ["wardrobe_lifestyle", "identity_lock"]},
        "lifestyle": {"primary": ["wardrobe_lifestyle", "body_consistency"], "secondary": ["full_body", "selfies"]},
        "uniform": {"primary": ["wardrobe_uniform", "full_body"], "secondary": ["body_consistency", "identity_lock"]},
    }
    SHOT_TYPE_TO_REFERENCE_TYPE = {
        "close_portrait": "face",
        "front_selfie": "selfie",
        "mirror_selfie": "selfie",
        "seated_table_shot": "lifestyle",
        "waist_up": "lifestyle",
        "full_body": "full_body",
        "friend_shot": "full_body",
        "candid_handheld": "lifestyle",
    }
    GENERATION_MODE_TO_REFERENCE_TYPE = {
        "portrait_mode": "face",
        "waist-up_mode": "lifestyle",
        "seated_lifestyle_mode": "lifestyle",
        "full-body_mode": "full_body",
        "selfie_mode": "selfie",
        "mirror_selfie_mode": "selfie",
        "uniform_mode": "uniform",
        "lifestyle_mode": "lifestyle",
    }

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
        folder_map = self._folder_map(manifest)
        reference_types = self._reference_types(manifest, folder_map)
        refs = self._legacy_reference_pack(manifest, reference_types)
        missing = [key for key in self.REQUIRED_REFERENCE_KEYS if not refs.get(key)]
        return IdentityPack(
            root=self.root,
            manifest=manifest,
            references=refs,
            reference_types=reference_types,
            missing_required=missing,
        )

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

    def select_reference_bundle(
        self,
        shot_archetype: str,
        generation_mode: str,
        pack: IdentityPack | None = None,
    ) -> Dict[str, Any]:
        pack = pack or self.load_pack()
        requested_type = (
            self.GENERATION_MODE_TO_REFERENCE_TYPE.get(generation_mode)
            or self.SHOT_TYPE_TO_REFERENCE_TYPE.get(shot_archetype, "face")
        )
        type_payload = pack.reference_types.get(requested_type, {})
        primary_anchors = [str(path) for path in type_payload.get("primary_anchors", []) if path]
        secondary_anchors = [str(path) for path in type_payload.get("secondary_anchors", []) if path]
        legacy_key = self._legacy_key_for_reference_type(requested_type, shot_archetype)
        selected = (
            primary_anchors[0]
            if primary_anchors
            else pack.references.get(legacy_key)
            or pack.references.get("face_reference")
            or "fallback_character_dna"
        )
        return {
            "requested_type": requested_type,
            "shot_archetype": shot_archetype,
            "generation_mode": generation_mode,
            "legacy_key": legacy_key,
            "selected": selected,
            "primary_anchors": primary_anchors,
            "secondary_anchors": secondary_anchors,
            "pack_ready": pack.ready,
            "manual_user_step": "Attach the selected anchors manually in your external generator before running the render.",
        }

    def _folder_map(self, manifest: Dict[str, Any]) -> Dict[str, str]:
        payload = manifest.get("reference_manifest") if isinstance(manifest.get("reference_manifest"), dict) else {}
        raw = payload.get("folder_mapping") if isinstance(payload.get("folder_mapping"), dict) else {}
        folder_map = dict(self.DEFAULT_FOLDER_MAP)
        for key, value in raw.items():
            if value:
                folder_map[str(key)] = str(value).replace("\\", "/")
        return folder_map

    def _reference_types(self, manifest: Dict[str, Any], folder_map: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        payload = manifest.get("reference_manifest") if isinstance(manifest.get("reference_manifest"), dict) else {}
        anchors = payload.get("anchors") if isinstance(payload.get("anchors"), dict) else {}
        result: Dict[str, Dict[str, Any]] = {}
        for reference_type, defaults in self.DEFAULT_REFERENCE_TYPE_MAP.items():
            cfg = anchors.get(reference_type) if isinstance(anchors.get(reference_type), dict) else {}
            primary_keys = self._normalize_anchor_keys(cfg.get("primary"), defaults.get("primary", []))
            secondary_keys = self._normalize_anchor_keys(cfg.get("secondary"), defaults.get("secondary", []))
            primary_anchors = self._resolve_anchor_paths(primary_keys, folder_map)
            secondary_anchors = self._resolve_anchor_paths(secondary_keys, folder_map)
            result[reference_type] = {
                "primary_keys": primary_keys,
                "secondary_keys": secondary_keys,
                "primary_anchors": primary_anchors,
                "secondary_anchors": secondary_anchors,
            }
        return result

    def _legacy_reference_pack(self, manifest: Dict[str, Any], reference_types: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
        refs = manifest.get("reference_pack") if isinstance(manifest.get("reference_pack"), dict) else {}
        normalized = {str(k): str(v).replace("\\", "/") for k, v in refs.items() if v is not None}
        fallback_refs = {
            "face_reference": self._first_anchor(reference_types.get("face", {})),
            "half_body_reference": self._first_anchor(reference_types.get("lifestyle", {}))
            or self._first_anchor(reference_types.get("selfie", {})),
            "full_body_reference": self._first_anchor(reference_types.get("full_body", {})),
            "expressions_pack": self._first_anchor({"primary_anchors": self._anchors_for_key("expressions", manifest)}),
            "angles_pack": self._first_anchor({"primary_anchors": self._anchors_for_key("angles", manifest)}),
            "lighting_neutral_reference": self._first_anchor({"primary_anchors": self._anchors_for_key("identity_lock", manifest)}),
            "style_neutral_reference": self._first_anchor({"primary_anchors": self._anchors_for_key("wardrobe_lifestyle", manifest)}),
            "walking_pose_reference": self._first_anchor(reference_types.get("full_body", {})),
            "seated_pose_reference": self._first_anchor(reference_types.get("lifestyle", {})),
        }
        for key, value in fallback_refs.items():
            if not normalized.get(key) and value:
                normalized[key] = value
        return normalized

    def _anchors_for_key(self, key: str, manifest: Dict[str, Any]) -> List[str]:
        folder_map = self._folder_map(manifest)
        return self._resolve_anchor_paths([key], folder_map)

    def _resolve_anchor_paths(self, keys: List[str], folder_map: Dict[str, str]) -> List[str]:
        resolved: List[str] = []
        for key in keys:
            raw_path = folder_map.get(key) or key
            path = self.root / raw_path
            normalized = raw_path.replace("\\", "/")
            if path.is_dir():
                resolved.append(f"{normalized}/")
                continue
            if path.is_file():
                resolved.append(normalized)
                continue
            matches = self._image_candidates(path)
            if matches:
                resolved.append(matches[0])
                continue
            resolved.append(f"{normalized}/" if "." not in Path(normalized).name else normalized)
        return resolved

    @staticmethod
    def _normalize_anchor_keys(raw: Any, fallback: List[str]) -> List[str]:
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return [str(item) for item in fallback if str(item).strip()]

    def _image_candidates(self, path: Path) -> List[str]:
        parent = path.parent
        stem = path.name
        if not parent.exists():
            return []
        matches: List[str] = []
        for ext in IMAGE_EXTENSIONS:
            candidate = parent / f"{stem}{ext}"
            if candidate.exists():
                matches.append(candidate.relative_to(self.root).as_posix())
        return sorted(matches)

    @staticmethod
    def _first_anchor(payload: Dict[str, Any]) -> str:
        anchors = payload.get("primary_anchors") if isinstance(payload, dict) else []
        if not anchors and isinstance(payload, dict):
            anchors = payload.get("secondary_anchors", [])
        return str(anchors[0]) if anchors else ""

    @staticmethod
    def _legacy_key_for_reference_type(reference_type: str, shot_archetype: str) -> str:
        if reference_type == "face":
            return "face_reference"
        if reference_type == "selfie":
            return "face_reference"
        if reference_type == "full_body":
            return "full_body_reference"
        if reference_type in {"lifestyle", "uniform"}:
            return "half_body_reference" if shot_archetype in {"seated_table_shot", "waist_up"} else "full_body_reference"
        return "face_reference"


def default_identity_manifest() -> Dict[str, Any]:
    return {
        "version": 2,
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
        "reference_manifest": {
            "schema": "character_identity_pack_v2",
            "folder_mapping": {
                "base": "references/base",
                "angles": "references/angles",
                "body_consistency": "references/body_consistency",
                "expressions": "references/expressions",
                "full_body": "references/full_body",
                "identity_lock": "references/identity_lock",
                "selfies": "references/selfies",
                "wardrobe_lifestyle": "references/wardrobe/lifestyle",
                "wardrobe_uniform": "references/wardrobe/uniform",
            },
            "anchors": {
                "face": {"primary": ["base", "identity_lock"], "secondary": ["angles", "expressions"]},
                "selfie": {"primary": ["selfies", "base"], "secondary": ["identity_lock", "angles"]},
                "full_body": {"primary": ["full_body", "body_consistency"], "secondary": ["wardrobe_lifestyle", "identity_lock"]},
                "lifestyle": {"primary": ["wardrobe_lifestyle", "body_consistency"], "secondary": ["full_body", "selfies"]},
                "uniform": {"primary": ["wardrobe_uniform", "full_body"], "secondary": ["body_consistency", "identity_lock"]},
            },
        },
    }