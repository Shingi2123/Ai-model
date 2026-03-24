from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import re
from typing import Any, ClassVar, Dict, List, Mapping

from virtual_persona.pipeline.identity import CharacterIdentityManager
from virtual_persona.pipeline.outfit_generator import ManualOutfitValidationError, OutfitBundle, OutfitGenerationError, OutfitGenerator


class PromptValidationError(ValueError):
    pass


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaceCoherenceState:
    mode: str
    canonical_location: str
    location_keywords: tuple[str, ...]
    private_scene: bool
    public_scene: bool
    travel_context: bool
    allow_background_people: bool
    allow_bag_prop: bool
    allow_wearable_bag: bool


@dataclass
class PromptComposer:
    state_store: Any
    CANONICAL_PROMPT_VERSION = "v6"
    PROMPT_STYLE_VERSION = "rewrite_v2"
    USER_FACING_OUTFIT_PLACEHOLDER = "Prompt is unavailable because outfit validation failed"
    COMPACT_PROMPT_THRESHOLD = 740
    DENSE_PROMPT_MIN_LENGTH = 728
    DENSE_PROMPT_EXPANDED_BLOCKS = 4
    STRUCTURED_DENSE_PROMPT_MIN_LENGTH = 560
    STRUCTURED_DENSE_EXPANDED_BLOCKS = 3
    EXPANDED_BLOCK_BODY_THRESHOLD = 28
    IDENTITY_FLOOR_MIN_CUES = 6
    IDENTITY_FLOOR_ORDER: tuple[str, ...] = ("face", "jawline", "nose", "eyes", "lips", "skin", "hair")
    CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
    PLACEHOLDER_TOKENS: tuple[str, ...] = (
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "tbd",
        "todo",
        "placeholder",
        "unknown",
        "same",
        "same outfit",
        "default",
    )
    INVALID_OUTFIT_TOKENS: tuple[str, ...] = PLACEHOLDER_TOKENS + (
        "outfit",
        "look",
        "look here",
    )
    OUTFIT_DETAIL_KEYWORDS: tuple[str, ...] = (
        "fit",
        "fitted",
        "relaxed",
        "silhouette",
        "drape",
        "fabric",
        "fabrics",
        "texture",
        "textures",
        "fold",
        "folds",
        "wrinkle",
        "wrinkles",
        "worn",
        "layering",
        "layered",
        "matte",
        "bunching",
        "crease",
        "creases",
        "everyday",
        "natural",
        "lived-in",
        "shifted",
        "arranged",
        "tension",
        "gathering",
        "settling",
        "slouched",
    )
    FORBIDDEN_POSITIVE_PHRASES: tuple[str, ...] = (
        "no plastic skin",
        "no identity drift",
        "no duplicate people",
        "no distorted limbs",
        "no distorted proportions",
        "no fashion catalog symmetry",
        "no editorial fashion look",
        "no overproduced campaign lighting",
        "half-body and 3/4 body framing from waist-up",
    )
    FRAMING_TOKENS: tuple[str, ...] = (
        "3/4 body",
        "waist-up",
        "head-and-shoulders",
        "full body",
        "head-to-toe",
        "mirror selfie",
        "front selfie",
        "portrait shot",
    )
    CLAUSE_STOPWORDS: tuple[str, ...] = (
        "a",
        "an",
        "and",
        "as",
        "at",
        "before",
        "beside",
        "by",
        "for",
        "from",
        "her",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "through",
        "to",
        "with",
    )
    DUPLICATE_SEQUENCE_STOPWORDS: tuple[str, ...] = CLAUSE_STOPWORDS + (
        "already",
        "just",
        "only",
        "still",
        "there",
        "yet",
    )
    DUPLICATE_SEQUENCE_SCAN_RANGE: tuple[int, ...] = tuple(range(12, 1, -1))
    DUPLICATE_BLOCK_FAILURE_TOKEN_THRESHOLD = 5
    DUPLICATE_CLAUSE_FATAL_RATIO = 0.88
    SOFTENED_DUPLICATE_VALIDATION_REASONS: tuple[str, ...] = (
        "Duplicate clauses detected in prompt",
        "Duplicate word sequence detected in canonical prompt.",
    )
    GARMENT_DUPLICATE_FAMILIES: ClassVar[Dict[str, tuple[str, ...]]] = {
        "fit_line": (
            "fall straight",
            "falls naturally",
            "natural drape",
            "gentle drape",
            "lived-in fall",
            "fabric falling easy",
            "easy line",
            "easy movement",
        ),
        "effortless_styling": (
            "without trying too hard",
            "without looking overthought",
            "without looking styled",
            "without looking staged",
            "effortless",
            "unforced",
            "not styled for attention",
        ),
        "fabric_texture": (
            "soft matte everyday fabrics",
            "soft matte everyday textures",
            "soft matte fabric",
            "light breathable everyday fabrics",
            "matte everyday fabric",
        ),
        "lived_in_wear": (
            "slightly imperfect",
            "lightly worn",
            "natural folds",
            "natural fabric folds",
            "slightly rumpled",
            "worn in",
            "actually used",
            "not pressed fully flat",
        ),
    }
    GARMENT_CATEGORY_TOKENS: ClassVar[Dict[str, tuple[str, ...]]] = {
        "dress": ("dress",),
        "bottom": ("jeans", "trousers", "pants", "skirt", "shorts", "denim", "joggers", "leggings"),
        "shoes": ("sneakers", "boots", "loafers", "sandals", "slides", "shoes", "trainers"),
        "outerwear": ("coat", "jacket", "cardigan", "blazer", "hoodie", "trench", "layer"),
        "accessory": ("bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "belt"),
        "top": ("top", "blouse", "shirt", "sweater", "knit", "knitwear", "tank", "tee", "camisole"),
    }
    REWRITE_FORBIDDEN_SCENE_PHRASES: tuple[str, ...] = (
        "before the day starts",
        "during the morning routine",
        "daily pause",
        "natural pause moment",
        "before heading out",
        "before boarding",
        "before breakfast",
    )
    REWRITE_FORBIDDEN_MOOD_PHRASES: tuple[str, ...] = (
        "grounded routine mood",
        "transitional mood",
        "calm arrival mood",
        "focused before-leaving mood",
        "composed self-presentation",
        "soft self-presentation",
        "focused self-presentation",
        "quiet confidence",
        "composed focus",
        "calm ease",
    )
    SCENE_PROP_TOKENS: tuple[str, ...] = (
        "coffee cup",
        "cup",
        "mug",
        "carry on",
        "carry-on",
        "luggage",
        "suitcase",
        "roller bag",
        "overnight bag",
        "boarding pass",
        "passport",
        "laptop",
    )
    OUTFIT_PLURAL_NOUNS: tuple[str, ...] = (
        "trousers",
        "pants",
        "jeans",
        "shorts",
        "joggers",
        "leggings",
        "sneakers",
        "boots",
        "loafers",
        "sandals",
        "slides",
        "trainers",
        "shoes",
        "glasses",
        "earrings",
    )

    CAMERA_ARCHETYPES: Dict[str, Dict[str, str]] = None  # type: ignore[assignment]
    GENERATION_MODE_REGISTRY: Dict[str, Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.outfit_generator = OutfitGenerator()
        if self.CAMERA_ARCHETYPES is None:
            self.CAMERA_ARCHETYPES = {
                "front_selfie": {
                    "perspective": "front phone camera at arm length",
                    "framing": "front selfie, head-and-shoulders",
                    "device": "smartphone front camera",
                    "framing_mode": "front selfie, head-and-shoulders",
                    "allowed_wording": "front selfie, arm-length framing, close face crop",
                },
                "mirror_selfie": {
                    "perspective": "mirror reflection view",
                    "framing": "mirror selfie, phone visible in reflection, head-and-shoulders or waist-up",
                    "device": "mirror geometry consistent",
                    "framing_mode": "mirror selfie, head-and-shoulders",
                    "allowed_wording": "mirror selfie, phone visible, reflection-consistent framing",
                },
                "candid_handheld": {
                    "perspective": "observer handheld perspective",
                    "framing": "candid 3/4 body or waist-up",
                    "device": "consumer smartphone rear camera",
                    "framing_mode": "candid handheld, 3/4 body",
                    "allowed_wording": "candid handheld, observer view, off-center frame",
                },
                "friend_shot": {
                    "perspective": "friend-shot conversational distance",
                    "framing": "3/4 body social frame",
                    "device": "consumer smartphone rear camera",
                    "framing_mode": "friend-shot, 3/4 body",
                    "allowed_wording": "friend-shot, 3/4 body, natural social distance",
                },
                "close_portrait": {
                    "perspective": "tight portrait perspective",
                    "framing": "close portrait, face dominant",
                    "device": "real lens behavior",
                    "framing_mode": "close portrait, face dominant",
                    "allowed_wording": "close portrait, face dominant, tight crop",
                },
                "seated_table_shot": {
                    "perspective": "seated eye-level across or beside table",
                    "framing": "waist-up seated candid with table context",
                    "device": "smartphone rear camera, available light",
                    "framing_mode": "waist-up seated candid",
                    "allowed_wording": "waist-up seated candid, table edge visible, hands interacting naturally",
                },
                "full_body": {
                    "perspective": "eye-level full-body perspective",
                    "framing": "full body, head-to-toe",
                    "device": "realistic smartphone lens",
                    "framing_mode": "full body, head-to-toe",
                    "allowed_wording": "full body, head-to-toe, entire stance visible",
                },
                "waist_up": {
                    "perspective": "eye-level waist-up framing",
                    "framing": "waist-up, torso centered with environment",
                    "device": "natural handheld rear camera",
                    "framing_mode": "waist-up candid",
                    "allowed_wording": "waist-up, torso visible, no full-body wording",
                },
            }
        if self.GENERATION_MODE_REGISTRY is None:
            self.GENERATION_MODE_REGISTRY = {
                "portrait_mode": {"shot_archetypes": ["close_portrait"], "negative": ["wax skin", "beauty filter"]},
                "waist-up_mode": {"shot_archetypes": ["waist_up"], "negative": ["broken torso proportions"]},
                "seated_lifestyle_mode": {"shot_archetypes": ["seated_table_shot"], "negative": ["impossible seated geometry", "feet on table unless explicitly requested"]},
                "full-body_mode": {"shot_archetypes": ["full_body", "friend_shot"], "negative": ["broken body proportions", "misaligned shoes", "distorted legs"]},
                "selfie_mode": {"shot_archetypes": ["front_selfie"], "negative": ["rear-camera perspective"]},
                "mirror_selfie_mode": {"shot_archetypes": ["mirror_selfie"], "negative": ["broken mirror reflection", "floating phone", "inconsistent reflection angle"]},
                "lifestyle_mode": {"shot_archetypes": ["candid_handheld", "friend_shot"], "negative": ["over-staged pose", "editorial fashion posture"]},
            }

    def load_blocks(self) -> Dict[str, str]:
        if self.state_store and hasattr(self.state_store, "load_prompt_blocks"):
            try:
                blocks = self.state_store.load_prompt_blocks() or {}
                if blocks:
                    return blocks
            except Exception:
                pass
        return {}

    def compose(self, context: Dict[str, Any], scene: Any, outfit_summary: str, content_type: str, outfit_item_ids: List[str] | None = None, platform_intent: str | None = None) -> str:
        return self.compose_package(context, scene, outfit_summary, content_type, outfit_item_ids, platform_intent)["final_prompt"]

    def compose_package(self, context: Dict[str, Any], scene: Any, outfit_summary: str, content_type: str, outfit_item_ids: List[str] | None = None, platform_intent: str | None = None) -> Dict[str, str]:
        blocks = self.load_blocks()
        recent = context.get("recent_moment_memory") or []
        shot_archetype = self._resolve_shot_archetype(scene, context, recent)
        generation_mode = self._resolve_generation_mode(scene, shot_archetype)
        scene_alignment = self._align_scene_geometry(scene, shot_archetype, generation_mode)
        shot_archetype = str(scene_alignment["shot_archetype"])
        generation_mode = str(scene_alignment["generation_mode"])
        platform_behavior = self._platform_behavior_intent(content_type, platform_intent)
        identity_manager = CharacterIdentityManager()
        identity_pack = identity_manager.load_pack()
        prompt_mode = "dense"
        framing_mode = str(scene_alignment["framing_mode"])

        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_desc = getattr(scene, "scene_moment", "") or getattr(scene, "description", "daily lifestyle moment")
        item_ids_text = ", ".join(outfit_item_ids or [])
        reference_selection = identity_manager.select_reference_bundle(shot_archetype, generation_mode, identity_pack)
        behavior = context.get("behavioral_context")

        identity_anchor = identity_manager.identity_anchor(context, identity_pack)
        body_anchor_shot = "full_body" if generation_mode == "full-body_mode" and shot_archetype == "friend_shot" else shot_archetype
        body_anchor = identity_manager.body_anchor(body_anchor_shot, context, identity_pack)
        scene_action = self._scene_action(scene, scene_desc, scene_loc)
        outfit_bundle, outfit_source = self._resolve_outfit_bundle(context, scene, outfit_summary)
        normalized_outfit = self._normalize_outfit_sentence_for_prompt(outfit_bundle.outfit_sentence or outfit_bundle.sentence, scene, context)
        outfit_scene_props = self._extract_scene_props_from_outfit_text(
            " ".join(
                part
                for part in [
                    str(outfit_bundle.outfit_sentence or ""),
                    str(outfit_bundle.sentence or ""),
                    str(outfit_summary or ""),
                ]
                if str(part or "").strip()
            )
        )
        presence_layer = self._presence_layer(context, scene, outfit_bundle, shot_archetype, platform_behavior)
        perceived_outfit = self._perceived_outfit_sentence(outfit_bundle, normalized_outfit, scene, context)
        imperfect_layer = self._imperfect_reality_layer(
            context=context,
            scene=scene,
            outfit_bundle=outfit_bundle,
            shot_archetype=shot_archetype,
            platform_behavior=platform_behavior,
            outfit_sentence=perceived_outfit,
        )
        wardrobe_block = self._wardrobe_context(outfit_bundle, shot_archetype, item_ids_text)
        camera_block = self._camera_context(shot_archetype, context)
        realism_block = self._realism_cues(shot_archetype, scene_loc)
        continuity_block = self._continuity_cues(context, scene)
        platform_block = self._platform_intent(context, content_type, platform_intent, platform_behavior)
        negative_prompt = self._negative_prompt(shot_archetype, scene, scene_loc, platform_behavior, generation_mode)
        reference_bundle = self._reference_bundle(reference_selection)
        primary_anchors = ", ".join(reference_selection.get("primary_anchors", []))
        secondary_anchors = ", ".join(reference_selection.get("secondary_anchors", []))
        manual_step = self._manual_generation_step(reference_selection)
        stored_outfit_sentence = self._clean_fragment(str(context.get("outfit_sentence") or "")) or normalized_outfit

        # backward-compatible keys (v3)
        ordered_blocks = {
            "identity_core": self._identity_core(context),
            "identity_anchor": identity_anchor,
            "body_anchor": body_anchor,
            "scene_action": scene_action,
            "wardrobe_block": wardrobe_block,
            "outfit_structured": outfit_bundle.to_dict(),
            "outfit_struct": outfit_bundle.to_dict(),
            "outfit_struct_json": json.dumps(outfit_bundle.to_dict(), ensure_ascii=False),
            "outfit_sentence": stored_outfit_sentence,
            "outfit_summary": stored_outfit_sentence,
            "outfit_perceived_sentence": perceived_outfit,
            "camera_block": camera_block,
            "realism_block": realism_block,
            "continuity_block": continuity_block,
            "presence_layer": presence_layer["summary"],
            "micro_body_behavior": presence_layer["micro_body_behavior"],
            "interaction_realism": presence_layer["interaction_realism"],
            "anti_model_symmetry": presence_layer["anti_model_symmetry"],
            "camera_distance_hint": presence_layer["camera_distance"],
            "platform_intent": platform_block,
            "prompt_mode": prompt_mode,
            "generation_mode": generation_mode,
            "framing_mode": framing_mode,
            "reference_bundle": reference_bundle,
            "reference_primary_type": reference_selection.get("requested_type", ""),
            "reference_selected": reference_selection.get("selected", ""),
            "reference_primary_anchors": primary_anchors,
            "reference_secondary_anchors": secondary_anchors,
            "reference_manual_step": manual_step,
            "identity_mode": "reference_manifest" if identity_pack.reference_types else ("legacy_reference_pack" if identity_pack.references else "dna_fallback"),
            "reference_pack_type": reference_selection.get("requested_type", ""),
            "life_continuity_context": continuity_block,
            "scene_context": scene_action,
            "wardrobe_context": wardrobe_block,
            "camera_context": camera_block,
            "framing_style": "imperfect framing, real handheld balance",
            "camera_physics": "handheld motion with gravity-consistent body pose",
            "sensor_realism": "smartphone dynamic range with mild grain in low light",
            "smartphone_behavior": "natural smartphone photo, candid realism, grounded lifestyle styling, believable available light",
            "social_behavior": self._social_behavior(platform_behavior),
            "micro_imperfections": self._micro_imperfections(scene_loc, platform_behavior),
            "camera_behavior_memory": self._camera_behavior_memory(shot_archetype, context, context.get("continuity_context") or {}, recent),
            "face_consistency": self._face_consistency_layer(context),
            "device_identity": self._device_identity_layer(shot_archetype, context, platform_behavior, self._primary_device_profile(context)),
            "favorite_locations": self._favorite_location_memory_layer(context, scene_loc, context.get("continuity_context") or {}),
            "composition_and_lighting": f"{self._lighting_hint(getattr(scene, 'time_of_day', 'day'))}; natural posture; gravity-consistent pose.",
            "realism_cues": realism_block,
            "continuity_cues": continuity_block,
            "anti_generic_constraints": self._anti_generic_constraints_layer(),
            "persona_voice_cues": self._persona_voice_cues(context),
            "negative_prompt": negative_prompt,
            "video_motion": "subtle body movement with stable identity",
            "video_camera_motion": "light handheld or slow tripod drift",
            "behavior_state": (
                f"energy={getattr(behavior, 'energy_level', '')}; social={getattr(behavior, 'social_mode', '')}; "
                f"arc={getattr(behavior, 'emotional_arc', '')}; habit={getattr(behavior, 'habit', '')}; "
                f"place={getattr(behavior, 'place_anchor', '')}; objects={', '.join(getattr(behavior, 'objects', []) or [])}; "
                f"self={getattr(behavior, 'self_presentation', '')}"
            ),
        }

        prompt_payload = self._build_final_prompt(
            prompt_mode=prompt_mode,
            identity_anchor=identity_anchor,
            body_anchor=body_anchor,
            framing_mode=framing_mode,
            context=context,
            shot_archetype=shot_archetype,
            scene=scene,
            scene_desc=scene_desc,
            scene_loc=scene_loc,
            outfit_sentence=perceived_outfit,
            realism_block=realism_block,
            continuity_block=continuity_block,
            device_identity=ordered_blocks["device_identity"],
            social_behavior=ordered_blocks["social_behavior"],
            scene_tags=scene_alignment.get("scene_tags", []),
            outfit_scene_props=outfit_scene_props,
            presence_layer=presence_layer,
            imperfect_layer=imperfect_layer,
        )
        final_prompt = str(prompt_payload["prompt"])
        prompt_mode = self._prompt_mode(final_prompt)
        ordered_blocks["final_prompt"] = final_prompt
        ordered_blocks["prompt_format_version"] = self.CANONICAL_PROMPT_VERSION
        ordered_blocks["prompt_style_version"] = str(
            prompt_payload.get("prompt_style_version") or self.PROMPT_STYLE_VERSION
        )
        ordered_blocks["shot_archetype"] = shot_archetype
        ordered_blocks["platform_behavior"] = platform_behavior
        ordered_blocks["generation_mode"] = generation_mode
        ordered_blocks["framing_mode"] = framing_mode
        ordered_blocks["reference_type"] = str(reference_selection.get("requested_type", ""))
        ordered_blocks["primary_anchors"] = primary_anchors
        ordered_blocks["secondary_anchors"] = secondary_anchors
        ordered_blocks["manual_generation_step"] = manual_step
        ordered_blocks["prompt_mode"] = prompt_mode
        ordered_blocks["outfit_source"] = outfit_source
        ordered_blocks["scene_source"] = str(getattr(scene, "scene_source", getattr(scene, "source", "unknown")) or "unknown")
        ordered_blocks["behavior_source"] = str(getattr(behavior, "source", "none") or "none")
        ordered_blocks["duplicate_clauses"] = list(prompt_payload.get("duplicate_clauses", []))
        ordered_blocks["duplicate_sequence_candidates"] = list(prompt_payload.get("duplicate_sequence_candidates", []))
        ordered_blocks["duplicate_sequence_removed"] = list(prompt_payload.get("duplicate_sequence_removed", []))
        ordered_blocks["duplicate_sequence_kept_reason"] = list(prompt_payload.get("duplicate_sequence_kept_reason", []))
        ordered_blocks["sanitized_prompt_applied"] = bool(prompt_payload.get("sanitized_prompt_applied"))
        ordered_blocks["rewrite_pass_applied"] = bool(prompt_payload.get("rewrite_pass_applied"))
        ordered_blocks["rewrite_diagnostics"] = dict(prompt_payload.get("rewrite_diagnostics") or {})
        ordered_blocks["fallback_prompt_applied"] = bool(prompt_payload.get("fallback_prompt_applied"))
        ordered_blocks["final_prompt_length"] = len(final_prompt)
        ordered_blocks["post_sanitize_prompt_length"] = int(prompt_payload.get("post_sanitize_prompt_length") or len(final_prompt))
        ordered_blocks["post_sanitize_validation_result"] = str(prompt_payload.get("post_sanitize_validation_result") or "")
        ordered_blocks["objects_inserted"] = list(self._behavior_object_terms(context, scene))
        ordered_blocks["prompt_block_names"] = ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        ordered_blocks["prompt_blocks"] = dict(prompt_payload.get("prompt_blocks", {}))
        return ordered_blocks

    @staticmethod
    def _prompt_mode(prompt: str) -> str:
        normalized = (prompt or "").strip()
        blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
        framing_block = blocks[1].lower() if len(blocks) > 1 else ""
        expanded_blocks = 0
        for block in blocks:
            _, _, body = block.partition(":")
            body_text = body.strip() or block
            if (
                len(body_text) >= PromptComposer.EXPANDED_BLOCK_BODY_THRESHOLD
                or body_text.count(",") >= 2
                or body_text.count(";") >= 2
            ):
                expanded_blocks += 1

        if "selfie" in framing_block and len(normalized) < 1550:
            return "compact"
        if len(normalized) > PromptComposer.COMPACT_PROMPT_THRESHOLD and expanded_blocks >= PromptComposer.DENSE_PROMPT_EXPANDED_BLOCKS:
            return "dense"
        if len(normalized) >= PromptComposer.DENSE_PROMPT_MIN_LENGTH and expanded_blocks >= PromptComposer.DENSE_PROMPT_EXPANDED_BLOCKS:
            return "dense"
        if len(blocks) == 6 and len(normalized) >= PromptComposer.STRUCTURED_DENSE_PROMPT_MIN_LENGTH and expanded_blocks >= PromptComposer.STRUCTURED_DENSE_EXPANDED_BLOCKS:
            return "dense"
        return "compact"

    def _identity_floor_defaults(self, context: Dict[str, Any]) -> Dict[str, str]:
        profile = context.get("character_profile") or {}
        age = self._ensure_english_fragment(profile.get("age", "22"), "22")

        face = self._ensure_english_fragment(
            profile.get("appearance_face_shape") or profile.get("face_shape") or "soft oval face",
            "soft oval face",
        )
        if "face" not in face.lower():
            face = f"{face} face"

        jawline = self._ensure_english_fragment(profile.get("jawline") or "gentle defined jawline", "gentle defined jawline")

        nose = self._ensure_english_fragment(profile.get("nose") or profile.get("nose_bridge") or "straight natural nose", "straight natural nose")
        if "nose" not in nose.lower():
            nose = f"{nose} natural nose"

        eyes = self._ensure_english_fragment(profile.get("eyes") or profile.get("appearance_eye_color") or "green almond eyes", "green almond eyes")
        if "eye" not in eyes.lower():
            eyes = f"{eyes} almond eyes"

        lips = self._ensure_english_fragment(profile.get("lips") or profile.get("lip_fullness") or "natural medium lips", "natural medium lips")
        if "lip" not in lips.lower():
            lips = f"{lips} lips"

        skin = self._ensure_english_fragment(profile.get("skin_realism_profile") or profile.get("skin") or "natural skin texture", "natural skin texture")
        if "skin" not in skin.lower() and "texture" not in skin.lower() and "freckle" not in skin.lower():
            skin = f"{skin} skin texture"

        hair = self._ensure_english_fragment(profile.get("hair") or profile.get("appearance_hair_color") or "light chestnut medium-length hair", "light chestnut medium-length hair")
        if "hair" not in hair.lower():
            hair = f"{hair} medium-length hair"

        return {
            "age": age,
            "face": face,
            "jawline": jawline,
            "nose": nose,
            "eyes": eyes,
            "lips": lips,
            "skin": skin,
            "hair": hair,
        }

    def _identity_floor_cue_count(self, identity_body: str) -> int:
        lowered = self._clean_fragment(identity_body).lower()
        patterns = {
            "face": r"\b(face|oval|round|square|heart-shaped|cheek contour|cheekbone)\b",
            "jawline": r"\bjaw(line)?\b",
            "nose": r"\bnose\b",
            "eyes": r"\beye|eyes|brow|brows\b",
            "lips": r"\blip|lips\b",
            "skin": r"\bskin|texture|freckle|complexion\b",
            "hair": r"\bhair\b",
        }
        return sum(1 for pattern in patterns.values() if re.search(pattern, lowered))

    def _recover_identity_body(self, identity_body: str, context: Dict[str, Any], *, force_floor: bool = False) -> str:
        repaired = self._repair_duplicate_sequences_in_text(identity_body, aggressive=True)
        if repaired and not force_floor and self._identity_floor_cue_count(repaired) >= self.IDENTITY_FLOOR_MIN_CUES:
            return repaired

        defaults = self._identity_floor_defaults(context)
        age = next((match.group(0) for match in [re.search(r"\b\d{2}(?:-year-old)?\b", repaired)] if match), defaults["age"])
        if age.isdigit():
            age = f"{age}-year-old"

        cues = [defaults[key] for key in self.IDENTITY_FLOOR_ORDER if defaults.get(key)]
        lead = f"a {age} woman with {self._human_join(cues)}"

        support_cues: List[str] = []
        if "shoulder" in repaired.lower():
            support_cues.append("relaxed shoulders")
        if "posture" in repaired.lower():
            support_cues.append("natural upright posture")
        if support_cues:
            lead = f"{lead}, {self._human_join(support_cues[:2])}"
        return self._clean_fragment(lead)

    def _resolve_generation_mode(self, scene: Any, shot_archetype: str) -> str:
        explicit = getattr(scene, "generation_mode", "")
        if explicit and explicit in self.GENERATION_MODE_REGISTRY:
            if shot_archetype in self.GENERATION_MODE_REGISTRY[explicit].get("shot_archetypes", []):
                return explicit
        for mode, cfg in self.GENERATION_MODE_REGISTRY.items():
            if shot_archetype in cfg.get("shot_archetypes", []):
                return mode
        return "lifestyle_mode"

    def _framing_mode(self, shot_archetype: str, generation_mode: str) -> str:
        camera_profile = self.CAMERA_ARCHETYPES.get(shot_archetype, self.CAMERA_ARCHETYPES["friend_shot"])
        framing = camera_profile.get("framing_mode", camera_profile.get("framing", shot_archetype))
        if generation_mode == "selfie_mode":
            return "front selfie, head-and-shoulders"
        if generation_mode == "mirror_selfie_mode":
            return "mirror selfie, head-and-shoulders"
        return framing

    def _align_scene_geometry(self, scene: Any, shot_archetype: str, generation_mode: str) -> Dict[str, Any]:
        lowered = self._scene_text(scene).lower()
        lowered_core = " ".join(
            [
                str(getattr(scene, "scene_moment", "") or ""),
                str(getattr(scene, "description", "") or ""),
                str(getattr(scene, "location", "") or ""),
                str(getattr(scene, "activity", "") or ""),
                str(getattr(scene, "visual_focus", "") or ""),
            ]
        ).lower()
        lowered_moment_type = str(getattr(scene, "scene_moment_type", "") or "").lower()
        explicit_shot = str(getattr(scene, "camera_archetype", "") or getattr(scene, "shot_archetype", "") or "")
        explicit_camera_locked = explicit_shot in self.CAMERA_ARCHETYPES
        is_travel = any(token in lowered for token in ["airport", "terminal", "travel", "flight", "layover", "boarding"])
        has_luggage = any(token in lowered for token in ["luggage", "suitcase", "carry-on", "carry on", "roller bag", "shoulder bag"])
        is_walking = any(token in lowered for token in ["walking", "walk", "stroll", "moving through", "crossing"])
        is_seated = any(token in lowered for token in ["seated", "sitting", "table", "coffee", "window seat", "waiting"])
        is_selfie = (
            "selfie" in lowered_core
            or "mirror" in lowered_core
            or (
                lowered_moment_type in {"selfie", "diary_mirror"}
                and not explicit_camera_locked
                and not (is_travel and is_walking and has_luggage)
            )
        )

        aligned_shot = shot_archetype
        if is_selfie:
            aligned_shot = "mirror_selfie" if "mirror" in lowered else "front_selfie"
        elif is_travel and is_walking and has_luggage:
            aligned_shot = "friend_shot"
        elif is_seated and shot_archetype in {"friend_shot", "full_body", "waist_up"}:
            aligned_shot = "seated_table_shot"

        aligned_generation = self._resolve_generation_mode(scene, aligned_shot)
        if aligned_shot == "friend_shot" and is_travel and is_walking and has_luggage:
            aligned_generation = "full-body_mode"

        return {
            "shot_archetype": aligned_shot,
            "generation_mode": aligned_generation,
            "framing_mode": self._coherent_framing_mode(aligned_shot, aligned_generation, lowered),
            "scene_tags": self._scene_tags(lowered, aligned_shot),
        }

    def _coherent_framing_mode(self, shot_archetype: str, generation_mode: str, lowered_scene_text: str) -> str:
        is_travel_walk = (
            any(token in lowered_scene_text for token in ["airport", "terminal", "travel", "layover"])
            and any(token in lowered_scene_text for token in ["walking", "walk", "stroll"])
            and any(token in lowered_scene_text for token in ["luggage", "suitcase", "carry-on", "carry on", "bag"])
        )
        if shot_archetype == "mirror_selfie":
            return "mirror selfie, waist-up" if "waist" in lowered_scene_text or "outfit" in lowered_scene_text else "mirror selfie, head-and-shoulders"
        if shot_archetype == "front_selfie":
            return "front selfie, head-and-shoulders"
        if shot_archetype == "seated_table_shot":
            return "waist-up seated candid"
        if shot_archetype == "full_body":
            return "full body, head-to-toe"
        if shot_archetype == "friend_shot" and is_travel_walk:
            return "3/4 body walking shot"
        if generation_mode == "full-body_mode" and shot_archetype in {"friend_shot", "candid_handheld"}:
            return "3/4 body shot"
        return self._framing_mode(shot_archetype, generation_mode)

    @staticmethod
    def _scene_text(scene: Any) -> str:
        return " ".join(
            [
                str(getattr(scene, "scene_moment", "") or ""),
                str(getattr(scene, "description", "") or ""),
                str(getattr(scene, "location", "") or ""),
                str(getattr(scene, "activity", "") or ""),
                str(getattr(scene, "visual_focus", "") or ""),
                str(getattr(scene, "scene_moment_type", "") or ""),
            ]
        )

    @staticmethod
    def _scene_tags(lowered_scene_text: str, shot_archetype: str) -> List[str]:
        tags: List[str] = []
        is_travel = any(token in lowered_scene_text for token in ["airport", "terminal", "travel", "flight", "layover", "boarding"])
        is_uniform = any(token in lowered_scene_text for token in ["uniform", "crew_member_in_uniform", "in uniform"])
        is_between_flights = any(token in lowered_scene_text for token in ["layover", "between flights", "between-flight", "before boarding"])
        if is_travel and not is_uniform:
            if is_between_flights:
                tags.append("off-duty crew member between flights in a casual travel look")
            else:
                tags.append("off-duty crew member in a casual layover travel look")
        if shot_archetype in {"friend_shot", "full_body", "candid_handheld"} and any(
            token in lowered_scene_text for token in ["luggage", "suitcase", "carry-on", "carry on"]
        ):
            tags.append("carry-on luggage stays visible in frame")
        if any(token in lowered_scene_text for token in ["terminal", "airport"]):
            tags.append("real terminal architecture, subtle reflections, rare non-dominant background travelers")
        if is_travel and shot_archetype in {"friend_shot", "full_body", "candid_handheld"}:
            tags.append("walking pose stays physically plausible and luggage appears only if framing allows it")
        if shot_archetype in {"front_selfie", "mirror_selfie"}:
            tags.append("phone presence is natural to the shot")
        return tags

    @staticmethod
    def _reference_bundle(reference_selection: Dict[str, Any]) -> str:
        requested_type = str(reference_selection.get("requested_type") or "face")
        legacy_key = str(reference_selection.get("legacy_key") or "face_reference")
        selected = str(reference_selection.get("selected") or "fallback_character_dna")
        primary = ",".join(reference_selection.get("primary_anchors", []))
        secondary = ",".join(reference_selection.get("secondary_anchors", []))
        pack_ready = bool(reference_selection.get("pack_ready"))
        return (
            f"preferred_type={requested_type}; preferred={legacy_key}; selected={selected}; "
            f"primary={primary or '-'}; secondary={secondary or '-'}; pack_ready={pack_ready}"
        )

    @staticmethod
    def _identity_core(context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        return (
            f"identity DNA: hair={profile.get('appearance_hair_color', 'light chestnut')}; "
            f"eyes={profile.get('appearance_eye_color', 'green')}; "
            f"face={profile.get('appearance_face_shape', 'soft oval')}; "
            f"body={profile.get('appearance_body_type', 'slim natural build')}"
        )

    @staticmethod
    def _wardrobe_context(outfit_bundle: Any, shot_archetype: str, outfit_item_ids: str) -> str:
        visible_scope = "upper-body focus" if shot_archetype in {"front_selfie", "close_portrait", "mirror_selfie", "seated_table_shot", "waist_up"} else "full outfit coherence"
        sentence = str(getattr(outfit_bundle, "outfit_sentence", "") or getattr(outfit_bundle, "sentence", "") or "")
        return f"outfit: {sentence} || {visible_scope}; item_ids={outfit_item_ids}."

    def _resolve_outfit_bundle(self, context: Dict[str, Any], scene: Any, outfit_summary: str) -> tuple[OutfitBundle, str]:
        manual_override = self.outfit_generator._resolve_manual_override(scene, context)
        canonical_sentence = self._clean_fragment(str(context.get("outfit_sentence") or ""))
        canonical_struct = self._coerce_outfit_struct(context.get("outfit_struct"), context.get("outfit_struct_json"))

        if manual_override:
            return self._generate_outfit_bundle(context, scene, outfit_summary, source="manual_override"), "manual_override"

        if canonical_sentence:
            try:
                return self._bundle_from_canonical_sentence(
                    canonical_sentence,
                    canonical_struct,
                    scene=scene,
                    context=context,
                    fallback_summary=outfit_summary,
                ), "context.outfit_sentence"
            except PromptValidationError:
                pass

        if canonical_struct:
            structured_sentence = self._clean_fragment(
                str(canonical_struct.get("outfit_sentence") or canonical_struct.get("sentence") or canonical_struct.get("outfit_summary") or "")
            )
            if structured_sentence:
                try:
                    return self._bundle_from_canonical_sentence(
                        structured_sentence,
                        canonical_struct,
                        scene=scene,
                        context=context,
                        fallback_summary=outfit_summary,
                    ), "context.outfit_struct"
                except PromptValidationError:
                    pass

        legacy_summary = self._clean_fragment(outfit_summary)
        if legacy_summary:
            return self._generate_outfit_bundle(context, scene, legacy_summary, source="legacy.outfit_summary"), "generated_bundle"
        fallback_sentence = self._contextual_outfit_fallback_sentence(scene, context)
        fallback_bundle = self._bundle_from_canonical_sentence(
            fallback_sentence,
            self._outfit_struct_from_sentence(fallback_sentence),
            scene=scene,
            context=context,
            fallback_summary="",
        )
        return fallback_bundle, "contextual_fallback"

    def _generate_outfit_bundle(self, context: Dict[str, Any], scene: Any, outfit_summary: str, *, source: str) -> OutfitBundle:
        try:
            bundle = self.outfit_generator.generate_bundle(outfit_summary=outfit_summary, scene=scene, context=context)
        except ManualOutfitValidationError as exc:
            raise PromptValidationError(str(exc)) from exc
        except OutfitGenerationError:
            fallback_outfit = self._contextual_outfit_fallback_sentence(scene, context)
            try:
                bundle = self.outfit_generator.generate_bundle(
                    outfit_summary=fallback_outfit,
                    scene=scene,
                    context=context,
                )
            except (ManualOutfitValidationError, OutfitGenerationError) as exc:
                return self._bundle_from_canonical_sentence(
                    fallback_outfit,
                    self._outfit_struct_from_sentence(fallback_outfit),
                    scene=scene,
                    context=context,
                    fallback_summary="",
                )
        return self._bundle_from_canonical_sentence(
            str(bundle.outfit_sentence or bundle.sentence or ""),
            bundle.to_dict(),
            scene=scene,
            context=context,
            fallback_summary=outfit_summary,
        )

    def _bundle_from_canonical_sentence(
        self,
        outfit_sentence: str,
        outfit_struct: Mapping[str, Any] | None,
        *,
        scene: Any,
        context: Dict[str, Any],
        fallback_summary: str,
    ) -> OutfitBundle:
        struct = self._coerce_outfit_struct(outfit_struct)
        normalized_sentence = self.validate_outfit_sentence(outfit_sentence, outfit_struct=struct)
        derived_struct = self._outfit_struct_from_sentence(normalized_sentence)
        payload = {
            "top": str(struct.get("top") or derived_struct.get("top") or ""),
            "bottom": str(struct.get("bottom") or derived_struct.get("bottom") or ""),
            "outerwear": str(struct.get("outerwear") or derived_struct.get("outerwear") or ""),
            "shoes": str(struct.get("shoes") or derived_struct.get("shoes") or ""),
            "accessories": str(struct.get("accessories") or derived_struct.get("accessories") or ""),
            "fit": str(struct.get("fit") or derived_struct.get("fit") or ""),
            "fabric": str(struct.get("fabric") or derived_struct.get("fabric") or ""),
            "condition": str(struct.get("condition") or derived_struct.get("condition") or ""),
            "styling": str(struct.get("styling") or derived_struct.get("styling") or ""),
            "sentence": normalized_sentence,
            "outfit_sentence": normalized_sentence,
            "style_profile": list(struct.get("style_profile") or context.get("outfit_style_profile") or []),
            "place": str(struct.get("place") or getattr(scene, "location", "") or context.get("city", "") or ""),
            "activity": str(struct.get("activity") or getattr(scene, "activity", "") or ""),
            "time_of_day": str(struct.get("time_of_day") or getattr(scene, "time_of_day", "") or ""),
            "weather_context": str(struct.get("weather_context") or ""),
            "social_presence": str(struct.get("social_presence") or getattr(scene, "social_presence", "") or ""),
            "energy": str(struct.get("energy") or ""),
            "habit": str(struct.get("habit") or ""),
            "style_intensity": float(struct.get("style_intensity") or 0.0),
            "outfit_style": str(struct.get("outfit_style") or context.get("outfit_style") or ""),
            "enhance_attractiveness": float(struct.get("enhance_attractiveness") or 0.0),
            "outfit_override_used": str(struct.get("outfit_override_used") or ""),
        }
        if not payload["style_profile"]:
            payload["style_profile"] = list((context.get("outfit_struct") or {}).get("style_profile") or [])
        if not any(payload[key] for key in ("top", "bottom", "outerwear", "shoes", "accessories")) and fallback_summary:
            fallback_sentence = self._contextual_outfit_fallback_sentence(scene, context)
            return self._bundle_from_canonical_sentence(
                fallback_sentence,
                self._outfit_struct_from_sentence(fallback_sentence),
                scene=scene,
                context=context,
                fallback_summary="",
            )
        return OutfitBundle(**payload)

    @staticmethod
    def _coerce_outfit_struct(*candidates: Any) -> Dict[str, Any]:
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                return dict(candidate)
            if isinstance(candidate, str) and candidate.strip():
                try:
                    parsed = json.loads(candidate)
                except (TypeError, ValueError, json.JSONDecodeError):
                    continue
                if isinstance(parsed, Mapping):
                    return dict(parsed)
        return {}

    def _outfit_struct_from_sentence(self, outfit_sentence: str) -> Dict[str, str]:
        pieces, detail_parts, _ = self._split_outfit_scene_props(outfit_sentence)
        payload = {"top": "", "bottom": "", "outerwear": "", "shoes": "", "accessories": "", "fit": "", "fabric": "", "condition": "", "styling": ""}
        for piece in pieces:
            category = self._outfit_category(piece)
            if category == "dress":
                payload["top"] = payload["top"] or piece
                continue
            if category == "accessory":
                payload["accessories"] = payload["accessories"] or piece
                continue
            payload[category] = payload.get(category, "") or piece

        for detail in detail_parts:
            lowered = detail.lower()
            if not payload["fit"] and any(token in lowered for token in ["fit", "fitted", "relaxed", "silhouette", "drape"]):
                payload["fit"] = detail
            elif not payload["fabric"] and any(token in lowered for token in ["fabric", "fabrics", "texture", "textures", "matte", "cotton", "knit", "linen", "wool", "settling"]):
                payload["fabric"] = detail
            elif not payload["condition"] and any(token in lowered for token in ["fold", "folds", "worn", "wrinkle", "wrinkles", "crease", "creases", "bunching", "lived-in", "shifted", "arranged", "tension", "gathering"]):
                payload["condition"] = detail
            elif not payload["styling"]:
                payload["styling"] = detail
        return payload

    def _camera_context(self, shot_archetype: str, context: Dict[str, Any]) -> str:
        camera_profile = self.CAMERA_ARCHETYPES.get(shot_archetype, self.CAMERA_ARCHETYPES["friend_shot"])
        device_profile = self._primary_device_profile(context)
        return (
            f"{camera_profile['perspective']}; {camera_profile['framing']}; {camera_profile['device']}; "
            f"allowed wording={camera_profile.get('allowed_wording', '')}; {self._device_profile(device_profile, shot_archetype)}"
        )

    @staticmethod
    def _primary_device_profile(context: Dict[str, str]) -> Dict[str, str]:
        profile = context.get("character_profile") or {}
        raw = profile.get("primary_device_profile") if isinstance(profile.get("primary_device_profile"), dict) else {}
        return {
            "device_class": str(raw.get("device_class") or profile.get("device_profile") or "modern premium smartphone"),
            "front_camera_behavior": str(raw.get("front_camera_behavior") or "arm-length front camera behavior"),
            "rear_camera_behavior": str(raw.get("rear_camera_behavior") or "rear camera handheld behavior"),
            "processing_style": str(raw.get("processing_style") or "natural processing"),
            "lens_character": str(raw.get("expected_lens_character") or "24-28mm equivalent"),
            "mirror_rules": str(raw.get("screen_mirror_visibility_rules") or "consistent mirror phone silhouette"),
            "night_limitations": str(raw.get("night_indoor_limitations") or "mild grain at low light"),
            "phone_shape": str(raw.get("phone_shape") or profile.get("recurring_phone_device") or "rounded phone"),
        }

    @staticmethod
    def _device_profile(device_profile: Dict[str, str], shot_archetype: str) -> str:
        camera_mode = device_profile["front_camera_behavior"] if shot_archetype in {"front_selfie", "mirror_selfie"} else device_profile["rear_camera_behavior"]
        return f"primary_device_profile=device_class={device_profile['device_class']}; camera_mode={camera_mode}; lens_character={device_profile['lens_character']}"

    @staticmethod
    def _realism_cues(shot_archetype: str, scene_loc: str) -> str:
        return (
            "realism: natural smartphone photo, candid realism, lived-in environment, stable face geometry, same body proportions, "
            "natural skin texture, real fabric folds, grounded styling, believable available light; "
            f"shot={shot_archetype}; location={scene_loc}."
        )

    @staticmethod
    def _platform_intent(context: Dict[str, Any], content_type: str, platform_intent: str | None, behavior_mode: str) -> str:
        intent = PromptComposer._platform_behavior_intent(content_type, platform_intent)
        mapping = {
            "instagram_feed": "slightly curated but lived-in",
            "story_lifestyle": "spontaneous and diary-like",
            "reel_cover": "clear focal point with natural movement",
            "travel_candid": "environment-first realism",
            "private_mirror": "private mirror documentation",
        }
        return f"platform=Instagram; intent={intent}; behavior_mode={behavior_mode}; direction={mapping.get(intent, 'lifestyle')}"

    @staticmethod
    def _platform_behavior_intent(content_type: str, platform_intent: str | None) -> str:
        intent = (platform_intent or "").strip().lower()
        if intent:
            return intent
        if content_type in {"video", "reel"}:
            return "reel_cover"
        if content_type in {"story", "stories"}:
            return "story_lifestyle"
        return "instagram_feed"

    def _negative_prompt(self, shot_archetype: str, scene: Any, scene_loc: str, platform_behavior: str, generation_mode: str) -> str:
        universal = [
            "extra fingers", "deformed hands", "duplicate person", "plastic skin", "bad anatomy", "wrong limb placement",
            "generic model photo", "sterile beauty campaign polish", "wrong phone shape",
            "identity drift", "unstable face geometry", "inconsistent body proportions",
            "perfect styling", "overly trendy outfit", "runway fashion",
            "over-coordinated clothing", "impractical clothing for context", "perfectly symmetrical pose",
            "over-styled clothing", "staged body posture", "influencer aesthetic", "studio-perfect positioning",
            "centered perfect posture", "posed look",
        ]
        shot_specific = {
            "mirror_selfie": ["broken mirror reflection", "floating phone", "inconsistent reflection angle", "duplicated hand", "impossible reflection geometry"],
            "front_selfie": ["rear-camera perspective", "detached floating arm"],
            "seated_table_shot": ["impossible seated geometry", "broken ankle angle", "floating shoe", "impossible chair contact"],
            "full_body": ["broken body proportions", "misaligned shoes", "distorted legs", "inconsistent torso length"],
            "friend_shot": ["broken body proportions", "distorted legs"],
        }
        location_specific: List[str] = []
        scene_text = " ".join(
            [
                str(scene_loc or "").lower(),
                str(getattr(scene, "scene_moment", "") or "").lower(),
                str(getattr(scene, "description", "") or "").lower(),
            ]
        )
        if "kitchen" in scene_text:
            location_specific.extend(["broken mug handle", "impossible cup grip"])
        if "street" in scene_text or "city" in scene_text:
            location_specific.append("impossible pedestrian scale")
        if any(token in scene_text for token in ["airport", "terminal", "travel", "flight", "luggage", "suitcase"]):
            location_specific.extend(["broken luggage handle", "impossible suitcase wheels", "warped airport perspective", "duplicate background people", "inconsistent walking pose"])
        mode_negative = self.GENERATION_MODE_REGISTRY.get(generation_mode, {}).get("negative", [])
        platform_negative = ["overproduced ad lighting"] if platform_behavior == "story_lifestyle" else []
        return ", ".join(dict.fromkeys(universal + shot_specific.get(shot_archetype, []) + location_specific + platform_negative + mode_negative))

    @staticmethod
    def _continuity_cues(context: Dict[str, Any], scene: Any) -> str:
        continuity = context.get("continuity_context") or {}
        arc = continuity.get("arc_hint", "stable_routine")
        hint = "same recurring woman across days with believable micro-variation"
        if arc == "arrival_and_adaptation":
            hint = "subtle arrival cues like not fully unpacked luggage"
        elif arc == "same_mode_continuation":
            hint = "routine confidence and settled posture"
        elif arc == "recovery_continuation":
            hint = "gentle pace and low-energy body language"
        return f"continuity: arc={arc}; hint={hint}; previous_evening={continuity.get('previous_evening_moment', '')}; signature={getattr(scene, 'moment_signature', '')}."

    @staticmethod
    def _device_identity_layer(shot_archetype: str, context: Dict[str, Any], platform_behavior: str, device_profile: Dict[str, str]) -> str:
        recurring_device = (context.get("character_profile") or {}).get("recurring_phone_device") or "personal smartphone"
        return f"capture chain consistent with recurring device={recurring_device}; phone shape={device_profile['phone_shape']}; mode={platform_behavior}; shot={shot_archetype}"

    @staticmethod
    def _camera_behavior_memory(shot_archetype: str, context: Dict[str, Any], continuity: Dict[str, Any], recent_moment_memory: List[Dict[str, Any]]) -> str:
        behavior = continuity.get("camera_behavior_memory") if isinstance(continuity.get("camera_behavior_memory"), dict) else {}
        if not behavior:
            behavior = (context.get("character_profile") or {}).get("camera_behavior_memory") or {}
        preferred = behavior.get("preferred_shot_archetypes") or ["candid_handheld", "friend_shot"]
        return (
            f"preferred_shot_archetypes={preferred}; average_camera_distance={behavior.get('average_camera_distance', '1.2m')}; "
            f"preferred_framing_style={behavior.get('preferred_framing_style', 'eye-level')}; selfie_frequency={behavior.get('selfie_frequency', 'rare')}"
        )

    @staticmethod
    def _social_behavior(platform_behavior: str) -> str:
        if platform_behavior == "instagram_feed":
            return "slightly curated social behavior with natural asymmetry"
        if platform_behavior == "story_lifestyle":
            return "spontaneity-first diary behavior with lived-in movement"
        return "spontaneity and lived-in environment cues"

    @staticmethod
    def _micro_imperfections(scene_loc: str, platform_behavior: str) -> str:
        base = [
            "slightly shifted chair angle",
            "book or notebook not perfectly centered",
            "blanket or coat crease consistent with recent use",
        ]
        if "home" in scene_loc.lower():
            base.append("small lived-in room asymmetry")
        if platform_behavior == "instagram_feed":
            base.append("still clean enough for feed but not commercial perfect")
        return f"micro imperfections: {', '.join(base)}."

    @staticmethod
    def _face_consistency_layer(context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        return (
            f"face consistency signature: {profile.get('face_signature', 'soft brows, gentle cheek contour, familiar lip shape')}; "
            f"face_shape={profile.get('face_shape', profile.get('appearance_face_shape', 'soft oval'))}; "
            f"nose_bridge={profile.get('nose_bridge', 'straight')}; cheekbone_softness={profile.get('cheekbone_softness', 'soft')}; "
            f"lip_fullness={profile.get('lip_fullness', 'medium-full')}; brow_style={profile.get('brow_style', 'natural')}"
        )

    @staticmethod
    def _favorite_location_memory_layer(context: Dict[str, Any], scene_loc: str, continuity: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        favorites = [
            x.strip()
            for x in str(profile.get("favorite_locations") or "kitchen window corner, favorite cafe table").split(",")
            if x.strip()
        ]
        recurring = [
            x.strip()
            for x in str(profile.get("recurring_spaces") or "living room sofa, hallway mirror").split(",")
            if x.strip()
        ]
        selected = next((spot for spot in favorites + recurring if spot.lower() in scene_loc.lower()), favorites[0] if favorites else "familiar place")
        return f"favorite location memory: favorite_locations={favorites}; recurring_spaces={recurring}; selected_recurring_anchor={selected}; recurrence_reason={continuity.get('arc_hint', 'routine continuity')}."

    @staticmethod
    def _anti_generic_constraints_layer() -> str:
        return "forbid generic AI wording and campaign aesthetics: no sterile commercial vibe, no luxury polish, no editorial over-posing."

    @staticmethod
    def _clean_generic_prompt_terms(text: str) -> str:
        cleaned = text
        for token in PromptComposer.BANNED_SYNTHETIC_PATTERNS:
            cleaned = cleaned.replace(token, "")
            cleaned = cleaned.replace(token.title(), "")
            cleaned = cleaned.replace(token.upper(), "")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r" *\n *", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _resolve_shot_archetype(self, scene: Any, context: Dict[str, Any], recent_moment_memory: List[Dict[str, Any]]) -> str:
        explicit = getattr(scene, "camera_archetype", "") or getattr(scene, "shot_archetype", "")
        if explicit and explicit in self.CAMERA_ARCHETYPES:
            return explicit
        text = " ".join([str(getattr(scene, "scene_moment", "")).lower(), str(getattr(scene, "description", "")).lower()])
        if "mirror" in text:
            return "mirror_selfie"
        if "selfie" in text:
            return "front_selfie"
        if "portrait" in text:
            return "close_portrait"
        if "table" in text or "coffee" in text or "seated" in text:
            return "seated_table_shot"
        if "full body" in text or "full-body" in text or "head-to-toe" in text:
            return "full_body"
        if "waist" in text:
            return "waist_up"
        if "candid" in text:
            return "candid_handheld"
        return "friend_shot"

    @staticmethod
    def _lighting_hint(time_of_day: str) -> str:
        return {
            "early_morning": "cool early morning light",
            "morning": "soft morning daylight",
            "late_morning": "clean late-morning daylight",
            "noon": "bright overhead daylight",
            "afternoon": "neutral afternoon light",
            "golden_hour": "warm directional golden hour light",
            "evening": "warm evening ambient light",
            "night": "mixed city and practical interior light",
        }.get(str(time_of_day or "").lower(), "natural soft light")

    @staticmethod
    def _scene_action(scene: Any, scene_desc: str, scene_loc: str) -> str:
        activity = str(getattr(scene, "activity", "") or "").strip()
        mood = str(getattr(scene, "mood", "") or "").strip()
        time_of_day = str(getattr(scene, "time_of_day", "") or "").strip()
        visual_focus = str(getattr(scene, "visual_focus", "") or "").strip()
        bits = [scene_desc, f"location={scene_loc}"]
        if activity:
            bits.append(f"action={activity}")
        if visual_focus:
            bits.append(f"visible focus={visual_focus}")
        if mood:
            bits.append(f"expression mood={mood}")
        if time_of_day:
            bits.append(f"time={time_of_day}")
        return "; ".join(bits) + "."

    @staticmethod
    def _persona_voice_cues(context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        voice = context.get("persona_voice") or {}
        restraint = voice.get("restraint", profile.get("voice_restrain", "medium"))
        reflection = voice.get("reflection", 0.65)
        self_irony = voice.get("self_irony", 0.3)
        return f"voice restraint={restraint}; reflection={reflection}; self_irony={self_irony}"

    @staticmethod
    def _manual_generation_step(reference_selection: Dict[str, Any]) -> str:
        primary = len(reference_selection.get("primary_anchors", []) or [])
        secondary = len(reference_selection.get("secondary_anchors", []) or [])
        if primary >= 3 and secondary:
            return "Attach 2-3 primary anchors, add 1 secondary anchor only if needed."
        if primary >= 2:
            return "Attach 2-3 primary anchors, add 1 secondary anchor if the generator starts drifting."
        if primary == 1:
            return "Attach the main primary anchor, then add 1-2 supporting anchors if needed."
        return "Attach the selected identity anchors manually before starting the render."

    def _build_final_prompt(
        self,
        *,
        prompt_mode: str,
        identity_anchor: str,
        body_anchor: str,
        framing_mode: str,
        context: Dict[str, Any],
        shot_archetype: str,
        scene: Any,
        scene_desc: str,
        scene_loc: str,
        outfit_sentence: str,
        realism_block: str,
        continuity_block: str,
        device_identity: str,
        social_behavior: str,
        scene_tags: List[str],
        outfit_scene_props: List[str],
        presence_layer: Dict[str, Any],
        imperfect_layer: Dict[str, Any],
    ) -> Dict[str, Any]:
        del prompt_mode, device_identity, social_behavior

        block_map = {
            "Identity": self._identity_block(identity_anchor=identity_anchor, body_anchor=body_anchor),
            "Framing": self._framing_block(framing_mode, shot_archetype, scene, presence_layer.get("camera_distance", "")),
            "Scene": self._scene_block(context, scene, scene_desc, scene_loc, scene_tags, presence_layer, outfit_scene_props),
            "Outfit": self._outfit_block(outfit_sentence),
            "Environment": self._environment_block(context, scene, scene_loc, scene_tags, continuity_block),
            "Mood": self._mood_block(context, scene, continuity_block, presence_layer),
        }
        block_map = self._apply_imperfect_reality_layer(
            block_map,
            scene=scene,
            context=context,
            shot_archetype=shot_archetype,
            imperfect_layer=imperfect_layer,
        )
        blocks = [
            block_map["Identity"],
            block_map["Framing"],
            block_map["Scene"],
            block_map["Outfit"],
            block_map["Environment"],
            block_map["Mood"],
        ]
        prompt = "\n\n".join(block.strip() for block in blocks if block.strip())
        raw_pre_rewrite_prompt = prompt
        finalized = self.finalize_canonical_prompt(
            prompt,
            scene,
            context,
            outfit_sentence=outfit_sentence,
            shot_archetype=shot_archetype,
            step="build_final_prompt",
            apply_rewrite=True,
            allow_fallback=True,
        )
        prompt = str(finalized.get("prompt") or prompt)
        final_blocks = dict(finalized.get("prompt_blocks") or {})
        finalized["prompt_blocks"] = final_blocks
        finalized["prompt_style_version"] = self.PROMPT_STYLE_VERSION
        logger.info(
            "prompt_rewrite_trace scene=%s raw_pre_rewrite_prompt=%r post_rewrite_prompt=%r prompt_style_version=%s",
            str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or "unknown_scene"),
            raw_pre_rewrite_prompt,
            prompt,
            self.PROMPT_STYLE_VERSION,
        )
        finalized["prompt"] = prompt
        return finalized

    @classmethod
    def expected_prompt_style_version(cls) -> str:
        return cls.PROMPT_STYLE_VERSION

    @classmethod
    def prompt_style_diagnostics(cls, prompt: str, *, prompt_style_version: str = "") -> Dict[str, Any]:
        normalized = str(prompt or "").strip()
        blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]

        def block_body(index: int) -> str:
            if index >= len(blocks):
                return ""
            _, _, body = blocks[index].partition(":")
            return (body.strip() or blocks[index].strip()).strip()

        identity_body = block_body(0)
        scene_body = block_body(2).lower()
        outfit_body = block_body(3).lower()
        mood_body = block_body(5).lower()

        scene_banned_phrases = [phrase for phrase in cls.REWRITE_FORBIDDEN_SCENE_PHRASES if phrase in scene_body]
        outfit_scene_props = [token for token in cls.SCENE_PROP_TOKENS if token in outfit_body]
        mood_label_like = (
            bool(mood_body)
            and (
                "self-presentation" in mood_body
                or mood_body.endswith(" mood")
                or mood_body in cls.REWRITE_FORBIDDEN_MOOD_PHRASES
            )
        )
        legacy_signatures: List[str] = []
        if identity_body.count(";") > 0:
            legacy_signatures.append("identity_semicolons")
        if scene_banned_phrases:
            legacy_signatures.append("scene_legacy_phrases")
        if outfit_scene_props:
            legacy_signatures.append("outfit_scene_props")
        if mood_label_like:
            legacy_signatures.append("mood_label_like")

        prompt_style_version_current = not prompt_style_version or prompt_style_version == cls.PROMPT_STYLE_VERSION
        return {
            "prompt_style_version": prompt_style_version,
            "expected_prompt_style_version": cls.PROMPT_STYLE_VERSION,
            "prompt_style_version_current": prompt_style_version_current,
            "identity_semicolons": identity_body.count(";"),
            "scene_banned_phrases": scene_banned_phrases,
            "outfit_scene_props": outfit_scene_props,
            "mood_label_like": mood_label_like,
            "legacy_signatures": legacy_signatures,
            "has_legacy_content": bool(legacy_signatures),
        }

    @staticmethod
    def _stable_variation_index(*parts: Any, modulo: int) -> int:
        if modulo <= 0:
            return 0
        seed = "||".join(str(part or "") for part in parts)
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
        return int(digest[:12], 16) % modulo

    def _stable_choice(self, options: List[str], *parts: Any) -> str:
        cleaned = [self._clean_fragment(option) for option in options if self._clean_fragment(option)]
        if not cleaned:
            return ""
        return cleaned[self._stable_variation_index(*parts, modulo=len(cleaned))]

    def _imperfect_reality_layer(
        self,
        *,
        context: Dict[str, Any],
        scene: Any,
        outfit_bundle: OutfitBundle,
        shot_archetype: str,
        platform_behavior: str,
        outfit_sentence: str,
    ) -> Dict[str, Any]:
        object_terms = self._behavior_object_terms(context, scene)
        scene_text = self._scene_text(scene).lower()
        behavior = context.get("behavioral_context")
        energy = str(getattr(behavior, "energy_level", "medium") or "medium").lower() if behavior is not None else "medium"
        signature_parts = [
            scene_text,
            outfit_sentence,
            shot_archetype,
            platform_behavior,
            ",".join(object_terms),
            energy,
            getattr(scene, "moment_signature", ""),
            getattr(outfit_bundle, "outfit_style", ""),
        ]

        scene_micro_pool = [
            "head angle a fraction off level as if the moment was caught mid-adjustment",
            "weight still settling onto one side instead of locking into a centered stance",
            "one forearm resting a little farther forward than the other",
            "torso turned a few degrees like the movement has not fully stopped yet",
        ]
        outfit_micro_pool = [
            "one side sitting a touch higher from recent movement",
            "fabric folding slightly off where a perfect styling pass would leave it",
            "hem and layers settling a little unevenly in motion",
            "strap or sleeve pulling the fabric a fraction off center",
        ]
        interaction_pool = [
            "fingers not closing with showroom precision",
            "grip staying natural with a small uneven pressure through the hand",
            "wrist angle landing a little loose instead of perfectly squared",
        ]
        mood_pool = [
            "attention landing somewhere just past the camera",
            "already a beat into the moment rather than presenting for it",
            "caught mid-thought with a little room left unsaid",
        ]

        if shot_archetype in {"front_selfie", "mirror_selfie"}:
            scene_micro_pool.extend(
                [
                    "phone-side shoulder staying a touch higher than the other side",
                    "chin tipped slightly instead of landing on a perfectly level line",
                ]
            )
        if shot_archetype == "seated_table_shot" or any(token in scene_text for token in ["seated", "sitting", "table", "chair"]):
            scene_micro_pool.extend(
                [
                    "back settling a little away from the chair line",
                    "one elbow sitting slightly farther out than the other",
                ]
            )
            interaction_pool.append("object placement staying a little off the neat center of the table")
        if "coffee cup" in object_terms:
            scene_micro_pool.extend(
                [
                    "cup tipped a fraction in her hand instead of sitting completely upright",
                    "cup angle reading a little lived-in rather than carefully presented",
                ]
            )
            interaction_pool.extend(
                [
                    "finger tension easing and tightening around the cup instead of fixing into one clean grip",
                    "cup hold staying slightly uneven in a natural way",
                ]
            )
        if "carry on" in object_terms:
            scene_micro_pool.extend(
                [
                    "handle angle sitting slightly off straight as the wrist relaxes",
                    "carry on line staying a touch imperfect beside her stride",
                ]
            )
            interaction_pool.extend(
                [
                    "handle grip landing a little loose instead of perfectly centered in the palm",
                    "bag and handle weight pulling one side a fraction higher",
                ]
            )
        if "bag" in object_terms:
            outfit_micro_pool.extend(
                [
                    "bag weight shifting the line of the layer slightly on one side",
                    "strap tension leaving a small off-center pull in the fabric",
                ]
            )
        if any(token in scene_text for token in ["hotel", "home", "kitchen", "living room"]):
            mood_pool.append("the frame feeling lightly interrupted rather than fully arranged")
        if platform_behavior == "story_lifestyle":
            mood_pool.append("a little less resolved, like the camera arrived in the middle of it")

        interaction_anchor = self._presence_interaction_cue(outfit_bundle, object_terms, shot_archetype)
        if "coffee cup" in object_terms:
            interaction_anchor = "coffee cup held with a relaxed uneven grip and light finger pressure"
        elif "carry on" in object_terms:
            interaction_anchor = "carry on handle held without perfect alignment"
        elif "bag" in object_terms:
            interaction_anchor = "bag strap sitting naturally so the clothing shifts slightly under it"

        return {
            "scene_micro": self._stable_choice(scene_micro_pool, *signature_parts, "scene_micro"),
            "outfit_micro": self._stable_choice(outfit_micro_pool, *signature_parts, "outfit_micro"),
            "asymmetry_anchor": self._presence_asymmetry_cue(object_terms, shot_archetype),
            "interaction_anchor": interaction_anchor,
            "interaction_micro": self._stable_choice(interaction_pool, *signature_parts, "interaction_micro"),
            "mood_micro": self._stable_choice(mood_pool, *signature_parts, "mood_micro"),
        }

    def _apply_imperfect_reality_layer(
        self,
        block_map: Dict[str, str],
        *,
        scene: Any,
        context: Dict[str, Any],
        shot_archetype: str,
        imperfect_layer: Dict[str, Any],
    ) -> Dict[str, str]:
        softened = dict(block_map)
        diagnostics = self._detect_perfection_patterns(softened)

        scene_body = self._split_block_label(softened["Scene"])[1].replace("small detail: ", "")
        outfit_body = self._split_block_label(softened["Outfit"])[1]
        mood_body = self._split_block_label(softened["Mood"])[1]
        original_mood_body = mood_body

        if diagnostics["needs_softening"]:
            scene_body = self._soften_scene_body(scene_body, context)
            mood_body = self._soften_mood_body(mood_body)

        scene_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_body)]
        protected_scene_extras: List[str] = []
        for extra in [
            imperfect_layer.get("asymmetry_anchor", ""),
            imperfect_layer.get("interaction_anchor", ""),
            imperfect_layer.get("scene_micro", ""),
            imperfect_layer.get("interaction_micro", ""),
        ]:
            cleaned = self._clean_fragment(str(extra or ""))
            if cleaned and cleaned.lower() not in scene_body.lower():
                scene_clauses.append(cleaned)
                protected_scene_extras.append(cleaned)
        if diagnostics["needs_softening"]:
            scene_clauses = self._prioritized_scene_clauses(scene_clauses, context, limit=9)
            scene_clauses = self._ensure_scene_extras(scene_clauses, protected_scene_extras, context, limit=9)
        scene_body = ", ".join(self._dedupe_semantic_phrases(scene_clauses))

        outfit_body = self._soften_outfit_body(
            outfit_body,
            scene=scene,
            context=context,
            shot_archetype=shot_archetype,
            imperfect_layer=imperfect_layer,
            allow_drop=diagnostics["needs_softening"],
        )

        mood_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Mood", mood_body)]
        mood_micro = self._clean_fragment(str(imperfect_layer.get("mood_micro") or ""))
        if "in-the-moment presence" in original_mood_body.lower() and not any(
            clause.lower() == "in-the-moment presence" for clause in mood_clauses
        ):
            mood_clauses.append("in-the-moment presence")
        if mood_micro and mood_micro.lower() not in mood_body.lower():
            mood_clauses.append(mood_micro)
        if diagnostics["needs_softening"]:
            base_mood = mood_clauses[:1]
            priority: List[str] = []
            for clause in mood_clauses:
                lowered = clause.lower()
                if lowered in {"in-the-moment presence", "transitional mood"} or "in-the-moment presence" in lowered:
                    priority.append(clause)
            mood_clauses = self._dedupe_phrases(base_mood + priority + mood_clauses[1:3] + ([mood_micro] if mood_micro else []))
        mood_body = ", ".join(self._dedupe_phrases(mood_clauses))

        softened["Scene"] = f"Scene: {scene_body}."
        softened["Outfit"] = f"Outfit: {outfit_body}."
        softened["Mood"] = f"Mood: {mood_body}."
        return softened

    def rewrite_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        shot_archetype: str = "",
    ) -> Dict[str, Any]:
        raw_blocks = [block.strip() for block in str(prompt or "").split("\n\n") if block.strip()]
        if len(raw_blocks) != 6:
            return {
                "prompt": str(prompt or "").strip(),
                "prompt_blocks": {},
                "rewrite_pass_applied": False,
                "rewrite_diagnostics": {},
            }

        block_names = ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        block_map = {name: raw_blocks[idx] for idx, name in enumerate(block_names)}
        resolved_shot = shot_archetype or self._resolve_shot_archetype(scene, context, context.get("recent_moment_memory") or [])
        rewritten_blocks = self._apply_in_the_moment_phrasing_layer(
            block_map,
            scene=scene,
            context=context,
            shot_archetype=resolved_shot,
        )
        rewritten_prompt = "\n\n".join(rewritten_blocks[name] for name in block_names)
        return {
            "prompt": rewritten_prompt,
            "prompt_blocks": rewritten_blocks,
            "rewrite_pass_applied": True,
            "rewrite_diagnostics": self._rewrite_pass_diagnostics(rewritten_blocks),
        }

    def _apply_in_the_moment_phrasing_layer(
        self,
        block_map: Dict[str, str],
        *,
        scene: Any,
        context: Dict[str, Any],
        shot_archetype: str,
    ) -> Dict[str, str]:
        transformed = dict(block_map)

        identity_body = self._split_block_label(transformed["Identity"])[1]
        scene_body = self._split_block_label(transformed["Scene"])[1]
        outfit_body = self._split_block_label(transformed["Outfit"])[1]
        environment_body = self._split_block_label(transformed["Environment"])[1]
        mood_body = self._split_block_label(transformed["Mood"])[1]

        transformed["Identity"] = f"Identity: {self._in_the_moment_identity_body(identity_body)}."
        transformed["Scene"] = f"Scene: {self._in_the_moment_scene_body(scene_body, scene)}."
        transformed["Environment"] = f"Environment: {self._in_the_moment_environment_body(environment_body)}."
        transformed["Mood"] = f"Mood: {self._in_the_moment_mood_body(mood_body)}."

        in_the_moment_outfit = self._in_the_moment_outfit_body(
            outfit_body,
            scene=scene,
            context=context,
            shot_archetype=shot_archetype,
        )
        try:
            transformed["Outfit"] = f"Outfit: {self.validate_outfit_sentence(in_the_moment_outfit)}."
        except PromptValidationError:
            transformed["Outfit"] = f"Outfit: {self._normalize_outfit_sentence_for_prompt(outfit_body, scene, context)}."

        required_scene_objects = self._dedupe_phrases(
            self._behavior_object_terms(context, scene) + self._extract_scene_props_from_outfit_text(scene_body)
        )
        scene_rewritten_body = self._split_block_label(transformed["Scene"])[1]
        missing_scene_phrases = [
            self._object_scene_phrase(object_term, scene, context=context)
            for object_term in required_scene_objects
            if object_term and object_term.lower() not in scene_rewritten_body.lower()
        ]
        missing_scene_phrases = [phrase for phrase in missing_scene_phrases if phrase]
        if missing_scene_phrases:
            scene_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_rewritten_body)]
            scene_rewritten_body = ", ".join(
                self._dedupe_semantic_phrases(scene_clauses + missing_scene_phrases)
            )
            transformed["Scene"] = f"Scene: {scene_rewritten_body}."

        diagnostics = self._rewrite_pass_diagnostics(transformed)
        if diagnostics.get("scene_banned_phrases"):
            transformed["Scene"] = f"Scene: {self._scene_presence_lead(scene, scene_body)}."
        if diagnostics.get("mood_banned_phrases") or diagnostics.get("mood_label_like"):
            transformed["Mood"] = f"Mood: {self._fallback_mood_presence_phrase(scene, context)}."
        if diagnostics.get("outfit_scene_props"):
            cleaned_outfit = self._normalize_outfit_sentence_for_prompt(outfit_body, scene, context)
            transformed["Outfit"] = f"Outfit: {self._in_the_moment_outfit_body(cleaned_outfit, scene=scene, context=context, shot_archetype=shot_archetype)}."
        if diagnostics.get("identity_semicolons"):
            transformed["Identity"] = f"Identity: {self._in_the_moment_identity_body(identity_body)}."
        return transformed

    def _rewrite_pass_diagnostics(self, block_map: Dict[str, str]) -> Dict[str, Any]:
        identity_body = self._split_block_label(block_map.get("Identity", ""))[1]
        scene_body = self._split_block_label(block_map.get("Scene", ""))[1].lower()
        outfit_body = self._split_block_label(block_map.get("Outfit", ""))[1].lower()
        environment_body = self._split_block_label(block_map.get("Environment", ""))[1].lower()
        mood_body = self._split_block_label(block_map.get("Mood", ""))[1].lower()
        prompt_text = "\n\n".join(block_map.get(name, "") for name in ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"])
        scene_banned = [phrase for phrase in self.REWRITE_FORBIDDEN_SCENE_PHRASES if phrase in scene_body]
        mood_banned = [phrase for phrase in self.REWRITE_FORBIDDEN_MOOD_PHRASES if phrase in mood_body]
        outfit_scene_props = [prop for prop in self._extract_scene_props_from_outfit_text(outfit_body) if prop]
        return {
            "identity_semicolons": identity_body.count(";"),
            "scene_banned_phrases": scene_banned,
            "mood_banned_phrases": mood_banned,
            "mood_label_like": " self-presentation" in mood_body or mood_body.endswith(" mood"),
            "outfit_scene_props": outfit_scene_props,
            "environment_semicolons": environment_body.count(";"),
            "total_semicolons": prompt_text.count(";"),
            "passed": (
                not scene_banned
                and not mood_banned
                and not outfit_scene_props
                and identity_body.count(";") == 0
                and prompt_text.count(";") <= 2
            ),
        }

    def _in_the_moment_identity_body(self, identity_body: str) -> str:
        if ";" not in identity_body and re.search(r"\ba\s+\d{2}(?:-year-old)?\s+woman\b", identity_body.lower()):
            return self._repair_duplicate_sequences_in_text(identity_body, aggressive=True)
        clauses = [self._clean_fragment(chunk) for chunk in re.split(r"\s*;\s*", identity_body) if self._clean_fragment(chunk)]
        if not clauses or all(clause.lower() in {"stable", "same", "recognizable"} or len(clause.split()) <= 2 for clause in clauses):
            return "a 22-year-old woman with a recognizable face, relaxed shoulders, and an easy upright posture"
        age = next((clause for clause in clauses if re.search(r"\b\d{2}(?:-year-old)?\b", clause)), "22-year-old")
        if age.isdigit():
            age = f"{age}-year-old"
        face_bits = [
            clause
            for clause in clauses
            if clause != age and clause.lower() != "woman" and not any(token in clause.lower() for token in ["hair", "makeup", "build", "height", "shoulders", "posture"])
        ]
        body_bits = [
            clause
            for clause in clauses
            if any(token in clause.lower() for token in ["hair", "makeup", "build", "height", "shoulders", "posture"])
        ]
        primary_face = self._human_join(face_bits[:6])
        secondary = self._human_join(body_bits[:4])
        lead = f"a {age} woman"
        if primary_face:
            lead = f"{lead} with {primary_face}"
        if secondary:
            lead = f"{lead}, {secondary}"
        return self._clean_fragment(lead)

    def _detect_perfection_patterns(self, block_map: Dict[str, str]) -> Dict[str, bool]:
        scene_body = self._split_block_label(block_map.get("Scene", ""))[1]
        outfit_body = self._split_block_label(block_map.get("Outfit", ""))[1]
        mood_body = self._split_block_label(block_map.get("Mood", ""))[1]
        scene_count = len(self._extract_semantic_clauses("Scene", scene_body))
        outfit_count = len(self._extract_semantic_clauses("Outfit", outfit_body))
        mood_count = len(self._extract_semantic_clauses("Mood", mood_body))
        counts = [count for count in [scene_count, outfit_count, mood_count] if count]

        too_symmetrical = bool(counts) and min(counts) >= 4 and (max(counts) - min(counts) <= 1)
        too_complete = scene_count >= 7 or outfit_count >= 6 or sum(counts) >= 14
        lowered = " ".join([scene_body.lower(), outfit_body.lower(), mood_body.lower()])
        too_clean = any(
            token in lowered
            for token in ["small detail:", "carefully arranged", "perfectly aligned", "fully styled", "precisely placed"]
        )
        return {
            "too_symmetrical": too_symmetrical,
            "too_complete": too_complete,
            "too_clean": too_clean,
            "needs_softening": too_symmetrical or too_complete or too_clean,
        }

    def _in_the_moment_scene_body(self, scene_body: str, scene: Any) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_body)]
        lead = self._scene_presence_lead(scene, scene_body)
        rewritten_raw: List[str] = []
        if lead:
            rewritten_raw.append(lead)
        for clause in clauses:
            rewritten_clause = self._rewrite_scene_clause_for_presence(clause, scene)
            if rewritten_clause:
                rewritten_raw.append(rewritten_clause)
        rewritten = self._dedupe_semantic_phrases(rewritten_raw)
        joined = " ".join(rewritten).lower()
        if len(rewritten) >= 4:
            tail = self._stable_choice(
                [
                    "the rest of it still carrying on outside the frame",
                    "like the camera cut in a second late",
                    "nothing in it trying too hard",
                ],
                scene_body,
                self._scene_text(scene),
                getattr(scene, "moment_signature", ""),
                "scene_tail",
            )
            if tail and tail.lower() not in joined:
                rewritten.append(tail)
        return ", ".join(rewritten[:6]) if rewritten else self._minimal_scene_body(scene)

    def _scene_presence_lead(self, scene: Any, scene_body: str) -> str:
        source = self._clean_fragment(
            str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or scene_body)
        )
        cleaned = self._grounded_phrase(source)
        replacements = [
            (
                r"\bslow first coffee in the kitchen corner before the day starts\b",
                "first coffee in the kitchen corner, the light still low, nothing rushed yet",
            ),
            (r"\bbefore the day starts\b", "the light still low, nothing rushed yet"),
            (r"\bduring the morning routine\b", "the routine already in motion"),
            (r"\bdaily pause\b", "a pause already underway"),
            (r"\bnatural pause moment\b", "a pause already underway"),
            (r"\bbefore heading out\b", "the door still a later problem"),
            (r"\bbefore boarding\b", "boarding still ahead"),
            (r"\bbefore breakfast\b", "before anything feels fully started"),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*,\s*at [a-z ]+$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
        return self._decapitalize_fragment(cleaned)

    def _rewrite_scene_clause_for_presence(self, clause: str, scene: Any) -> str:
        cleaned = self._grounded_phrase(clause)
        if not cleaned:
            return ""

        activity = str(getattr(scene, "activity", "") or "").replace("_", " ").strip().lower()
        if activity and cleaned.lower() == activity:
            return ""

        replacements = [
            (r"\bbefore the day starts\b", "the light still low, nothing rushed yet"),
            (r"\bduring the morning routine\b", "the routine already in motion"),
            (r"\bin a calm moment\b", "with the quiet still hanging there"),
            (r"\bbefore heading out\b", "with the door still a later problem"),
            (r"\bbefore boarding\b", "with boarding still ahead"),
            (r"\bbefore breakfast\b", "before anything feels fully started"),
            (r"\bholding cup naturally\b", "coffee cup in hand"),
            (r"\bresting hands naturally\b", "hands left alone"),
            (r"\btouching the window lightly\b", "fingers near the window"),
            (r"\bminimal facial expression with inward attention\b", "more inward than expressive"),
            (r"\bmeasured expression and upright posture\b", "held together without looking posed"),
            (r"\bgentle expression and relaxed shoulders\b", "relaxed shoulders and an expression left soft"),
            (r"\bnatural pause moment\b", "a pause already underway"),
            (r"\bstill posture\b", "a pause already underway"),
            (r"\bslow relaxed movement\b", "movement just slow enough to still be in it"),
            (r"\bsmall detail:\s*", ""),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        if cleaned.lower().startswith("at "):
            cleaned = f"in {cleaned[3:]}"
        if cleaned.lower().startswith("with coffee cup in hand"):
            cleaned = cleaned[5:]

        if cleaned.lower().startswith("with the quiet still hanging there"):
            cleaned = cleaned.replace("with the quiet still hanging there", "quiet still hanging there", 1)
        cleaned = re.sub(r"\b(daily pause|natural pause moment)\b", "a pause already underway", cleaned, flags=re.IGNORECASE)
        return self._decapitalize_fragment(cleaned)

    def _smooth_scene_clause(self, clause: str) -> str:
        cleaned = self._repair_duplicate_sequences_in_text(self._grounded_phrase(clause), aggressive=True)
        if not cleaned:
            return ""
        cleaned = re.sub(
            r"^(?:calm|quiet|soft|slow)\s+(waiting|walking|standing|sitting)\b",
            r"\1",
            cleaned,
            flags=re.IGNORECASE,
        )
        if "boarding still ahead" in cleaned.lower() and ", boarding still ahead" not in cleaned.lower() and "with boarding still ahead" not in cleaned.lower():
            cleaned = re.sub(r"\s+boarding still ahead\b", ", boarding still ahead", cleaned, flags=re.IGNORECASE, count=1)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return self._clean_fragment(cleaned)

    def _scene_quality_ok(self, scene_body: str) -> bool:
        lowered = self._clean_fragment(scene_body).lower()
        if len(lowered.split()) < 5:
            return False
        if re.match(r"^(?:calm|quiet|soft|slow)\s+(waiting|walking|standing|sitting)\b", lowered):
            return False
        if "boarding still ahead" in lowered and ", boarding still ahead" not in lowered and "with boarding still ahead" not in lowered:
            return False
        return True

    def _quality_recover_scene_body(self, scene_body: str, scene: Any, context: Dict[str, Any]) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_body)]
        if not clauses:
            clauses = [self._scene_presence_lead(scene, scene_body) or self._minimal_scene_body(scene)]
        smoothed = [self._smooth_scene_clause(clause) for clause in clauses]
        smoothed = [clause for clause in smoothed if clause]

        required_objects = self._behavior_object_terms(context, scene)
        for object_term in required_objects:
            phrase = self._object_scene_phrase(object_term, scene, context=context)
            if phrase and phrase.lower() not in " ".join(smoothed).lower():
                smoothed.append(self._smooth_scene_clause(phrase))

        lowered_scene = self._scene_text(scene).lower()
        if (
            any(token in lowered_scene for token in ["waiting", "pause", "coffee", "gate"])
            and not any("pause already underway" in clause.lower() or "still for a second, not frozen" in clause.lower() for clause in smoothed)
        ):
            smoothed.append("a pause already underway")

        recovered = self._dedupe_semantic_phrases(smoothed)
        if not recovered:
            recovered = [self._smooth_scene_clause(self._scene_presence_lead(scene, scene_body) or self._minimal_scene_body(scene))]
        return ", ".join([clause for clause in recovered if clause][:6])

    def _environment_quality_ok(self, environment_body: str) -> bool:
        clauses = self._extract_semantic_clauses("Environment", environment_body)
        lowered = self._clean_fragment(environment_body).lower()
        return len(clauses) >= 3 and "photorealistic" in lowered and "perspective" in lowered and "light" in lowered

    def _mood_quality_ok(self, mood_body: str) -> bool:
        lowered = self._clean_fragment(mood_body).lower()
        if len(lowered.split()) < 6:
            return False
        return not lowered.endswith(" mood") and "self-presentation" not in lowered

    def _prompt_quality_floor_diagnostics(self, prompt: str, scene: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        block_map = self._prompt_block_map(prompt)
        if not block_map:
            return {
                "passed": False,
                "failed_checks": ["block_structure"],
                "identity_cue_count": 0,
                "outfit_grammar_ok": False,
                "scene_natural": False,
                "environment_rich": False,
                "mood_rich": False,
            }

        identity_body = self._split_block_label(block_map["Identity"])[1]
        scene_body = self._split_block_label(block_map["Scene"])[1]
        outfit_body = self._split_block_label(block_map["Outfit"])[1]
        environment_body = self._split_block_label(block_map["Environment"])[1]
        mood_body = self._split_block_label(block_map["Mood"])[1]

        identity_cue_count = self._identity_floor_cue_count(identity_body)
        outfit_grammar_ok = True
        try:
            self.validate_outfit_sentence(outfit_body)
        except PromptValidationError:
            outfit_grammar_ok = False
        if self._has_invalid_plural_article(outfit_body):
            outfit_grammar_ok = False
        clothing, _, _ = self._split_outfit_scene_props(outfit_body)
        normalized_clothing = self._normalize_outfit_clothing_items(clothing)
        if len(normalized_clothing) != len(self._dedupe_phrases(clothing)):
            outfit_grammar_ok = False

        scene_natural = self._scene_quality_ok(scene_body)
        environment_rich = self._environment_quality_ok(environment_body)
        mood_rich = self._mood_quality_ok(mood_body)

        failed_checks: List[str] = []
        if identity_cue_count < self.IDENTITY_FLOOR_MIN_CUES:
            failed_checks.append("identity_floor")
        if not outfit_grammar_ok:
            failed_checks.append("outfit_grammar")
        if not scene_natural:
            failed_checks.append("scene_naturalness")
        if not environment_rich:
            failed_checks.append("environment_floor")
        if not mood_rich:
            failed_checks.append("mood_floor")
        return {
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "identity_cue_count": identity_cue_count,
            "outfit_grammar_ok": outfit_grammar_ok,
            "scene_natural": scene_natural,
            "environment_rich": environment_rich,
            "mood_rich": mood_rich,
        }

    def _recover_canonical_prompt_quality(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        shot_archetype: str = "",
    ) -> Dict[str, Any]:
        block_map = self._prompt_block_map(prompt)
        if not block_map:
            return {
                "prompt": str(prompt or "").strip(),
                "prompt_blocks": {},
                "quality_recovery_applied": False,
                "quality_diagnostics": self._prompt_quality_floor_diagnostics(prompt, scene, context),
            }

        diagnostics = self._prompt_quality_floor_diagnostics(prompt, scene, context)
        updated = dict(block_map)
        changed = False
        outfit_recovered = False

        if diagnostics["identity_cue_count"] < self.IDENTITY_FLOOR_MIN_CUES:
            identity_body = self._split_block_label(updated["Identity"])[1]
            recovered_identity = self._recover_identity_body(identity_body, context, force_floor=True)
            updated["Identity"] = f"Identity: {recovered_identity}."
            changed = True

        current_outfit = self._split_block_label(updated["Outfit"])[1] or self._clean_fragment(outfit_sentence)
        recovered_outfit = self._normalize_outfit_sentence_for_prompt(current_outfit, scene, context)
        if recovered_outfit != self._clean_fragment(current_outfit):
            changed = True
            outfit_recovered = True
        updated["Outfit"] = f"Outfit: {recovered_outfit}."

        scene_body = self._split_block_label(updated["Scene"])[1]
        if not diagnostics["scene_natural"]:
            recovered_scene = self._quality_recover_scene_body(scene_body, scene, context)
            updated["Scene"] = f"Scene: {recovered_scene}."
            changed = True

        if not diagnostics["environment_rich"]:
            coherence = self._resolve_place_coherence(context, scene, environment_body=self._split_block_label(updated["Environment"])[1])
            recovered_environment = self._in_the_moment_environment_body(self._coherent_environment_seed(scene, context, coherence))
            updated["Environment"] = f"Environment: {recovered_environment}."
            changed = True

        if not diagnostics["mood_rich"]:
            updated["Mood"] = f"Mood: {self._fallback_mood_presence_phrase(scene, context)}."
            changed = True

        recovered_prompt = "\n\n".join(
            updated[name]
            for name in ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        )
        return {
            "prompt": recovered_prompt,
            "prompt_blocks": updated,
            "quality_recovery_applied": changed,
            "outfit_recovered": outfit_recovered,
            "quality_diagnostics": self._prompt_quality_floor_diagnostics(recovered_prompt, scene, context),
        }

    def _in_the_moment_environment_body(self, environment_body: str) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Environment", environment_body)]
        rewritten: List[str] = []
        for clause in clauses:
            cleaned = self._grounded_phrase(clause)
            lowered = cleaned.lower()
            if lowered.startswith("physically plausible spatial depth"):
                cleaned = "real spatial depth"
            elif lowered == "accurate perspective and scale":
                cleaned = "perspective and scale staying real"
            elif "behaving as natural available light" in lowered:
                cleaned = re.sub(r"\s*behaving as natural available light", " working like available light", cleaned, flags=re.IGNORECASE)
            elif lowered == "lived-in environmental detail":
                cleaned = "lived-in detail"
            rewritten.append(cleaned)
        return ", ".join(self._dedupe_phrases(rewritten)) if rewritten else self._grounded_phrase(environment_body)

    def _in_the_moment_mood_body(self, mood_body: str) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Mood", mood_body)]
        rewritten_raw: List[str] = []
        for clause in clauses:
            rewritten_clause = self._rewrite_mood_clause_for_presence(clause)
            if rewritten_clause:
                rewritten_raw.append(rewritten_clause)
        rewritten = self._dedupe_phrases(rewritten_raw)
        if not any("already happening by the time the camera catches it" in clause.lower() for clause in rewritten):
            rewritten.append("already happening by the time the camera catches it")
        return ", ".join(rewritten[:3]) if rewritten else "already happening by the time the camera catches it"

    def _rewrite_mood_clause_for_presence(self, clause: str) -> str:
        cleaned = self._grounded_phrase(clause)
        lowered = cleaned.lower()

        exact = {
            "grounded routine mood": "the rhythm staying ordinary and unforced",
            "transitional mood": "like she is between one thing and the next",
            "calm arrival mood": "just settled into the place",
            "focused before-leaving mood": "already half ready to move again",
            "in-the-moment presence": "already happening by the time the camera catches it",
            "unposed asymmetry kept in the frame": "small imbalance left in the frame",
            "soft observational restraint": "more observant than expressive",
            "quiet confidence": "held together without turning it into a pose",
            "composed focus": "focused without tightening up for the frame",
            "calm ease": "calm in a way that reads lived-in",
            "quiet curiosity": "curious without playing it outward",
        }
        if lowered in exact:
            return exact[lowered]
        if lowered.endswith(" self-presentation"):
            token = lowered.replace(" self-presentation", "").strip()
            return {
                "transitional": "still a little between places",
                "soft": "easy in the face and shoulders",
                "focused": "more inward than performative",
                "composed": "held together without putting it on",
                "relaxed": "easy in the body",
            }.get(token, "")
        if "relaxed body language" in lowered and "lived-in" in lowered:
            return "relaxed body language, lived-in and not tidied up for the frame"
        if "quietly intimate body language" in lowered:
            return "quietly intimate body language, a little more open through the posture"
        if "quietly confident body language" in lowered:
            return "quiet confidence without the posed part"
        if "natural body language with no posed look" in lowered:
            return "natural body language with nothing performed for the camera"
        if lowered.endswith(" mood"):
            return ""
        return cleaned

    def _fallback_mood_presence_phrase(self, scene: Any, context: Dict[str, Any]) -> str:
        behavior = context.get("behavioral_context")
        self_presentation = str(getattr(behavior, "self_presentation", "") or "").lower() if behavior is not None else ""
        outfit_override = str(context.get("outfit_override", "") or "").lower()
        if outfit_override == "slightly_sexy":
            return "quietly intimate body language, a little more open through the posture"
        if self_presentation == "transitional":
            return "like she is between one thing and the next, already happening by the time the camera catches it"
        if "focused" in str(getattr(scene, "mood", "") or "").lower() or self_presentation == "focused":
            return "focused without tightening up for the frame, already happening by the time the camera catches it"
        return "held together without turning it into a pose, already happening by the time the camera catches it"

    def _in_the_moment_outfit_body(
        self,
        outfit_body: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        shot_archetype: str,
    ) -> str:
        clothing, details, _ = self._split_outfit_scene_props(outfit_body)
        promoted_details: List[str] = []
        retained_clothing: List[str] = []
        for chunk in clothing:
            if self._is_outfit_detail_only_clause(chunk):
                promoted_details.append(chunk)
            else:
                retained_clothing.append(chunk)
        clothing = self._dedupe_phrases(retained_clothing)
        details = self._dedupe_phrases(details + promoted_details)

        if shot_archetype not in {"front_selfie", "mirror_selfie"} and len(clothing) > 4:
            clothing = self._drop_nonessential_outfit_item(clothing, context, scene)

        phrase_candidates: List[str] = []
        for item in clothing:
            rewritten_item = self._rewrite_outfit_item_for_presence(item)
            if rewritten_item:
                phrase_candidates.append(rewritten_item)
        phrases = self._dedupe_phrases(phrase_candidates)
        detail_phrase = self._grounded_outfit_detail_phrase(details)
        if detail_phrase and detail_phrase.lower() not in " ".join(phrases).lower():
            phrases.append(detail_phrase)
        rebuilt = ", ".join(phrases[:5])
        return rebuilt or self._normalize_outfit_sentence_for_prompt(outfit_body, scene, context)

    def _rewrite_outfit_item_for_presence(self, item: str) -> str:
        cleaned = self._grounded_phrase(item)
        lowered = cleaned.lower()
        if self._is_scene_prop_phrase(cleaned):
            return ""
        clothing_tokens = (
            "dress",
            "jeans",
            "trousers",
            "pants",
            "skirt",
            "shorts",
            "denim",
            "sneakers",
            "boots",
            "loafers",
            "sandals",
            "slides",
            "shoes",
            "trainers",
            "coat",
            "jacket",
            "cardigan",
            "blazer",
            "hoodie",
            "trench",
            "top",
            "blouse",
            "shirt",
            "sweater",
            "knit",
            "knitwear",
            "tank",
            "tee",
            "bag",
        )
        if len(lowered.split()) <= 3 and not any(token in lowered for token in clothing_tokens):
            return ""
        category = self._outfit_category(cleaned)

        if category == "dress":
            if "knit" in lowered:
                return f"{cleaned} with an easy line through the body"
            return f"{cleaned} worn like the day is already underway"
        if category == "bottom":
            if "trousers" in lowered or "pants" in lowered:
                if "straight" in lowered:
                    return f"{cleaned} with an easy line through the leg"
                return f"{cleaned} with easy movement through the leg"
            if "jeans" in lowered or "denim" in lowered:
                return f"{cleaned} with light natural wear"
            return f"{cleaned} moving easy with her"
        if category == "shoes":
            if any(token in lowered for token in ["sneakers", "trainers"]):
                return f"{cleaned} worn in"
            if any(token in lowered for token in ["slides", "sandals"]):
                return f"{cleaned} that look actually used"
            return f"{cleaned} kept easy and grounded"
        if category == "outerwear":
            if "cardigan" in lowered:
                return f"{cleaned} left open and shifting a little"
            return f"{cleaned} falling into its own lines"
        if category == "accessory":
            if "overnight bag" in lowered:
                return ""
            if "carry on" in lowered or "carry-on" in lowered:
                return ""
            if "bag" in lowered:
                return f"{cleaned} worn crossbody with the strap cutting diagonally through the frame"
            return f"{cleaned} looking actually carried"
        if "knitwear" in lowered:
            return f"{cleaned} with a few real folds"
        if "knit" in lowered:
            return f"{cleaned} that sits naturally"
        return f"{cleaned} worn without looking overthought"

    def _grounded_outfit_detail_phrase(self, details: List[str]) -> str:
        for detail in reversed(details):
            cleaned = self._grounded_phrase(detail)
            lowered = cleaned.lower()
            if len(lowered.split()) <= 1:
                continue
            if "not perfectly arranged" in lowered or "not too arranged" in lowered or "shifted" in lowered:
                return "one side sitting a little off from recent movement"
            if any(token in lowered for token in ["drape", "soft body lines", "relaxed fit"]):
                return "easy movement through the fit"
            if any(token in lowered for token in ["fold", "wrinkle", "crease", "texture"]):
                return "light natural wear in the fabric"
            if any(token in lowered for token in ["pull", "off center", "uneven", "higher"]):
                return cleaned
        return ""

    @staticmethod
    def _decapitalize_fragment(text: str) -> str:
        cleaned = PromptComposer._clean_fragment(text)
        if len(cleaned) < 2:
            return cleaned.lower()
        if cleaned[0].isupper() and cleaned[1].islower():
            return cleaned[0].lower() + cleaned[1:]
        return cleaned

    @staticmethod
    def _grounded_phrase(text: str) -> str:
        cleaned = PromptComposer._clean_fragment(text)
        replacements = [
            ("slightly", "a little"),
            ("rather than", "not"),
            ("feels lived-in", "lands lived-in"),
            ("without perfect alignment", "without lining up too neatly"),
            ("not perfectly arranged", "not too arranged"),
            ("perfectly aligned", "too aligned"),
            ("perfectly squared", "too squared"),
        ]
        for old, new in replacements:
            cleaned = re.sub(re.escape(old), new, cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bsoft observational restraint\b", "more observant than expressive", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned.strip(" ,;:.")

    def _prioritized_scene_clauses(self, clauses: List[str], context: Dict[str, Any], limit: int) -> List[str]:
        required_objects = self._behavior_object_terms(context)
        cleaned = self._dedupe_phrases(clauses)
        if len(cleaned) <= limit:
            return cleaned
        kept: List[str] = []
        deferred: List[str] = []
        for idx, clause in enumerate(cleaned):
            lowered = clause.lower()
            is_required = idx == 0 or any(obj in lowered for obj in required_objects)
            if "bag" in required_objects and "travel items nearby" in lowered:
                is_required = True
            if "pause already underway" in lowered or "still for a second" in lowered:
                is_required = True
            is_micro = any(
                token in lowered
                for token in ["slight", "slightly", "fraction", "uneven", "loose", "mid-thought", "finger tension", "grip", "wrist"]
            )
            is_behavioral = any(
                token in lowered
                for token in [
                    "posture",
                    "pause",
                    "holding",
                    "walking",
                    "handling",
                    "measured steps",
                    "movement",
                    "thoughtful pause",
                    "boarding screen",
                    "uneven grip",
                    "finger pressure",
                    "sleeve brushing",
                ]
            )
            if is_required or is_micro or is_behavioral:
                kept.append(clause)
            else:
                deferred.append(clause)
        return self._dedupe_phrases(kept + deferred)[:limit]

    def _soften_scene_body(self, scene_body: str, context: Dict[str, Any]) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_body)]
        return ", ".join(self._prioritized_scene_clauses(clauses, context, limit=8))

    def _ensure_scene_extras(self, clauses: List[str], extras: List[str], context: Dict[str, Any], limit: int) -> List[str]:
        selected = self._dedupe_phrases(clauses)
        required_objects = self._behavior_object_terms(context)
        for extra in self._dedupe_phrases(extras):
            if extra in selected:
                continue
            while len(selected) >= limit:
                removable_index = next(
                    (
                        idx
                        for idx, clause in enumerate(selected[::-1])
                        if idx >= 0
                        and not any(obj in clause.lower() for obj in required_objects)
                        and "boarding screen" not in clause.lower()
                        and "holding " not in clause.lower()
                        and "posture" not in clause.lower()
                        and clause != selected[0]
                    ),
                    None,
                )
                if removable_index is None:
                    break
                actual_index = len(selected) - 1 - removable_index
                selected.pop(actual_index)
            if len(selected) < limit:
                selected.append(extra)
        return self._dedupe_phrases(selected[:limit])

    def _soften_mood_body(self, mood_body: str) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Mood", mood_body)]
        return ", ".join(self._dedupe_phrases(clauses[:3]))

    def _soften_outfit_body(
        self,
        outfit_body: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        shot_archetype: str,
        imperfect_layer: Dict[str, Any],
        allow_drop: bool,
    ) -> str:
        clothing_text, _, detail_text = self._clean_fragment(outfit_body).partition(";")
        clothing = self._dedupe_phrases(
            [chunk for chunk in re.split(r"\s*(?:,| and )\s*", clothing_text) if self._clean_fragment(chunk)]
        )
        details = self._dedupe_phrases(
            [chunk for chunk in re.split(r"\s*,\s*", detail_text) if self._clean_fragment(chunk)]
        )

        outfit_micro = self._clean_fragment(str(imperfect_layer.get("outfit_micro") or ""))
        if outfit_micro and outfit_micro.lower() not in ", ".join(details).lower():
            details.append(outfit_micro)

        if allow_drop and shot_archetype not in {"front_selfie", "mirror_selfie"}:
            clothing = self._drop_nonessential_outfit_item(clothing, context, scene)
        if allow_drop and len(details) > 2:
            details = self._dedupe_phrases(details[:1] + details[-1:])

        rebuilt = ", ".join(clothing)
        if details:
            rebuilt = f"{rebuilt}; {', '.join(self._dedupe_phrases(details))}" if rebuilt else ", ".join(self._dedupe_phrases(details))
        try:
            return self._normalize_outfit_sentence_for_prompt(rebuilt, scene, context)
        except PromptValidationError:
            return self._normalize_outfit_sentence_for_prompt(outfit_body, scene, context)

    def _drop_nonessential_outfit_item(self, clothing: List[str], context: Dict[str, Any], scene: Any) -> List[str]:
        if len(clothing) <= 3:
            return clothing
        required_objects = {obj.lower() for obj in self._behavior_object_terms(context, scene)}
        drop_candidates: List[str] = []
        for item in clothing:
            lowered = item.lower()
            category = self._outfit_category(item)
            protected = (
                category == "shoes"
                or ("bag" in lowered and "bag" in required_objects)
            )
            if protected:
                continue
            if category in {"accessory", "outerwear"}:
                drop_candidates.append(item)
        if not drop_candidates:
            return clothing
        to_drop = self._stable_choice(
            drop_candidates,
            self._scene_text(scene),
            ",".join(clothing),
            ",".join(sorted(required_objects)),
            "drop_nonessential_outfit_item",
        )
        return [item for item in clothing if self._normalize_phrase_key(item) != self._normalize_phrase_key(to_drop)]

    @staticmethod
    def _parse_anchor_values(anchor: str, prefix: str) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for chunk in anchor.replace(prefix, "").split(";"):
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            cleaned_key = key.strip()
            cleaned_value = value.strip()
            if cleaned_key and cleaned_value:
                values[cleaned_key] = cleaned_value
        return values

    def _identity_block(self, identity_anchor: str, body_anchor: str) -> str:
        identity_values = self._parse_anchor_values(identity_anchor, "stable identity anchor: ")
        body_values = self._parse_anchor_values(body_anchor, "body consistency anchor: ")
        age = self._ensure_english_fragment(identity_values.get("age", "22"), "22")
        if age.isdigit():
            age = f"{age}-year-old"
        phrases = [
            age,
            "woman",
            self._ensure_english_fragment(identity_values.get("face", "soft oval face"), "soft oval face"),
            self._ensure_english_fragment(identity_values.get("jawline", "gentle defined jawline"), "gentle defined jawline"),
            self._ensure_english_fragment(identity_values.get("nose", "straight natural nose"), "straight natural nose"),
            self._ensure_english_fragment(identity_values.get("eyes", "green almond eyes"), "green almond eyes"),
            self._ensure_english_fragment(identity_values.get("lips", "natural medium lips"), "natural medium lips"),
            self._ensure_english_fragment(identity_values.get("skin", "natural skin texture"), "natural skin texture"),
            self._ensure_english_fragment(identity_values.get("freckles", "subtle freckles"), "subtle freckles"),
            self._ensure_english_fragment(identity_values.get("hair", "light chestnut medium-length hair"), "light chestnut medium-length hair"),
            self._ensure_english_fragment(identity_values.get("makeup", "soft everyday makeup"), "soft everyday makeup"),
            self._ensure_english_fragment(body_values.get("body_type", "slim natural build"), "slim natural build"),
            self._ensure_english_fragment(body_values.get("estimated_height", "average height"), "average height"),
            self._ensure_english_fragment(body_values.get("shoulder_set", "relaxed shoulders"), "relaxed shoulders"),
            self._ensure_english_fragment(body_values.get("posture", "natural upright posture"), "natural upright posture"),
        ]
        return f"Identity: {'; '.join(self._dedupe_phrases(phrases))}."

    def _framing_block(self, framing_mode: str, shot_archetype: str, scene: Any, camera_distance_hint: str = "") -> str:
        lowered = self._scene_text(scene).lower()
        if self._is_travel_walk(lowered):
            return "3/4 body walking shot"
        canonical = {
            "full_body": "full body shot",
            "seated_table_shot": "waist-up seated candid shot",
            "mirror_selfie": "mirror selfie head-and-shoulders shot",
            "front_selfie": "front selfie head-and-shoulders shot",
            "close_portrait": "close portrait shot",
            "waist_up": "waist-up candid shot",
            "candid_handheld": "candid 3/4 body shot",
            "friend_shot": "candid 3/4 body shot",
        }
        if shot_archetype == "mirror_selfie" and "waist-up" in framing_mode:
            return "mirror selfie waist-up shot"
        framing = canonical.get(shot_archetype, "candid 3/4 body shot")
        if camera_distance_hint and shot_archetype in {"friend_shot", "candid_handheld", "seated_table_shot", "waist_up", "close_portrait"}:
            return f"{framing} {camera_distance_hint}".strip()
        return framing

    def _scene_block(
        self,
        context: Dict[str, Any],
        scene: Any,
        scene_desc: str,
        scene_loc: str,
        scene_tags: List[str],
        presence_layer: Dict[str, Any] | None = None,
        outfit_scene_props: List[str] | None = None,
    ) -> str:
        lowered = self._scene_text(scene).lower()
        coherence = self._resolve_place_coherence(context, scene, scene_body=scene_desc)
        visual_focus = self._strip_scene_noise(str(getattr(scene, "visual_focus", "") or "").strip())
        tag_prefix = self._scene_tag_prefix(scene_tags)
        behavior = context.get("behavioral_context")
        object_terms = self._dedupe_phrases(self._behavior_object_terms(context, scene) + list(outfit_scene_props or []))
        object_terms = [
            term
            for term in object_terms
            if self._object_is_legitimate(term, context, scene, coherence)
        ]
        visual_focus = self._sanitize_visual_focus(visual_focus, object_terms, coherence)
        movement, interaction, expression = self._behavior_scene_cues(context, scene)
        micro_detail = self._scene_micro_detail(scene, behavior, object_terms, visual_focus, context)
        scene_presence = list((presence_layer or {}).get("scene_cues") or [])
        if self._is_travel_walk(lowered):
            pieces = [f"{tag_prefix} walking through the airport terminal before boarding" if tag_prefix else "Walking through the airport terminal before boarding"]
            luggage_phrase = self._travel_luggage_phrase(lowered, visual_focus).lstrip(", ").strip()
            if luggage_phrase:
                pieces.append(f"with {luggage_phrase.replace('pulling ', '').replace('carrying ', '')}")
            if movement:
                pieces.append(movement)
            if interaction:
                pieces.append(interaction)
            if expression:
                pieces.append(expression)
            if micro_detail:
                pieces.append(micro_detail)
            if (
                any(token in lowered for token in ["waiting", "pause", "coffee", "gate"])
                and not any("pause already underway" in piece.lower() or "still for a second" in piece.lower() for piece in pieces)
            ):
                pieces.append("a pause already underway")
            for object_term in object_terms:
                phrase = self._object_scene_phrase(object_term, scene, context=context, coherence=coherence)
                if phrase and phrase.lower() not in " ".join(pieces).lower():
                    pieces.append(phrase)
            for cue in scene_presence:
                if cue.lower() not in " ".join(pieces).lower():
                    pieces.append(cue)
            return f"Scene: {', '.join(self._dedupe_semantic_phrases(pieces))}."

        activity = str(getattr(scene, "activity", "") or "").strip().replace("_", " ")
        base_scene = self._ensure_english_fragment(self._strip_scene_noise(scene_desc), "")
        location = self._ensure_english_fragment(self._clean_fragment(scene_loc), self._scene_location_fallback(scene))
        pieces: List[str] = []
        if base_scene:
            pieces.append(base_scene)
        elif activity and location:
            pieces.append(f"{activity} at {location}")
        elif location:
            pieces.append(f"At {location}")
        if location and location.lower() not in (base_scene or "").lower():
            pieces.append(f"at {location}")
        if activity and activity.lower() not in " ".join(pieces).lower():
            pieces.append(activity)
        if visual_focus and visual_focus.lower() not in " ".join(pieces).lower():
            pieces.append(f"with {visual_focus}")
        if movement and movement.lower() not in " ".join(pieces).lower():
            pieces.append(movement)
        if interaction and interaction.lower() not in " ".join(pieces).lower():
            pieces.append(interaction)
        if expression and expression.lower() not in " ".join(pieces).lower():
            pieces.append(expression)
        if micro_detail and micro_detail.lower() not in " ".join(pieces).lower():
            pieces.append(micro_detail)
        if (
            any(token in lowered for token in ["waiting", "pause", "coffee", "gate"])
            and not any("pause already underway" in piece.lower() or "still for a second" in piece.lower() for piece in pieces)
        ):
            pieces.append("a pause already underway")
        for object_term in object_terms:
            phrase = self._object_scene_phrase(object_term, scene, context=context, coherence=coherence)
            if phrase and phrase.lower() not in " ".join(pieces).lower():
                pieces.append(phrase)
        for cue in scene_presence:
            if cue.lower() not in " ".join(pieces).lower():
                pieces.append(cue)
        return f"Scene: {', '.join(self._dedupe_semantic_phrases(pieces))}."

    def _outfit_block(self, outfit_sentence: str) -> str:
        cleaned = self._normalize_outfit_sentence_for_prompt(outfit_sentence)
        return f"Outfit: {cleaned}."

    def _environment_block(self, context: Dict[str, Any], scene: Any, scene_loc: str, scene_tags: List[str], continuity_block: str) -> str:
        del continuity_block, scene_tags
        lighting = self._lighting_hint(getattr(scene, "time_of_day", "day"))
        coherence = self._resolve_place_coherence(context, scene, environment_body=scene_loc)
        location_phrase = self._clean_fragment(coherence.canonical_location or scene_loc)
        behavior = context.get("behavioral_context")
        parts: List[str] = [
            f"Environment: photorealistic {location_phrase}",
            "physically plausible spatial depth",
            "accurate perspective and scale",
            f"{lighting} behaving as natural available light",
        ]
        if coherence.mode.startswith("airport"):
            parts.insert(1, "real terminal architecture")
        else:
            parts.insert(1, "lived-in environmental detail")
        if behavior is not None and coherence.allow_background_people:
            presence = {
                "alone": "no other people in frame",
                "light_public": "soft background people only",
                "social": "public life present but secondary",
            }.get(str(getattr(behavior, "social_mode", "alone") or "alone"), "")
            if presence:
                parts.append(presence)
        return f"{'; '.join(self._dedupe_phrases(parts))}."

    def _mood_block(
        self,
        context: Dict[str, Any],
        scene: Any,
        continuity_block: str,
        presence_layer: Dict[str, Any] | None = None,
    ) -> str:
        del continuity_block
        coherence = self._resolve_place_coherence(context, scene)
        mood = str(getattr(scene, "mood", "") or "").strip().lower()
        behavior = context.get("behavioral_context")
        mood_presence = list((presence_layer or {}).get("mood_cues") or [])
        time_of_day = str(getattr(scene, "time_of_day", "") or "").lower()
        outfit_override = str(context.get("outfit_override") or "").lower()
        canonical = {
            "curious": "quiet curiosity",
            "focused": "composed focus",
            "calm": "calm ease",
            "active": "light forward momentum",
            "natural": "natural ease",
            "tired": "gentle low energy",
            "soft": "soft calm",
            "happy": "light warmth",
        }
        base = canonical.get(mood, "quiet confidence")
        if outfit_override == "slightly_sexy":
            return "Mood: quietly intimate body language, a little more open through the posture."
        if coherence.private_scene and time_of_day in {"early_morning", "morning", "late_morning"}:
            return "Mood: already happening by the time the camera catches it."
        if behavior is not None:
            arc_mood = {
                "arrival": "calm arrival mood",
                "routine": "grounded routine mood",
                "reflection": "reflective calm",
                "transition": "transitional mood",
                "departure": "focused before-leaving mood",
            }.get(str(getattr(behavior, "emotional_arc", "routine") or "routine"), "")
            self_presentation = str(getattr(behavior, "self_presentation", "") or "").replace("_", " ")
            details = [base]
            if arc_mood and not self._is_kitchen_coffee_scene(context, scene):
                details.append(arc_mood)
            if self_presentation:
                details.append(f"{self_presentation} self-presentation")
            details.extend(mood_presence)
            return f"Mood: {', '.join(self._dedupe_phrases(details))}."
        if mood_presence:
            return f"Mood: {', '.join(self._dedupe_phrases([base] + mood_presence))}."
        return f"Mood: {base}."

    def _presence_layer(
        self,
        context: Dict[str, Any],
        scene: Any,
        outfit_bundle: OutfitBundle,
        shot_archetype: str,
        platform_behavior: str,
    ) -> Dict[str, Any]:
        del platform_behavior
        behavior = context.get("behavioral_context")
        object_terms = self._behavior_object_terms(context, scene)
        descriptor = " ".join(
            [
                str(getattr(outfit_bundle, "top", "") or ""),
                str(getattr(outfit_bundle, "bottom", "") or ""),
                str(getattr(outfit_bundle, "outerwear", "") or ""),
                str(getattr(outfit_bundle, "shoes", "") or ""),
                str(getattr(outfit_bundle, "accessories", "") or ""),
                str(getattr(outfit_bundle, "fit", "") or ""),
                str(getattr(outfit_bundle, "fabric", "") or ""),
                str(getattr(outfit_bundle, "condition", "") or ""),
                str(getattr(outfit_bundle, "styling", "") or ""),
                str(getattr(outfit_bundle, "outfit_style", "") or ""),
                str(getattr(outfit_bundle, "outfit_override_used", "") or ""),
            ]
        ).lower()
        relaxed = any(token in descriptor for token in ["soft", "relaxed", "easy", "lived-in", "knit", "drape", "loose", "cardigan"])
        fitted = any(token in descriptor for token in ["fitted", "body-skimming", "close fit", "ribbed", "silhouette", "defined", "open neckline"])
        structured = any(token in descriptor for token in ["tailored", "blazer", "neat"])
        seated = shot_archetype == "seated_table_shot" or any(token in self._scene_text(scene).lower() for token in ["seated", "sitting", "chair", "table"])
        override_key = self._presence_override_key(outfit_bundle, scene, context)

        posture_cue = self._presence_posture_cue(behavior, relaxed, fitted, structured)
        asymmetry_cue = self._presence_asymmetry_cue(object_terms, shot_archetype)
        imperfection_cue = self._presence_imperfection_cue(behavior, seated)
        fabric_cue = self._presence_fabric_cue(outfit_bundle, object_terms, relaxed, fitted, seated)
        interaction_cue = self._presence_interaction_cue(outfit_bundle, object_terms, shot_archetype)
        body_language_cue = self._presence_body_language_cue(behavior, override_key, relaxed, fitted, structured)
        camera_distance = self._presence_camera_distance_cue(behavior, override_key, shot_archetype, relaxed, fitted)

        scene_cues = self._dedupe_phrases([posture_cue, asymmetry_cue, fabric_cue, interaction_cue, imperfection_cue])[:5]
        mood_cues = self._dedupe_phrases(
            [
                body_language_cue,
                "in-the-moment presence",
                "unposed asymmetry kept in the frame",
            ]
        )[:3]

        return {
            "scene_cues": scene_cues,
            "mood_cues": mood_cues,
            "camera_distance": camera_distance,
            "micro_body_behavior": ", ".join(scene_cues[:3]),
            "interaction_realism": interaction_cue,
            "anti_model_symmetry": ", ".join(self._dedupe_phrases([asymmetry_cue, imperfection_cue, "in-the-moment presence"])),
            "summary": ", ".join(self._dedupe_phrases(scene_cues[:2] + mood_cues[:2])),
        }

    def _perceived_outfit_sentence(
        self,
        outfit_bundle: OutfitBundle,
        fallback_sentence: str,
        scene: Any,
        context: Dict[str, Any],
    ) -> str:
        top = self._clean_fragment(getattr(outfit_bundle, "top", "") or "")
        bottom = self._clean_fragment(getattr(outfit_bundle, "bottom", "") or "")
        outerwear = self._clean_fragment(getattr(outfit_bundle, "outerwear", "") or "")
        shoes = self._clean_fragment(getattr(outfit_bundle, "shoes", "") or "")
        accessories = self._clean_fragment(getattr(outfit_bundle, "accessories", "") or "")
        if shoes and any(token in shoes.lower() for token in ["sneakers", "trainers"]) and "worn" not in shoes.lower():
            shoes = f"{shoes} worn in"

        clothing: List[str] = []
        if top:
            clothing.append(top)
        if bottom:
            clothing.append(bottom)
        for piece in [outerwear, shoes, accessories]:
            if piece:
                clothing.append(piece)

        details = self._dedupe_phrases(
            [
                self._clean_fragment(getattr(outfit_bundle, "fit", "") or ""),
                self._clean_fragment(getattr(outfit_bundle, "fabric", "") or ""),
                self._clean_fragment(getattr(outfit_bundle, "condition", "") or ""),
                self._clean_fragment(getattr(outfit_bundle, "styling", "") or ""),
                "slightly shifted and not perfectly arranged",
            ]
        )

        if clothing:
            rebuilt = ", ".join(self._normalize_outfit_clothing_items(clothing))
            detail_phrase = self._grounded_outfit_detail_phrase(details)
            if detail_phrase:
                rebuilt = f"{rebuilt}, {detail_phrase}"
            try:
                return self.validate_outfit_sentence(rebuilt)
            except PromptValidationError:
                pass
        return self._normalize_outfit_sentence_for_prompt(fallback_sentence, scene, context)

    def _presence_override_key(self, outfit_bundle: OutfitBundle, scene: Any, context: Dict[str, Any]) -> str:
        raw = self._clean_fragment(
            getattr(outfit_bundle, "outfit_override_used", "")
            or getattr(scene, "outfit_override", "")
            or context.get("outfit_override")
            or ""
        ).lower().replace(" ", "_")
        allowed = set(getattr(self.outfit_generator, "OVERRIDE_HINTS", {}).keys())
        return raw if raw in allowed else ""

    @staticmethod
    def _presence_posture_cue(behavior: Any, relaxed: bool, fitted: bool, structured: bool) -> str:
        energy = str(getattr(behavior, "energy_level", "medium") or "medium").lower() if behavior is not None else "medium"
        if fitted or structured:
            return "posture held a little more intentionally so the clothing catches lightly at the waist and shoulders"
        if relaxed and energy == "low":
            return "shoulders resting a touch lower with a soft bend through the torso"
        if energy == "high":
            return "weight shifting naturally through one hip instead of a frozen centered stance"
        return "weight settled slightly off-center with a natural line through the torso"

    @staticmethod
    def _presence_asymmetry_cue(object_terms: List[str], shot_archetype: str) -> str:
        if "carry on" in object_terms or "bag" in object_terms:
            return "one shoulder sitting slightly higher from the bag or handle and the torso turned a few degrees"
        if "coffee cup" in object_terms:
            return "one hand sitting a little higher around the cup while the other side of the body stays looser"
        if shot_archetype in {"front_selfie", "mirror_selfie"}:
            return "phone-side shoulder fractionally lifted with the body angled a little off-center"
        return "one arm a little higher than the other with the body turned slightly off-center"

    @staticmethod
    def _presence_imperfection_cue(behavior: Any, seated: bool) -> str:
        energy = str(getattr(behavior, "energy_level", "medium") or "medium").lower() if behavior is not None else "medium"
        if seated:
            return "back not perfectly aligned with the seat and the head tipped lightly"
        if energy == "low":
            return "back not fully straight and chin tipped slightly instead of held perfectly level"
        return "head tipped slightly with balance not split perfectly down the center"

    def _presence_fabric_cue(
        self,
        outfit_bundle: OutfitBundle,
        object_terms: List[str],
        relaxed: bool,
        fitted: bool,
        seated: bool,
    ) -> str:
        top_text = " ".join(
            [
                str(getattr(outfit_bundle, "top", "") or ""),
                str(getattr(outfit_bundle, "outerwear", "") or ""),
                str(getattr(outfit_bundle, "fabric", "") or ""),
                str(getattr(outfit_bundle, "condition", "") or ""),
            ]
        ).lower()
        has_sleeve = any(token in top_text for token in ["sleeve", "cardigan", "jacket", "coat", "knit", "shirt", "top"])
        if fitted:
            return "fabric catching lightly at the waist or shoulder as the body turns"
        if relaxed and ("coffee cup" in object_terms or seated) and has_sleeve:
            return "fabric easing into soft folds at the waist and gathering a little at the elbow where the sleeve bends"
        if relaxed:
            return "fabric settling into soft real folds instead of a clean showroom fall"
        if seated:
            return "clothing settling with believable folds where the body meets the seat"
        return "clothing shifting slightly on the body with small lived-in folds"

    def _presence_interaction_cue(self, outfit_bundle: OutfitBundle, object_terms: List[str], shot_archetype: str) -> str:
        outer_text = " ".join(
            [
                str(getattr(outfit_bundle, "top", "") or ""),
                str(getattr(outfit_bundle, "outerwear", "") or ""),
                str(getattr(outfit_bundle, "accessories", "") or ""),
            ]
        ).lower()
        cues: List[str] = []
        if "coffee cup" in object_terms:
            sleeve_touch = "sleeve brushing the cup" if any(token in outer_text for token in ["cardigan", "jacket", "coat", "knit", "sleeve"]) else "wrist bending naturally around the cup"
            cues.append(f"coffee cup held with a relaxed uneven grip and light finger pressure, {sleeve_touch}")
        if "carry on" in object_terms:
            cues.append("carry on handle held without perfect alignment, with the wrist relaxed and the clothing pulling lightly near the shoulder")
        if "bag" in object_terms:
            cues.append("bag strap sitting naturally so the clothing shifts slightly under it")
        if "phone" in object_terms and shot_archetype not in {"front_selfie", "mirror_selfie"}:
            cues.append("phone held casually instead of squared for presentation")
        if cues:
            return ", ".join(self._dedupe_phrases(cues[:2]))
        return "hands interacting with objects in a casual imperfect way"

    @staticmethod
    def _presence_body_language_cue(behavior: Any, override_key: str, relaxed: bool, fitted: bool, structured: bool) -> str:
        self_presentation = str(getattr(behavior, "self_presentation", "") or "").lower() if behavior is not None else ""
        if override_key in {"slightly_sexy", "intimate_home", "tight_silhouette"}:
            return "quietly intimate body language with a slightly more open posture"
        if override_key == "more_feminine":
            return "softly confident body language with gentle openness"
        if self_presentation in {"focused", "composed"}:
            return "more closed body language that still feels naturally inhabited"
        if relaxed:
            return "relaxed body language that feels lived-in rather than arranged"
        if fitted or structured:
            return "quietly confident body language without a staged pose"
        return "natural body language with no posed look"

    @staticmethod
    def _presence_camera_distance_cue(
        behavior: Any,
        override_key: str,
        shot_archetype: str,
        relaxed: bool,
        fitted: bool,
    ) -> str:
        energy = str(getattr(behavior, "energy_level", "medium") or "medium").lower() if behavior is not None else "medium"
        if shot_archetype in {"front_selfie", "mirror_selfie", "full_body"}:
            return ""
        if override_key in {"slightly_sexy", "intimate_home", "tight_silhouette"}:
            return "from slightly closer private distance"
        if override_key == "more_feminine" or fitted:
            return "from easy conversational distance"
        if shot_archetype in {"friend_shot", "candid_handheld"} and energy == "high":
            return "from slightly looser observer distance"
        if relaxed and shot_archetype == "seated_table_shot":
            return "from close table-side distance"
        return ""

    @staticmethod
    def _scene_location_fallback(scene: Any) -> str:
        lowered = PromptComposer._scene_text(scene).lower()
        if any(token in lowered for token in ["airport", "terminal", "boarding", "gate"]):
            return "airport terminal"
        if "cafe" in lowered:
            return "cafe interior"
        if any(token in lowered for token in ["home", "kitchen"]):
            return "home interior"
        return "everyday location"

    @staticmethod
    def _context_day_type(context: Dict[str, Any]) -> str:
        life_state = context.get("life_state")
        return str(context.get("day_type") or getattr(life_state, "day_type", "") or "").strip().lower()

    def _scene_supports_departure_bag(self, scene: Any, context: Dict[str, Any]) -> bool:
        lowered = self._scene_text(scene).lower()
        day_type = self._context_day_type(context)
        return (
            day_type in {"layover_day", "travel_day", "airport_transfer"}
            or any(
                token in lowered
                for token in [
                    "by the door",
                    "heading out",
                    "returning",
                    "return home",
                    "packed",
                    "packing",
                    "unpacked",
                    "after arriving",
                    "before leaving",
                    "arrival",
                    "departure",
                ]
            )
        )

    def _resolve_place_coherence(
        self,
        context: Dict[str, Any],
        scene: Any,
        *,
        scene_body: str = "",
        environment_body: str = "",
        outfit_body: str = "",
    ) -> PlaceCoherenceState:
        behavior = context.get("behavioral_context")
        place_anchor = str(getattr(behavior, "place_anchor", getattr(behavior, "familiar_place_anchor", "")) or "").lower()
        habit = str(getattr(behavior, "habit", getattr(behavior, "selected_habit", "")) or "").lower()
        day_type = self._context_day_type(context)
        lowered = " ".join(
            [
                self._scene_text(scene),
                str(scene_body or ""),
                str(environment_body or ""),
                str(outfit_body or ""),
            ]
        ).lower()

        travel_context = (
            day_type in {"layover_day", "travel_day", "airport_transfer"}
            or place_anchor in {"terminal_gate", "hotel_window"}
            or any(
                token in lowered
                for token in [
                    "airport",
                    "terminal",
                    "gate",
                    "boarding",
                    "flight",
                    "layover",
                    "hotel",
                    "travel",
                    "check-in",
                    "check in",
                ]
            )
        )
        transit_context = place_anchor == "terminal_gate" or any(
            token in lowered for token in ["airport", "terminal", "gate", "boarding", "runway"]
        )
        cafe_context = place_anchor == "cafe_corner" or "cafe" in lowered
        kitchen_context = place_anchor == "kitchen_corner" or any(
            token in lowered for token in ["kitchen", "kitchenette", "breakfast corner", "counter light"]
        )
        bathroom_context = "mirror" in lowered and "bathroom" in lowered
        bedside_context = "bedside" in lowered or ("bed" in lowered and not transit_context and not cafe_context)
        hotel_private_context = (
            place_anchor == "hotel_window"
            or ("hotel" in lowered and not kitchen_context and not transit_context)
            or any(token in lowered for token in ["hotel room", "window corner"])
        )
        home_private_context = any(token in lowered for token in ["home", "living room", "room corner"]) and not kitchen_context

        if transit_context:
            waiting_context = any(
                token in lowered for token in ["waiting", "gate", "seated", "seat", "seating", "row seating", "before boarding"]
            )
            canonical_location = "airport gate" if waiting_context else "airport terminal"
            return PlaceCoherenceState(
                mode="airport_gate" if waiting_context else "airport_terminal",
                canonical_location=canonical_location,
                location_keywords=("airport", "terminal", "gate", "boarding"),
                private_scene=False,
                public_scene=True,
                travel_context=True,
                allow_background_people=True,
                allow_bag_prop=True,
                allow_wearable_bag=True,
            )
        if cafe_context:
            return PlaceCoherenceState(
                mode="cafe_interior",
                canonical_location="cafe interior",
                location_keywords=("cafe", "coffee shop", "table"),
                private_scene=False,
                public_scene=True,
                travel_context=travel_context,
                allow_background_people=True,
                allow_bag_prop=True,
                allow_wearable_bag=True,
            )
        if kitchen_context:
            if travel_context or day_type == "layover_day":
                if "hotel" in lowered or place_anchor == "hotel_window":
                    canonical_location = "hotel kitchenette"
                elif day_type == "layover_day":
                    canonical_location = "small hotel breakfast corner"
                else:
                    canonical_location = "small breakfast corner"
                return PlaceCoherenceState(
                    mode="hotel_kitchenette",
                    canonical_location=canonical_location,
                    location_keywords=("kitchen", "kitchenette", "breakfast", "counter", "coffee"),
                    private_scene=True,
                    public_scene=False,
                    travel_context=True,
                    allow_background_people=False,
                    allow_bag_prop=True,
                    allow_wearable_bag=False,
                )
            return PlaceCoherenceState(
                mode="home_kitchen",
                canonical_location="home kitchen",
                location_keywords=("home", "kitchen", "counter", "coffee"),
                private_scene=True,
                public_scene=False,
                travel_context=False,
                allow_background_people=False,
                allow_bag_prop=self._scene_supports_departure_bag(scene, context),
                allow_wearable_bag=False,
            )
        if bathroom_context:
            return PlaceCoherenceState(
                mode="bathroom_mirror",
                canonical_location="bathroom mirror",
                location_keywords=("bathroom", "mirror", "sink"),
                private_scene=True,
                public_scene=False,
                travel_context=travel_context,
                allow_background_people=False,
                allow_bag_prop=travel_context,
                allow_wearable_bag=False,
            )
        if bedside_context:
            return PlaceCoherenceState(
                mode="bedside",
                canonical_location="bedside corner",
                location_keywords=("bedside", "bed", "room"),
                private_scene=True,
                public_scene=False,
                travel_context=travel_context,
                allow_background_people=False,
                allow_bag_prop=travel_context,
                allow_wearable_bag=False,
            )
        if hotel_private_context:
            canonical_location = "hotel window corner" if "window" in lowered else "hotel room"
            return PlaceCoherenceState(
                mode="hotel_private",
                canonical_location=canonical_location,
                location_keywords=("hotel", "room", "window"),
                private_scene=True,
                public_scene=False,
                travel_context=True,
                allow_background_people=False,
                allow_bag_prop=True,
                allow_wearable_bag=False,
            )
        if home_private_context:
            return PlaceCoherenceState(
                mode="home_private",
                canonical_location="quiet home room corner",
                location_keywords=("home", "room", "corner"),
                private_scene=True,
                public_scene=False,
                travel_context=False,
                allow_background_people=False,
                allow_bag_prop=self._scene_supports_departure_bag(scene, context),
                allow_wearable_bag=False,
            )
        return PlaceCoherenceState(
            mode="generic_daily",
            canonical_location=self._scene_location_fallback(scene),
            location_keywords=tuple(self._scene_location_fallback(scene).lower().split()),
            private_scene=False,
            public_scene=False,
            travel_context=travel_context,
            allow_background_people=False,
            allow_bag_prop=travel_context,
            allow_wearable_bag=not travel_context,
        )

    @staticmethod
    def _clean_fragment(text: str) -> str:
        cleaned = " ".join(str(text or "").replace("_", " ").split())
        return cleaned.strip(" ,;:.")

    def _strip_scene_noise(self, text: str) -> str:
        cleaned = self._clean_fragment(text)
        banned = [
            "golden hour",
            "morning light",
            "evening light",
            "daylight",
            "lighting",
            "outfit",
            "mood",
            "curious",
            "focused",
            "calm",
            "happy",
            "sad",
            "soft light",
        ]
        result = cleaned
        for token in banned:
            result = re.sub(re.escape(token), " ", result, flags=re.IGNORECASE)
        return self._clean_fragment(result)

    @staticmethod
    def _normalize_phrase_key(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()

    def _dedupe_phrases(self, phrases: List[str]) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        for phrase in phrases:
            cleaned = self._clean_fragment(phrase)
            if not cleaned:
                continue
            key = self._normalize_phrase_key(cleaned)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _dedupe_semantic_phrases(self, phrases: List[str]) -> List[str]:
        result: List[str] = []
        seen_entries: List[Dict[str, Any]] = []
        for phrase in self._dedupe_phrases(phrases):
            clause = {
                "block": "Scene",
                "text": phrase,
                "key": self._normalize_phrase_key(phrase),
                "tokens": self._semantic_tokens(phrase),
            }
            if any(self._clauses_overlap(clause, existing) for existing in seen_entries):
                continue
            seen_entries.append(clause)
            result.append(phrase)
        return result

    @staticmethod
    def _sequence_key(sequence: str) -> str:
        return PromptComposer._clean_fragment(str(sequence or "").lower())

    @staticmethod
    def _sequence_words(sequence: str) -> List[str]:
        return re.findall(r"[a-z]+", str(sequence or "").lower())

    def _sequence_content_words(self, sequence: str) -> List[str]:
        return [
            word
            for word in self._sequence_words(sequence)
            if len(word) > 2 and word not in self.DUPLICATE_SEQUENCE_STOPWORDS
        ]

    def _garment_phrase_family(self, text: str) -> str:
        lowered = self._clean_fragment(text).lower()
        if not lowered:
            return ""
        for family, phrases in self.GARMENT_DUPLICATE_FAMILIES.items():
            if any(phrase in lowered for phrase in phrases):
                return family
        return ""

    def _garment_category_hint(self, text: str) -> str:
        lowered = self._clean_fragment(text).lower()
        if not lowered:
            return ""
        category = self._outfit_category(lowered)
        if category:
            return category
        for family, tokens in self.GARMENT_CATEGORY_TOKENS.items():
            if any(token in lowered for token in tokens):
                return family
        return ""

    def _is_soft_garment_overlap(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        blocks = {str(left.get("block") or ""), str(right.get("block") or "")}
        if "Outfit" not in blocks:
            return False
        left_text = self._clean_fragment(str(left.get("text") or ""))
        right_text = self._clean_fragment(str(right.get("text") or ""))
        if not left_text or not right_text:
            return False
        left_family = self._garment_phrase_family(left_text)
        right_family = self._garment_phrase_family(right_text)
        left_category = self._garment_category_hint(left_text)
        right_category = self._garment_category_hint(right_text)
        if not left_category or not right_category or left_category != right_category:
            return False
        if left_family and right_family and left_family == right_family:
            return True
        lowered = f"{left_text.lower()} {right_text.lower()}"
        return any(
            token in lowered
            for token in (
                "without trying too hard",
                "natural drape",
                "fall straight",
                "falls naturally",
                "slightly imperfect",
                "effortless",
                "soft matte",
            )
        )

    def _is_fatal_duplicate_sequence(self, entry: Mapping[str, Any]) -> bool:
        if not bool(entry.get("critical")):
            return False
        sequence = self._clean_fragment(str(entry.get("sequence") or ""))
        if not sequence:
            return False
        content_words = self._sequence_content_words(sequence)
        if len(content_words) < 3:
            return False
        if any(token in sequence.lower() for token in ["a little off", "little off", "off center", "a little higher"]):
            return False
        if self._garment_phrase_family(sequence) and int(entry.get("count") or 0) <= 2:
            return False
        return True

    def _detect_duplicate_sequence_candidates(self, prompt: str) -> List[Dict[str, Any]]:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            return []

        candidates: Dict[str, Dict[str, Any]] = {}
        lowered = normalized_prompt.lower()

        def _add_candidate(sequence: str, kind: str, *, count: int, critical: bool, kept_reason: str = "") -> None:
            cleaned_sequence = self._clean_fragment(sequence)
            if not cleaned_sequence:
                return
            if self._garment_phrase_family(cleaned_sequence) and count <= 2:
                critical = False
                kept_reason = kept_reason or "garment_phrase_overlap"
            key = f"{kind}:{self._sequence_key(cleaned_sequence)}"
            current = candidates.get(key)
            payload = {
                "sequence": cleaned_sequence,
                "kind": kind,
                "count": count,
                "critical": critical,
                "kept_reason": kept_reason,
            }
            if current is None or (
                int(payload["critical"]) > int(current["critical"])
                or payload["count"] > current["count"]
            ):
                candidates[key] = payload

        for match in re.finditer(r"\b([a-z]+)(?:\s+\1\b)+", lowered):
            sequence = match.group(0)
            content_words = self._sequence_content_words(sequence)
            kept_reason = "" if content_words else "functional_word_repeat"
            _add_candidate(
                sequence,
                "adjacent_word",
                count=len(self._sequence_words(sequence)),
                critical=bool(content_words),
                kept_reason=kept_reason,
            )

        for size in self.DUPLICATE_SEQUENCE_SCAN_RANGE:
            pattern = re.compile(
                rf"\b((?:[a-z]+(?:\s+[a-z]+){{{size - 1}}}))\s+\1\b",
                re.IGNORECASE,
            )
            for match in pattern.finditer(normalized_prompt):
                sequence = match.group(1)
                content_words = self._sequence_content_words(sequence)
                kept_reason = "" if len(content_words) >= 2 else "short_or_functional_repeat"
                _add_candidate(
                    sequence,
                    f"adjacent_ngram_{size}",
                    count=2,
                    critical=len(content_words) >= 2,
                    kept_reason=kept_reason,
                )

        prompt_words = re.findall(r"[a-z]+", lowered)
        for size in (2, 3):
            counts: Dict[str, int] = {}
            for idx in range(len(prompt_words) - size + 1):
                phrase_words = prompt_words[idx : idx + size]
                content_words = [
                    word
                    for word in phrase_words
                    if len(word) > 2 and word not in self.DUPLICATE_SEQUENCE_STOPWORDS
                ]
                if len(content_words) < 2:
                    continue
                phrase = " ".join(phrase_words)
                counts[phrase] = counts.get(phrase, 0) + 1
            for phrase, count in counts.items():
                if count < 2:
                    continue
                critical = count >= 3
                kept_reason = "" if critical else "single_anchor_repeat"
                _add_candidate(
                    phrase,
                    f"global_ngram_{size}",
                    count=count,
                    critical=critical,
                    kept_reason=kept_reason,
                )

        return sorted(
            candidates.values(),
            key=lambda entry: (-int(bool(entry.get("critical"))), -int(entry.get("count") or 0), str(entry.get("sequence") or "")),
        )

    def _repair_duplicate_sequences_in_text(self, text: str, *, aggressive: bool) -> str:
        repaired = str(text or "")
        previous = None
        while repaired != previous:
            previous = repaired
            repaired = re.sub(
                r"\b([a-z]+)(?:\s+\1\b)+",
                r"\1",
                repaired,
                flags=re.IGNORECASE,
            )
            for size in self.DUPLICATE_SEQUENCE_SCAN_RANGE:
                repaired = re.sub(
                    rf"\b((?:[a-z]+(?:\s+[a-z]+){{{size - 1}}}))\s+\1\b",
                    r"\1",
                    repaired,
                    flags=re.IGNORECASE,
                )
        repaired = re.sub(r"\s{2,}", " ", repaired)
        repaired = re.sub(r"\s+([,.;:])", r"\1", repaired)
        repaired = re.sub(r"([,.;:]){2,}", r"\1", repaired)
        repaired = re.sub(r"\s*\.\s*\.", ".", repaired)
        repaired = repaired.strip()
        if aggressive:
            repaired = repaired.replace(", ,", ",")
            repaired = repaired.replace(" and and ", " and ")
        return repaired

    def _sanitize_duplicate_sequences_in_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        aggressive: bool,
        outfit_sentence: str = "",
        step: str = "",
    ) -> Dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        block_map = self._prompt_block_map(normalized_prompt)
        before_candidates = self._detect_duplicate_sequence_candidates(normalized_prompt)
        if not block_map:
            return {
                "prompt": self._repair_duplicate_sequences_in_text(normalized_prompt, aggressive=aggressive),
                "duplicate_sequence_candidates": [entry["sequence"] for entry in before_candidates],
                "duplicate_sequence_removed": [],
                "duplicate_sequence_kept_reason": [
                    f"{entry['sequence']}:{entry['kept_reason']}"
                    for entry in before_candidates
                    if entry.get("kept_reason")
                ],
                "sanitized_prompt_applied": False,
                "prompt_blocks": {},
                "sanitization_step": step,
            }

        prompt_blocks = dict(block_map)
        for label in ["Identity", "Scene", "Outfit", "Environment", "Mood"]:
            body = self._split_block_label(prompt_blocks[label])[1]
            repaired_body = self._repair_duplicate_sequences_in_text(body, aggressive=aggressive)
            if label == "Scene":
                scene_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", repaired_body)]
                for object_term in self._behavior_object_terms(context, scene):
                    if object_term and object_term.lower() not in ", ".join(scene_clauses).lower():
                        phrase = self._object_scene_phrase(object_term, scene, context=context)
                        if phrase:
                            scene_clauses.append(phrase)
                repaired_body = ", ".join(self._dedupe_semantic_phrases(scene_clauses)) if scene_clauses else repaired_body
            elif label == "Mood":
                mood_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Mood", repaired_body)]
                repaired_body = ", ".join(self._dedupe_phrases(mood_clauses)) if mood_clauses else repaired_body
            elif label == "Outfit":
                preferred_outfit = self._clean_fragment(outfit_sentence) or repaired_body
                try:
                    compacted = self._compact_outfit_phrase_clusters(repaired_body or preferred_outfit, aggressive=aggressive)
                    repaired_body = self._normalize_outfit_sentence_for_prompt(
                        str(compacted.get("outfit_sentence") or repaired_body or preferred_outfit),
                        scene,
                        context,
                    )
                except PromptValidationError:
                    repaired_body = self._normalize_outfit_sentence_for_prompt(preferred_outfit, scene, context)
            prompt_blocks[label] = (
                prompt_blocks[label]
                if label == "Framing"
                else f"{label}: {self._clean_fragment(repaired_body)}."
            )

        repaired_prompt = "\n\n".join(
            [
                prompt_blocks["Identity"],
                prompt_blocks["Framing"],
                prompt_blocks["Scene"],
                prompt_blocks["Outfit"],
                prompt_blocks["Environment"],
                prompt_blocks["Mood"],
            ]
        )
        after_candidates = self._detect_duplicate_sequence_candidates(repaired_prompt)
        before_keys = {self._sequence_key(entry["sequence"]) for entry in before_candidates}
        after_keys = {self._sequence_key(entry["sequence"]) for entry in after_candidates}
        removed = [
            entry["sequence"]
            for entry in before_candidates
            if self._sequence_key(entry["sequence"]) not in after_keys
        ]
        kept = [
            f"{entry['sequence']}:{entry['kept_reason'] or ('still_critical' if entry.get('critical') else 'kept')}"
            for entry in after_candidates
        ]
        return {
            "prompt": repaired_prompt,
            "duplicate_sequence_candidates": [entry["sequence"] for entry in before_candidates],
            "duplicate_sequence_removed": removed,
            "duplicate_sequence_kept_reason": kept,
            "sanitized_prompt_applied": repaired_prompt != normalized_prompt,
            "prompt_blocks": prompt_blocks,
            "sanitization_step": step,
        }

    def _build_safe_fallback_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        shot_archetype: str = "",
    ) -> Dict[str, Any]:
        block_map = self._prompt_block_map(prompt)
        identity_body = self._split_block_label(block_map.get("Identity", ""))[1] if block_map else ""
        framing_block = block_map.get("Framing", "") if block_map else ""
        resolved_shot = shot_archetype or self._resolve_shot_archetype(scene, context, context.get("recent_moment_memory") or [])
        if not framing_block:
            framing_block = self._framing_block(self._framing_mode(resolved_shot, self._resolve_generation_mode(scene, resolved_shot)), resolved_shot, scene)

        identity_text = self._recover_identity_body(identity_body, context, force_floor=True)

        preferred_outfit = self._clean_fragment(outfit_sentence) or self.extract_outfit_sentence(prompt) or self._contextual_outfit_fallback_sentence(scene, context)
        scene_anchor = self._scene_presence_lead(scene, self._minimal_scene_body(scene)) or self._minimal_scene_body(scene)
        coherence = self._resolve_place_coherence(context, scene, outfit_body=preferred_outfit)
        scene_objects = [
            phrase
            for phrase in [
                self._object_scene_phrase(term, scene, context=context)
                for term in self._behavior_object_terms(context, scene)[:3]
            ]
            if phrase
        ]
        lowered_scene_text = self._scene_text(scene).lower()
        if (
            any(token in lowered_scene_text for token in ["waiting", "coffee", "pause"])
            and not any("pause" in phrase.lower() or "still for a second" in phrase.lower() for phrase in scene_objects)
        ):
            scene_objects.append("a pause already underway")
        if (
            any(token in lowered_scene_text for token in ["terminal", "gate", "boarding"])
            and "checking the boarding screen occasionally" not in " ".join(scene_objects).lower()
        ):
            scene_objects.append("checking the boarding screen occasionally")
        scene_text = ", ".join(self._dedupe_semantic_phrases([self._smooth_scene_clause(scene_anchor)] + [self._smooth_scene_clause(obj) for obj in scene_objects])[:6]) or self._smooth_scene_clause(scene_anchor)

        compacted = self._compact_outfit_phrase_clusters(preferred_outfit, aggressive=True)
        coherent_outfit = self._coherent_outfit_sentence(
            str(compacted.get("outfit_sentence") or preferred_outfit),
            scene=scene,
            context=context,
            shot_archetype=resolved_shot,
            coherence=coherence,
            apply_in_the_moment=False,
        )
        outfit_text = self._normalize_outfit_sentence_for_prompt(coherent_outfit, scene, context)
        outfit_text = self._clean_fragment(outfit_text.split(";")[0]) or self._contextual_outfit_fallback_sentence(scene, context)

        minimal_environment = self._coherent_environment_seed(scene, context, coherence)
        environment_parts = [self._clean_fragment(part) for part in minimal_environment.split(";") if self._clean_fragment(part)]
        environment_text = ", ".join(environment_parts[:6]) if environment_parts else "photorealistic real environment with accurate perspective and scale"
        mood_text = self._fallback_mood_presence_phrase(scene, context) or "held together without turning it into a pose"
        prompt_blocks = {
            "Identity": f"Identity: {identity_text}.",
            "Framing": framing_block,
            "Scene": f"Scene: {scene_text}.",
            "Outfit": f"Outfit: {outfit_text}.",
            "Environment": f"Environment: {environment_text}.",
            "Mood": f"Mood: {mood_text}.",
        }
        return {
            "prompt": "\n\n".join(
                [
                    prompt_blocks["Identity"],
                    prompt_blocks["Framing"],
                    prompt_blocks["Scene"],
                    prompt_blocks["Outfit"],
                    prompt_blocks["Environment"],
                    prompt_blocks["Mood"],
                ]
            ),
            "prompt_blocks": prompt_blocks,
        }

    @staticmethod
    def _human_join(parts: List[str]) -> str:
        cleaned = [PromptComposer._clean_fragment(part) for part in parts if PromptComposer._clean_fragment(part)]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"

    def _has_duplicate_clauses(self, prompt: str) -> bool:
        return bool(self._find_duplicate_clauses(prompt))

    def _classify_duplicate_clause_entry(self, left: Dict[str, Any], right: Dict[str, Any]) -> str:
        left_tokens = set(left.get("tokens") or set())
        right_tokens = set(right.get("tokens") or set())
        if left.get("key") and left.get("key") == right.get("key") and max(len(left_tokens), len(right_tokens)) >= self.DUPLICATE_BLOCK_FAILURE_TOKEN_THRESHOLD:
            return "fatal"
        if self._is_soft_garment_overlap(left, right):
            return "soft"
        if left_tokens and right_tokens:
            if (left_tokens <= right_tokens or right_tokens <= left_tokens) and max(len(left_tokens), len(right_tokens)) >= self.DUPLICATE_BLOCK_FAILURE_TOKEN_THRESHOLD:
                return "fatal"
            if self._token_overlap_ratio(left_tokens, right_tokens) >= self.DUPLICATE_CLAUSE_FATAL_RATIO:
                return "fatal"
        return "soft"

    def _duplicate_clause_entries(self, prompt: str) -> List[Dict[str, Any]]:
        duplicates: List[Dict[str, Any]] = []
        seen: List[Dict[str, Any]] = []
        for block in [block.strip() for block in str(prompt or "").split("\n\n") if block.strip()]:
            block_name, body = self._split_block_label(block)
            for clause in self._extract_semantic_clauses(block_name, body):
                duplicate_of = next((entry for entry in seen if self._clauses_overlap(clause, entry)), None)
                if duplicate_of is None:
                    seen.append(clause)
                    continue
                duplicates.append(
                    {
                        "severity": self._classify_duplicate_clause_entry(clause, duplicate_of),
                        "message": f"{block_name}:{clause['text']} == {duplicate_of['block']}:{duplicate_of['text']}",
                        "left": clause,
                        "right": duplicate_of,
                    }
                )
        return duplicates

    def _find_duplicate_clauses(self, prompt: str) -> List[str]:
        return [entry["message"] for entry in self._duplicate_clause_entries(prompt)]

    def sanitize_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        step: str = "",
    ) -> Dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        block_names = ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        raw_blocks = [block.strip() for block in normalized_prompt.split("\n\n") if block.strip()]
        if len(raw_blocks) != 6:
            return {
                "prompt": normalized_prompt,
                "duplicate_clauses": [],
                "sanitized_prompt_applied": False,
                "prompt_blocks": {},
                "sanitization_step": step,
            }

        block_map = {name: raw_blocks[idx] for idx, name in enumerate(block_names)}
        diagnostics = {
            "duplicate_clauses": [],
            "sanitized_prompt_applied": False,
            "prompt_blocks": {},
            "sanitization_step": step,
        }

        preferred_outfit = self._clean_fragment(outfit_sentence) or self.extract_outfit_sentence(normalized_prompt)
        try:
            preferred_outfit = self._normalize_outfit_sentence_for_prompt(preferred_outfit, scene, context)
        except PromptValidationError:
            preferred_outfit = self._contextual_outfit_fallback_sentence(scene, context)
        block_map["Outfit"] = f"Outfit: {preferred_outfit}."

        kept_entries: List[Dict[str, Any]] = []
        sanitized_bodies: Dict[str, str] = {}
        priority_order = ["Identity", "Outfit", "Scene", "Environment", "Mood"]
        for name in priority_order:
            label, body = self._split_block_label(block_map[name])
            clauses = self._extract_semantic_clauses(label, body)
            kept_clauses: List[Dict[str, Any]] = []
            for clause in clauses:
                duplicate_of = next((entry for entry in kept_entries if self._clauses_overlap(clause, entry)), None)
                if duplicate_of is not None:
                    severity = self._classify_duplicate_clause_entry(clause, duplicate_of)
                    diagnostics["duplicate_clauses"].append(
                        f"{severity}:{label}:{clause['text']} == {duplicate_of['block']}:{duplicate_of['text']}"
                    )
                    if severity == "fatal":
                        diagnostics["sanitized_prompt_applied"] = True
                        continue
                kept_clauses.append(clause)
                kept_entries.append(clause)
            sanitized_bodies[label] = self._compose_block_body(
                label,
                kept_clauses,
                body,
                scene=scene,
                context=context,
                preferred_outfit=preferred_outfit,
            )

        framing_block = block_map["Framing"]
        diagnostics["prompt_blocks"] = {
            "Identity": f"Identity: {sanitized_bodies['Identity']}.",
            "Framing": framing_block,
            "Scene": f"Scene: {sanitized_bodies['Scene']}.",
            "Outfit": f"Outfit: {sanitized_bodies['Outfit']}.",
            "Environment": f"Environment: {sanitized_bodies['Environment']}.",
            "Mood": f"Mood: {sanitized_bodies['Mood']}.",
        }
        diagnostics["prompt"] = "\n\n".join(
            [
                diagnostics["prompt_blocks"]["Identity"],
                diagnostics["prompt_blocks"]["Framing"],
                diagnostics["prompt_blocks"]["Scene"],
                diagnostics["prompt_blocks"]["Outfit"],
                diagnostics["prompt_blocks"]["Environment"],
                diagnostics["prompt_blocks"]["Mood"],
            ]
        )
        return diagnostics

    @staticmethod
    def _split_block_label(block: str) -> tuple[str, str]:
        if ": " not in block:
            return "Framing", block.strip()
        label, body = block.split(": ", 1)
        return label.strip(), body.strip().rstrip(".")

    @staticmethod
    def _prompt_block_map(prompt: str) -> Dict[str, str]:
        raw_blocks = [block.strip() for block in str(prompt or "").split("\n\n") if block.strip()]
        if len(raw_blocks) != 6:
            return {}
        return {
            "Identity": raw_blocks[0],
            "Framing": raw_blocks[1],
            "Scene": raw_blocks[2],
            "Outfit": raw_blocks[3],
            "Environment": raw_blocks[4],
            "Mood": raw_blocks[5],
        }

    def _extract_semantic_clauses(self, block_name: str, body: str) -> List[Dict[str, Any]]:
        if block_name == "Framing":
            cleaned = self._clean_fragment(body)
            return [{"block": block_name, "text": cleaned, "key": self._normalize_phrase_key(cleaned), "tokens": self._semantic_tokens(cleaned)}] if cleaned else []
        separator = r"\s*,\s*" if block_name in {"Scene", "Mood", "Outfit"} else r"\s*[;,]\s*"
        clauses: List[Dict[str, Any]] = []
        if block_name == "Outfit":
            clothing_text, _, detail_text = body.partition(";")
            parts = [self._clean_fragment(chunk) for chunk in re.split(r"\s*(?:,| and )\s*", clothing_text) if self._clean_fragment(chunk)]
            details = [self._clean_fragment(chunk) for chunk in re.split(r"\s*,\s*", detail_text) if self._clean_fragment(chunk)]
            raw_clauses = parts + details
        else:
            raw_clauses = [self._clean_fragment(chunk) for chunk in re.split(separator, body) if self._clean_fragment(chunk)]
        for clause in raw_clauses:
            clauses.append(
                {
                    "block": block_name,
                    "text": clause,
                    "key": self._normalize_phrase_key(clause),
                    "tokens": self._semantic_tokens(clause),
                }
            )
        return clauses

    def _semantic_tokens(self, text: str) -> set[str]:
        normalized = str(text or "").lower().replace("carry-on", "carry_on").replace("carry on", "carry_on")
        raw_tokens = re.findall(r"[a-z0-9_]+", normalized)
        tokens: set[str] = set()
        for token in raw_tokens:
            if token in self.CLAUSE_STOPWORDS or len(token) <= 2:
                continue
            if token.endswith("s") and len(token) > 4:
                token = token[:-1]
            tokens.add(token)
        return tokens

    @staticmethod
    def _token_overlap_ratio(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        intersection = len(left & right)
        union = len(left | right)
        return intersection / union if union else 0.0

    def _clauses_overlap(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        if {left.get("block"), right.get("block")} == {"Scene", "Environment"}:
            environment_clause = left if left.get("block") == "Environment" else right
            if str(environment_clause.get("text") or "").lower().startswith("photorealistic "):
                return False
        if left["key"] and left["key"] == right["key"]:
            return True
        left_tokens = set(left.get("tokens") or set())
        right_tokens = set(right.get("tokens") or set())
        if not left_tokens or not right_tokens:
            return False
        if self._is_soft_garment_overlap(left, right):
            return self._token_overlap_ratio(left_tokens, right_tokens) >= self.DUPLICATE_CLAUSE_FATAL_RATIO
        overlap = left_tokens & right_tokens
        if len(overlap) < 2:
            return False
        if left_tokens <= right_tokens or right_tokens <= left_tokens:
            return True
        return self._token_overlap_ratio(left_tokens, right_tokens) >= 0.72

    def _compose_block_body(
        self,
        block_name: str,
        clauses: List[Dict[str, Any]],
        original_body: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        preferred_outfit: str,
    ) -> str:
        texts = [self._clean_fragment(clause["text"]) for clause in clauses if self._clean_fragment(clause["text"])]
        if block_name == "Identity":
            return "; ".join(texts) if texts else self._clean_fragment(original_body)
        if block_name == "Outfit":
            if texts:
                clothing: List[str] = []
                details: List[str] = []
                for text in texts:
                    if self._is_outfit_detail_only_clause(text):
                        details.append(text)
                    else:
                        clothing.append(text)
                rebuilt = ", ".join(clothing)
                if details:
                    rebuilt = f"{rebuilt}; {', '.join(details)}" if rebuilt else ", ".join(details)
                try:
                    return self._normalize_outfit_sentence_for_prompt(rebuilt, scene, context)
                except PromptValidationError:
                    pass
            return self._normalize_outfit_sentence_for_prompt(preferred_outfit, scene, context)
        if block_name == "Environment":
            if texts and not any(text.lower().startswith("photorealistic ") for text in texts):
                texts.insert(0, self._minimal_environment_body(scene).split(";")[0].strip())
            if texts:
                return "; ".join(texts)
            return self._minimal_environment_body(scene)
        if block_name == "Mood":
            if texts:
                return ", ".join(texts)
            return "quiet confidence"
        if block_name == "Scene":
            if texts:
                return ", ".join(texts)
            return self._minimal_scene_body(scene)
        return self._clean_fragment(original_body)

    def _split_outfit_scene_props(self, outfit_text: str) -> tuple[List[str], List[str], List[str]]:
        cleaned = self._clean_fragment(outfit_text)
        clothing_text, _, detail_text = cleaned.partition(";")
        clothing_chunks = [self._clean_fragment(chunk) for chunk in re.split(r"\s*(?:,| and )\s*", clothing_text) if self._clean_fragment(chunk)]
        detail_chunks = [self._clean_fragment(chunk) for chunk in re.split(r"\s*,\s*", detail_text) if self._clean_fragment(chunk)]
        clothing: List[str] = []
        props: List[str] = []
        for chunk in clothing_chunks:
            if self._is_scene_prop_phrase(chunk):
                props.append(self._canonical_scene_prop_phrase(chunk))
            else:
                clothing.append(chunk)
        return self._dedupe_phrases(clothing), self._dedupe_phrases(detail_chunks), self._dedupe_phrases(props)

    def _extract_scene_props_from_outfit_text(self, outfit_text: str) -> List[str]:
        return self._split_outfit_scene_props(outfit_text)[2]

    def _is_scene_prop_phrase(self, text: str) -> bool:
        lowered = self._clean_fragment(text).lower()
        if not lowered:
            return False
        if "bag" in lowered and not any(
            token in lowered for token in ["carry on", "carry-on", "roller bag", "suitcase", "luggage", "overnight bag"]
        ):
            return False
        return any(token in lowered for token in self.SCENE_PROP_TOKENS)

    def _canonical_scene_prop_phrase(self, text: str) -> str:
        lowered = self._clean_fragment(text).lower()
        if any(token in lowered for token in ["carry on", "carry-on", "suitcase", "luggage", "roller bag"]):
            return "carry on"
        if any(token in lowered for token in ["coffee cup", "cup", "mug"]):
            return "coffee cup"
        if "overnight bag" in lowered:
            return "bag"
        if "boarding pass" in lowered:
            return "boarding pass"
        if "passport" in lowered:
            return "passport"
        if "laptop" in lowered:
            return "laptop"
        return self._clean_fragment(text)

    @classmethod
    def _has_invalid_plural_article(cls, text: str) -> bool:
        lowered = cls._clean_fragment(text).lower()
        if not lowered:
            return False
        plural_pattern = "|".join(re.escape(token) for token in cls.OUTFIT_PLURAL_NOUNS)
        return bool(
            re.search(
                rf"\b(?:a|an)\s+(?:[a-z-]+\s+){{0,4}}(?:{plural_pattern})\b",
                lowered,
            )
        )

    @classmethod
    def _strip_invalid_outfit_article(cls, text: str) -> str:
        cleaned = cls._clean_fragment(text)
        if not cleaned:
            return ""
        plural_pattern = "|".join(re.escape(token) for token in cls.OUTFIT_PLURAL_NOUNS)
        cleaned = re.sub(
            rf"^(?:a|an)\s+(?=(?:[a-z-]+\s+){{0,4}}(?:{plural_pattern})\b)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        return cls._clean_fragment(cleaned)

    def _garment_anchor_token(self, text: str) -> str:
        lowered = self._clean_fragment(text).lower()
        best = ""
        for tokens in self.GARMENT_CATEGORY_TOKENS.values():
            for token in tokens:
                if re.search(rf"\b{re.escape(token)}\b", lowered) and len(token) > len(best):
                    best = token
        return best

    def _same_garment_anchor(self, left: str, right: str) -> bool:
        left_clean = self._clean_fragment(left)
        right_clean = self._clean_fragment(right)
        if not left_clean or not right_clean:
            return False
        if self._outfit_category(left_clean) != self._outfit_category(right_clean):
            return False
        left_anchor = self._garment_anchor_token(left_clean)
        right_anchor = self._garment_anchor_token(right_clean)
        if left_anchor and right_anchor and left_anchor == right_anchor:
            return True
        return self._token_overlap_ratio(self._semantic_tokens(left_clean), self._semantic_tokens(right_clean)) >= 0.72

    def _prefer_outfit_phrase(self, left: str, right: str) -> str:
        if self._same_garment_anchor(left, right) and self._outfit_category(left) == "shoes":
            left_worn = "worn in" in left.lower()
            right_worn = "worn in" in right.lower()
            if left_worn != right_worn:
                return left if left_worn else right

        def _score(text: str) -> tuple[int, int, int]:
            lowered = self._clean_fragment(text).lower()
            tokens = re.findall(r"[a-z-]+", lowered)
            modifiers = sum(
                1
                for token in [
                    "relaxed",
                    "straight",
                    "soft",
                    "light",
                    "comfortable",
                    "fitted",
                    "tailored",
                    "structured",
                    "compact",
                    "small",
                    "everyday",
                    "breathable",
                    "knit",
                    "linen",
                    "crossbody",
                    "white",
                    "leather",
                ]
                if token in lowered
            )
            relation_penalty = int(bool(re.search(r"\b(with|that|worn|left|looking|falling|moving|kept)\b", lowered)))
            grammar_bonus = 0 if self._has_invalid_plural_article(lowered) else 2
            return (grammar_bonus + modifiers + min(len(tokens), 6) - relation_penalty, -len(tokens), -len(lowered))

        return left if _score(left) >= _score(right) else right

    def _normalize_outfit_clothing_items(self, clothing: List[str]) -> List[str]:
        normalized: List[str] = []
        for item in self._dedupe_phrases(clothing):
            cleaned = self._strip_invalid_outfit_article(self._repair_duplicate_sequences_in_text(item, aggressive=True))
            if not cleaned:
                continue
            overlap_index = next((idx for idx, existing in enumerate(normalized) if self._same_garment_anchor(existing, cleaned)), None)
            if overlap_index is None:
                normalized.append(cleaned)
                continue
            normalized[overlap_index] = self._prefer_outfit_phrase(normalized[overlap_index], cleaned)
        return self._dedupe_phrases(normalized)

    def _compact_outfit_item_phrase(self, text: str, *, aggressive: bool) -> str:
        cleaned = self._clean_fragment(text)
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        category = self._outfit_category(cleaned)
        for token in self.GARMENT_CATEGORY_TOKENS.get(category, ()):
            if token in lowered:
                token_index = lowered.find(token)
                if token_index >= 0:
                    compact = cleaned[: token_index + len(token)].strip(" ,;:.")
                    if compact:
                        return compact
        if aggressive:
            compact = re.split(
                r"\b(?:that|with|worn|following|moving|kept|left|looking|falling)\b",
                cleaned,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip(" ,;:.")
            if compact:
                return compact
        return cleaned

    def _compact_outfit_details(self, details: List[str], *, aggressive: bool) -> tuple[List[str], int]:
        canonical_by_family = {
            "fit_line": "easy movement through the fit",
            "effortless_styling": "styled in an unforced way",
            "fabric_texture": "matte everyday fabric",
            "lived_in_wear": "worn in",
        }
        kept: List[str] = []
        seen_families: set[str] = set()
        removed_count = 0
        for detail in self._dedupe_phrases(details):
            cleaned = self._clean_fragment(detail)
            if not cleaned:
                continue
            family = self._garment_phrase_family(cleaned)
            if family:
                if family in seen_families:
                    removed_count += 1
                    continue
                seen_families.add(family)
                if aggressive:
                    kept.append(canonical_by_family.get(family, cleaned))
                else:
                    kept.append(cleaned)
                continue
            kept.append(cleaned)
        return self._dedupe_phrases(kept), removed_count

    def _compact_outfit_phrase_clusters(
        self,
        outfit_sentence: str,
        *,
        aggressive: bool,
    ) -> Dict[str, Any]:
        clothing, details, _props = self._split_outfit_scene_props(outfit_sentence)
        compacted_clothing: List[str] = []
        removed_count = 0
        for item in clothing:
            if self._is_outfit_detail_only_clause(item):
                details.append(item)
                removed_count += 1
                continue
            compacted = self._compact_outfit_item_phrase(item, aggressive=aggressive)
            if compacted != self._clean_fragment(item):
                removed_count += 1
            compacted_clothing.append(compacted or self._clean_fragment(item))
        compacted_details, detail_removed = self._compact_outfit_details(details, aggressive=aggressive)
        removed_count += detail_removed
        prompt_text = ", ".join(self._dedupe_phrases(compacted_clothing))
        if compacted_details:
            prompt_text = f"{prompt_text}; {', '.join(self._dedupe_phrases(compacted_details))}" if prompt_text else ", ".join(compacted_details)
        return {
            "outfit_sentence": self._clean_fragment(prompt_text),
            "garment_phrase_compaction_applied": removed_count > 0,
            "softened_duplicate_sequences_count": removed_count,
        }

    def _normalize_outfit_sentence_for_prompt(self, outfit_sentence: str, scene: Any | None = None, context: Dict[str, Any] | None = None) -> str:
        cleaned = self._clean_fragment(outfit_sentence)
        if cleaned and not self._is_invalid_outfit_value(cleaned):
            compacted = self._compact_outfit_phrase_clusters(cleaned, aggressive=False)
            cleaned = self._clean_fragment(str(compacted.get("outfit_sentence") or cleaned))
            clothing, details, _ = self._split_outfit_scene_props(cleaned)
            clothing = self._normalize_outfit_clothing_items(clothing)
            details, _ = self._compact_outfit_details(details, aggressive=False)
            rebuilt = ", ".join(clothing)
            if "sneakers" in rebuilt.lower() and "worn in" not in rebuilt.lower():
                rebuilt = re.sub(r"\bcomfortable sneakers\b", "comfortable sneakers worn in", rebuilt, flags=re.IGNORECASE)
            if details:
                rebuilt = f"{rebuilt}; {', '.join(self._dedupe_phrases(details))}" if rebuilt else ", ".join(self._dedupe_phrases(details))
            try:
                return self.validate_outfit_sentence(rebuilt)
            except PromptValidationError:
                pass
        if scene is not None and context is not None:
            fallback = self._contextual_outfit_fallback_sentence(scene, context)
            return self.validate_outfit_sentence(fallback)
        return self.validate_outfit_sentence(cleaned)

    def _outfit_item_allowed_for_place(
        self,
        item: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        coherence: PlaceCoherenceState,
    ) -> bool:
        lowered = self._clean_fragment(item).lower()
        if not lowered:
            return False
        if any(token in lowered for token in ["carry on", "carry-on", "coffee cup", "coffee", "mug", "boarding pass", "passport"]):
            return False
        if "overnight bag" in lowered:
            return False
        if "bag" in lowered and not coherence.allow_wearable_bag:
            return False
        if "bag" in lowered and not self._bag_is_legitimate(context, scene, coherence):
            return False
        return True

    def _coherent_outfit_sentence(
        self,
        outfit_sentence: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        shot_archetype: str,
        coherence: PlaceCoherenceState,
        apply_in_the_moment: bool,
    ) -> str:
        cleaned = self._clean_fragment(outfit_sentence)
        clothing, details, _ = self._split_outfit_scene_props(cleaned)
        kept_clothing = [
            item
            for item in clothing
            if self._outfit_item_allowed_for_place(item, scene=scene, context=context, coherence=coherence)
        ]
        if len(self.outfit_semantic_units(", ".join(kept_clothing))) < 3:
            fallback_sentence = self._contextual_outfit_fallback_sentence(scene, context)
            fallback_clothing, fallback_details, _ = self._split_outfit_scene_props(fallback_sentence)
            kept_clothing = [
                item
                for item in fallback_clothing
                if self._outfit_item_allowed_for_place(item, scene=scene, context=context, coherence=coherence)
            ]
            details = fallback_details
        rebuilt = ", ".join(self._dedupe_phrases(kept_clothing))
        if details:
            rebuilt = f"{rebuilt}; {', '.join(self._dedupe_phrases(details))}" if rebuilt else ", ".join(self._dedupe_phrases(details))
        normalized = self._normalize_outfit_sentence_for_prompt(rebuilt, scene, context)
        if not apply_in_the_moment:
            return normalized
        return self.validate_outfit_sentence(
            self._in_the_moment_outfit_body(
                normalized,
                scene=scene,
                context=context,
                shot_archetype=shot_archetype,
            )
        )

    def _soft_simplify_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        aggressive: bool,
    ) -> Dict[str, Any]:
        block_map = self._prompt_block_map(prompt)
        if not block_map:
            return {
                "prompt": str(prompt or "").strip(),
                "prompt_blocks": {},
                "changed": False,
                "garment_phrase_compaction_applied": False,
                "softened_duplicate_sequences_count": 0,
            }

        updated_blocks = dict(block_map)
        preferred_outfit = self._split_block_label(updated_blocks["Outfit"])[1] or self._clean_fragment(outfit_sentence)
        compacted_outfit = self._compact_outfit_phrase_clusters(preferred_outfit, aggressive=aggressive)
        try:
            outfit_body = self._normalize_outfit_sentence_for_prompt(
                str(compacted_outfit.get("outfit_sentence") or preferred_outfit),
                scene,
                context,
            )
        except PromptValidationError:
            outfit_body = self._contextual_outfit_fallback_sentence(scene, context)
        if aggressive and ";" in outfit_body:
            head, _, tail = outfit_body.partition(";")
            detail = self._grounded_outfit_detail_phrase(
                [chunk for chunk in re.split(r"\s*,\s*", tail) if self._clean_fragment(chunk)]
            )
            if not detail:
                detail = self._clean_fragment(tail.split(",", 1)[0])
            if detail:
                outfit_body = f"{self._clean_fragment(head)}, {detail}"
            else:
                outfit_body = self._clean_fragment(head) or outfit_body
        if aggressive and "sneakers" in outfit_body.lower() and "worn in" not in outfit_body.lower():
            outfit_body = re.sub(r"\bcomfortable sneakers\b", "comfortable sneakers worn in", outfit_body, flags=re.IGNORECASE)
        updated_blocks["Outfit"] = f"Outfit: {outfit_body}."

        scene_clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", self._split_block_label(updated_blocks["Scene"])[1])]
        if scene_clauses:
            limit = 6 if aggressive else 4
            updated_blocks["Scene"] = f"Scene: {', '.join(self._prioritized_scene_clauses(scene_clauses, context, limit))}."

        environment_clauses = self._dedupe_phrases(
            [clause["text"] for clause in self._extract_semantic_clauses("Environment", self._split_block_label(updated_blocks["Environment"])[1])]
        )
        if environment_clauses:
            limit = 6 if aggressive else 4
            separator = ", " if aggressive else "; "
            updated_blocks["Environment"] = f"Environment: {separator.join(environment_clauses[:limit])}."

        mood_clauses = self._dedupe_phrases(
            [clause["text"] for clause in self._extract_semantic_clauses("Mood", self._split_block_label(updated_blocks["Mood"])[1])]
        )
        if mood_clauses:
            selected_mood = mood_clauses[:2]
            already_happening = next(
                (clause for clause in mood_clauses if "already happening by the time the camera catches it" in clause.lower()),
                "",
            )
            transitional_clause = next(
                (clause for clause in mood_clauses if "like she is between one thing and the next" in clause.lower()),
                "",
            )
            if transitional_clause:
                selected_mood = self._dedupe_phrases([transitional_clause] + selected_mood)
            if already_happening and already_happening not in selected_mood:
                selected_mood = self._dedupe_phrases(selected_mood[:1] + [already_happening])
            updated_blocks["Mood"] = f"Mood: {', '.join(selected_mood)}."

        updated_prompt = "\n\n".join(
            updated_blocks[name]
            for name in ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        )
        return {
            "prompt": updated_prompt,
            "prompt_blocks": updated_blocks,
            "changed": updated_prompt.strip() != str(prompt or "").strip(),
            "garment_phrase_compaction_applied": bool(compacted_outfit.get("garment_phrase_compaction_applied")),
            "softened_duplicate_sequences_count": int(compacted_outfit.get("softened_duplicate_sequences_count") or 0),
        }

    @staticmethod
    def _is_outfit_detail_only_clause(text: str) -> bool:
        lowered = str(text or "").lower()
        clothing_tokens = (
            "dress",
            "jeans",
            "trousers",
            "pants",
            "skirt",
            "shorts",
            "denim",
            "sneakers",
            "boots",
            "loafers",
            "sandals",
            "slides",
            "shoes",
            "trainers",
            "coat",
            "jacket",
            "cardigan",
            "blazer",
            "hoodie",
            "trench",
            "top",
            "blouse",
            "shirt",
            "sweater",
            "knit",
            "tank",
            "tee",
            "bag",
        )
        has_clothing = any(token in lowered for token in clothing_tokens)
        has_detail = any(token in lowered for token in PromptComposer.OUTFIT_DETAIL_KEYWORDS)
        return has_detail and not has_clothing

    @staticmethod
    def _outfit_validation_status_for_reason(reason: str) -> str:
        lowered = str(reason or "").strip().lower()
        if not lowered:
            return "recoverable"
        fatal_markers = (
            "empty",
            "english only",
            "contain english clothing text",
            "actual clothing pieces",
            "placeholder",
        )
        if any(marker in lowered for marker in fatal_markers):
            return "fatal"
        return "recoverable"

    def _build_structured_outfit_sentence(
        self,
        outfit_struct: Mapping[str, Any] | None,
        *,
        scene: Any,
        context: Dict[str, Any],
        coherence: PlaceCoherenceState | None = None,
    ) -> str:
        struct = self._coerce_outfit_struct(outfit_struct)
        if not struct:
            return ""

        fallback_struct = self._outfit_struct_from_sentence(
            self._safe_fallback_outfit_sentence(scene, context, coherence=coherence)
        )
        coherence = coherence or self._resolve_place_coherence(context, scene)

        top = self._clean_fragment(str(struct.get("top") or fallback_struct.get("top") or ""))
        bottom = self._clean_fragment(str(struct.get("bottom") or fallback_struct.get("bottom") or ""))
        outerwear = self._clean_fragment(str(struct.get("outerwear") or fallback_struct.get("outerwear") or ""))
        shoes = self._clean_fragment(str(struct.get("shoes") or fallback_struct.get("shoes") or ""))
        accessories = self._clean_fragment(str(struct.get("accessories") or fallback_struct.get("accessories") or ""))

        clothing = [piece for piece in [top, bottom, outerwear, shoes] if piece]
        if accessories and self._outfit_item_allowed_for_place(accessories, scene=scene, context=context, coherence=coherence):
            clothing.append(accessories)
        clothing = self._normalize_outfit_clothing_items(clothing)

        details = self._dedupe_phrases(
            [
                self._clean_fragment(str(struct.get("fit") or fallback_struct.get("fit") or "")),
                self._clean_fragment(str(struct.get("fabric") or fallback_struct.get("fabric") or "")),
                self._clean_fragment(str(struct.get("condition") or fallback_struct.get("condition") or "")),
                self._clean_fragment(str(struct.get("styling") or fallback_struct.get("styling") or "")),
            ]
        )
        detail_phrase = self._grounded_outfit_detail_phrase(details)
        rebuilt = ", ".join(clothing)
        if detail_phrase:
            rebuilt = f"{rebuilt}; {detail_phrase}" if rebuilt else detail_phrase
        return self._clean_fragment(rebuilt)

    def _safe_fallback_outfit_sentence(
        self,
        scene: Any,
        context: Dict[str, Any],
        *,
        coherence: PlaceCoherenceState | None = None,
    ) -> str:
        lowered = self._scene_text(scene).lower()
        behavior = context.get("behavioral_context")
        place_anchor = str(
            getattr(behavior, "place_anchor", "")
            or getattr(behavior, "familiar_place_anchor", "")
            or ""
        ).lower()
        social_presence = str(
            getattr(behavior, "social_mode", "")
            or getattr(behavior, "social_presence_mode", "")
            or getattr(getattr(behavior, "daily_state", None), "social_presence_mode", "")
            or ""
        ).lower()
        day_type = self._context_day_type(context)
        time_of_day = str(getattr(scene, "time_of_day", "") or "").lower()
        coherence = coherence or self._resolve_place_coherence(context, scene)

        allow_bag = coherence.allow_wearable_bag and self._bag_is_legitimate(context, scene, coherence)
        everyday_bag = ", and a small everyday bag" if allow_bag else ""

        if any(token in lowered for token in ["airport", "terminal", "gate", "boarding"]) or place_anchor == "terminal_gate":
            seated = any(token in lowered for token in ["waiting", "seated", "window", "chair", "table"]) or "waiting" in str(getattr(scene, "scene_moment_type", "") or "").lower()
            if seated or day_type == "work_day":
                return (
                    "soft knit layer, straight trousers, comfortable sneakers"
                    f"{everyday_bag}; practical travel-ready fit with natural fabric folds"
                )
            return (
                "light knit top, light jacket, practical straight trousers, comfortable sneakers"
                f"{everyday_bag}; travel-ready fit with soft layers and natural fabric folds"
            )

        if (
            any(token in lowered for token in ["kitchen", "home", "living room", "hotel"])
            or place_anchor in {"kitchen_corner", "hotel_window"}
        ):
            indoor_shoes = "comfortable indoor shoes" if any(token in lowered for token in ["home", "kitchen", "living room"]) else "comfortable flat shoes"
            light_layer = "light cardigan" if time_of_day in {"morning", "evening", "night"} or "hotel" in lowered else "soft overshirt"
            return (
                f"soft casual knit top, relaxed straight trousers, {indoor_shoes}, and a {light_layer}; "
                "easy indoor fit with natural fabric texture"
            )

        if any(token in lowered for token in ["cafe", "street", "sidewalk", "city", "urban"]):
            outer_layer = "light jacket" if "street" in lowered or social_presence in {"light_public", "social", "alone_but_in_public"} else "soft layer"
            return (
                f"soft everyday top, straight jeans, comfortable sneakers, and a {outer_layer}; "
                "casual urban fit with easy layering"
            )

        return (
            "soft knit top, straight trousers, comfortable sneakers"
            f"{everyday_bag}; practical fit with natural fabric folds"
        )

    def recover_outfit_sentence(
        self,
        outfit_sentence: str,
        *,
        scene: Any,
        context: Dict[str, Any],
        outfit_struct: Mapping[str, Any] | None = None,
        shot_archetype: str = "",
        apply_in_the_moment: bool = False,
    ) -> Dict[str, Any]:
        struct = self._coerce_outfit_struct(outfit_struct)
        cleaned = self._clean_fragment(outfit_sentence)
        coherence = self._resolve_place_coherence(context, scene, outfit_body=cleaned)
        diagnostics: Dict[str, Any] = {
            "sentence": "",
            "outfit_validation_status": "fatal",
            "outfit_repair_applied": False,
            "outfit_fallback_used": False,
            "outfit_fallback_reason": "",
            "outfit_recovery_source": "primary",
            "primary_validation_error": "",
            "user_facing_prompt_placeholder_used": False,
        }

        def _finalize(candidate: str, *, status: str, source: str, repair: bool, fallback: bool, reason: str = "") -> Dict[str, Any]:
            normalized = self.validate_outfit_sentence(candidate)
            if apply_in_the_moment:
                normalized = self.validate_outfit_sentence(
                    self._in_the_moment_outfit_body(
                        normalized,
                        scene=scene,
                        context=context,
                        shot_archetype=shot_archetype,
                    )
                )
            diagnostics.update(
                {
                    "sentence": normalized,
                    "outfit_validation_status": status,
                    "outfit_repair_applied": repair,
                    "outfit_fallback_used": fallback,
                    "outfit_fallback_reason": reason,
                    "outfit_recovery_source": source,
                }
            )
            return diagnostics

        if cleaned:
            try:
                primary = self.validate_outfit_sentence(cleaned, outfit_struct=struct)
                coherent_primary = self._coherent_outfit_sentence(
                    primary,
                    scene=scene,
                    context=context,
                    shot_archetype=shot_archetype,
                    coherence=coherence,
                    apply_in_the_moment=apply_in_the_moment,
                )
                if coherent_primary == primary:
                    return _finalize(primary, status="passed", source="primary", repair=False, fallback=False)
                return _finalize(coherent_primary, status="recoverable", source="repaired", repair=True, fallback=False)
            except PromptValidationError as exc:
                diagnostics["primary_validation_error"] = str(exc)
                diagnostics["outfit_validation_status"] = self._outfit_validation_status_for_reason(str(exc))

        repair_candidate = ""
        if cleaned:
            compacted = self._compact_outfit_phrase_clusters(cleaned, aggressive=False)
            compacted_sentence = self._clean_fragment(str(compacted.get("outfit_sentence") or cleaned))
            clothing, details, _props = self._split_outfit_scene_props(compacted_sentence)
            clothing = self._normalize_outfit_clothing_items(clothing)
            details, _ = self._compact_outfit_details(details, aggressive=False)
            repair_candidate = ", ".join(clothing)
            if details:
                repair_candidate = f"{repair_candidate}; {', '.join(self._dedupe_phrases(details))}" if repair_candidate else ", ".join(self._dedupe_phrases(details))

        for candidate in [repair_candidate, self._build_structured_outfit_sentence(struct, scene=scene, context=context, coherence=coherence)]:
            normalized_candidate = self._clean_fragment(candidate)
            if not normalized_candidate:
                continue
            try:
                coherent_candidate = self._coherent_outfit_sentence(
                    normalized_candidate,
                    scene=scene,
                    context=context,
                    shot_archetype=shot_archetype,
                    coherence=coherence,
                    apply_in_the_moment=apply_in_the_moment,
                )
                return _finalize(
                    coherent_candidate,
                    status="recoverable",
                    source="repaired",
                    repair=True,
                    fallback=False,
                )
            except PromptValidationError:
                continue

        fallback_reason = diagnostics["primary_validation_error"] or "repair_failed"
        for candidate in [
            self._safe_fallback_outfit_sentence(scene, context, coherence=coherence),
            "soft knit top, straight trousers, comfortable sneakers; practical fit with natural fabric folds",
        ]:
            normalized_candidate = self._clean_fragment(candidate)
            if not normalized_candidate:
                continue
            try:
                return _finalize(
                    normalized_candidate,
                    status="degraded",
                    source="fallback",
                    repair=True,
                    fallback=True,
                    reason=fallback_reason,
                )
            except PromptValidationError:
                continue

        diagnostics["outfit_fallback_used"] = True
        diagnostics["outfit_fallback_reason"] = fallback_reason or "critical_outfit_failure"
        return diagnostics

    def recover_prompt_outfit_block(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        outfit_struct: Mapping[str, Any] | None = None,
        shot_archetype: str = "",
        apply_in_the_moment: bool = True,
    ) -> Dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        prompt_blocks = self._prompt_block_map(normalized_prompt)
        diagnostics: Dict[str, Any] = {
            "prompt": normalized_prompt,
            "prompt_blocks": prompt_blocks,
            "changed": False,
            "outfit_sentence": self.extract_outfit_sentence(normalized_prompt),
            "outfit_validation_status": "fatal" if normalized_prompt else "pending",
            "outfit_repair_applied": False,
            "outfit_fallback_used": False,
            "outfit_fallback_reason": "",
            "outfit_recovery_source": "primary",
            "user_facing_prompt_placeholder_used": False,
        }
        if not prompt_blocks:
            return diagnostics

        current_outfit = self._split_block_label(prompt_blocks["Outfit"])[1] or self._clean_fragment(outfit_sentence)
        recovered_outfit = self.recover_outfit_sentence(
            current_outfit,
            scene=scene,
            context=context,
            outfit_struct=outfit_struct,
            shot_archetype=shot_archetype,
            apply_in_the_moment=False,
        )
        resolved_outfit = self._clean_fragment(str(recovered_outfit.get("sentence") or current_outfit or outfit_sentence))
        if not resolved_outfit:
            return diagnostics

        updated_blocks = dict(prompt_blocks)
        updated_blocks["Outfit"] = f"Outfit: {resolved_outfit}."
        updated_prompt = "\n\n".join(
            [
                updated_blocks["Identity"],
                updated_blocks["Framing"],
                updated_blocks["Scene"],
                updated_blocks["Outfit"],
                updated_blocks["Environment"],
                updated_blocks["Mood"],
            ]
        )
        coherent = self._apply_place_coherence_to_prompt(
            updated_prompt,
            scene,
            context,
            outfit_sentence=resolved_outfit,
            shot_archetype=shot_archetype,
            apply_in_the_moment=apply_in_the_moment,
        )
        final_prompt = str(coherent.get("prompt") or updated_prompt).strip()
        final_outfit = self.extract_outfit_sentence(final_prompt) or resolved_outfit

        diagnostics.update(
            {
                "prompt": final_prompt,
                "prompt_blocks": dict(coherent.get("prompt_blocks") or self._prompt_block_map(final_prompt) or updated_blocks),
                "changed": final_prompt != normalized_prompt or bool(recovered_outfit.get("outfit_repair_applied")),
                "outfit_sentence": final_outfit,
                "outfit_validation_status": str(recovered_outfit.get("outfit_validation_status") or "recoverable"),
                "outfit_repair_applied": bool(recovered_outfit.get("outfit_repair_applied")),
                "outfit_fallback_used": bool(recovered_outfit.get("outfit_fallback_used")),
                "outfit_fallback_reason": str(recovered_outfit.get("outfit_fallback_reason") or ""),
                "outfit_recovery_source": str(recovered_outfit.get("outfit_recovery_source") or "primary"),
                "user_facing_prompt_placeholder_used": False,
            }
        )
        return diagnostics

    def _contextual_outfit_fallback_sentence(self, scene: Any, context: Dict[str, Any]) -> str:
        lowered = self._scene_text(scene).lower()
        style_intensity = str(context.get("style_intensity") or "").lower()
        outfit_style = str(context.get("outfit_style") or "").lower()
        bold_evening_hotel = (
            ("bold" in style_intensity or "bold" in outfit_style)
            and "hotel" in lowered
            and str(getattr(scene, "time_of_day", "") or "").lower() in {"evening", "night"}
        )
        if bold_evening_hotel:
            return (
                "fitted knit dress, light cardigan, and comfortable flat slides; "
                "soft body lines with natural drape"
            )
        return self._safe_fallback_outfit_sentence(scene, context)

    def _minimal_scene_body(self, scene: Any) -> str:
        scene_moment = self._clean_fragment(str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or "daily moment"))
        location = self._scene_location_fallback(scene)
        if location.lower() in scene_moment.lower():
            return scene_moment
        return f"{scene_moment} at {location}"

    def _minimal_environment_body(self, scene: Any) -> str:
        location = self._scene_location_fallback(scene)
        lighting = self._lighting_hint(getattr(scene, "time_of_day", "day"))
        if "airport" in location:
            return f"photorealistic {location}; real terminal architecture; accurate perspective and scale; {lighting} behaving as natural available light"
        return f"photorealistic {location}; lived-in environmental detail; accurate perspective and scale; {lighting} behaving as natural available light"

    def _normalize_outfit_summary(self, outfit_summary: str, scene: Any, context: Dict[str, Any]) -> str:
        city = str(context.get("city", "") or "")
        weather = context.get("weather")
        day_type = str(context.get("day_type", "") or "")
        behavior = context.get("behavioral_context")
        behavior_mode = str(
            getattr(behavior, "outfit_behavior_mode", "")
            or getattr(behavior, "self_presentation", "")
            or getattr(getattr(behavior, "daily_state", None), "self_presentation_mode", "")
            or ""
        )
        try:
            bundle = self.outfit_generator.generate_bundle(outfit_summary=outfit_summary, scene=scene, context=context)
            return bundle.outfit_sentence or bundle.sentence
        except ManualOutfitValidationError as exc:
            raise PromptValidationError(str(exc)) from exc
        except OutfitGenerationError:
            default_items = self.generate_default_outfit(
                scene,
                city,
                weather,
                day_type=day_type,
                behavior_mode=behavior_mode,
            )
            return ", ".join(default_items)

    def generate_default_outfit(
        self,
        scene: Any,
        city: str,
        weather: Any,
        *,
        day_type: str = "",
        behavior_mode: str = "",
    ) -> List[str]:
        del city
        temp_c = getattr(weather, "temp_c", None)
        lowered = self._scene_text(scene).lower()
        lowered_day_type = str(day_type or "").lower()
        lowered_behavior_mode = str(behavior_mode or "").lower().replace("-", "_")
        is_travel = lowered_day_type == "travel_day" or any(token in lowered for token in ["airport", "terminal", "flight", "boarding", "travel"])
        is_work = lowered_day_type == "work_day" or any(token in lowered_behavior_mode for token in ["work", "uniform", "structured"])
        is_day_off = lowered_day_type in {"day_off", "weekend_day", "layover_day"}
        is_evening = str(getattr(scene, "time_of_day", "") or "").lower() in {"evening", "night"}
        if temp_c is None:
            temp_c = 18

        if is_travel:
            if temp_c <= 8:
                outfit = ["soft travel sweater", "straight trousers", "leather ankle boots"]
            elif temp_c <= 18:
                outfit = ["light knit top", "straight jeans", "white sneakers"]
            else:
                outfit = ["breathable travel top", "relaxed straight trousers", "white sneakers"]
        elif is_work:
            if temp_c <= 8:
                outfit = ["fine-knit top", "tailored trousers", "leather ankle boots"]
            elif temp_c <= 18:
                outfit = ["clean knit top", "tailored trousers", "sleek loafers"]
            else:
                outfit = ["light blouse", "tailored trousers", "sleek loafers"]
        elif is_day_off:
            if temp_c <= 8:
                outfit = ["soft wool sweater", "straight jeans", "leather ankle boots"]
            elif temp_c <= 18:
                outfit = ["soft knit top", "straight jeans", "white sneakers"]
            else:
                outfit = ["easy tank top", "linen trousers", "low-profile sandals"]
        elif temp_c <= 8:
            outfit = ["wool coat", "straight trousers", "leather ankle boots"]
        elif temp_c <= 18:
            outfit = ["light knit top", "straight jeans", "white sneakers"]
        else:
            outfit = ["sleeveless top", "linen trousers", "low-profile sandals"]

        if is_travel or "travel" in lowered_behavior_mode:
            accessory = "crossbody bag"
        elif is_work:
            accessory = "structured shoulder bag"
        elif is_evening:
            accessory = "simple shoulder bag"
        else:
            accessory = "minimal tote bag"
        return outfit + [accessory]

    def _is_invalid_outfit_value(self, text: str) -> bool:
        cleaned = self._clean_fragment(text).lower()
        if not cleaned:
            return True
        if cleaned in self.INVALID_OUTFIT_TOKENS:
            return True
        if re.fullmatch(r"[.\-_/]+", cleaned):
            return True
        if all(char in ".-_/" for char in cleaned):
            return True
        return False

    @classmethod
    def outfit_semantic_units(cls, outfit_sentence: str, outfit_struct: Mapping[str, Any] | None = None) -> set[str]:
        lowered = " ".join(str(outfit_sentence or "").lower().split())
        struct = dict(outfit_struct or {})
        units: set[str] = set()

        if any(struct.get(key) for key in ("top",)) or any(token in lowered for token in ["top", "blouse", "shirt", "sweater", "knit", "tank", "tee", "camisole"]):
            units.add("top")
        if any(struct.get(key) for key in ("outerwear",)) or any(token in lowered for token in ["coat", "jacket", "cardigan", "blazer", "hoodie", "trench", "layer"]):
            units.add("layer")
        if any(struct.get(key) for key in ("bottom",)) or any(token in lowered for token in ["jeans", "trousers", "pants", "skirt", "shorts", "denim", "joggers", "leggings"]):
            units.add("bottom_or_dress")
        if any(token in lowered for token in ["dress"]) and not any(struct.get(key) for key in ("bottom",)):
            units.add("bottom_or_dress")
        if any(struct.get(key) for key in ("shoes",)) or any(token in lowered for token in ["sneakers", "boots", "loafers", "sandals", "slides", "heels", "shoes", "trainers"]):
            units.add("shoes")
        if any(struct.get(key) for key in ("accessories",)) or any(token in lowered for token in ["bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "belt"]):
            units.add("accessory")
        if any(struct.get(key) for key in ("fit", "fabric", "condition", "styling")) or any(token in lowered for token in cls.OUTFIT_DETAIL_KEYWORDS):
            units.add("detail")
        return units

    @classmethod
    def validate_outfit_sentence(cls, outfit_sentence: str, outfit_struct: Mapping[str, Any] | None = None) -> str:
        cleaned = " ".join(str(outfit_sentence or "").replace("_", " ").split()).strip(" ,;:")
        lowered = cleaned.lower()
        if not cleaned:
            raise PromptValidationError("Outfit block is empty")
        if cls.CYRILLIC_RE.search(cleaned):
            raise PromptValidationError("Outfit block must be English only")
        if lowered in cls.INVALID_OUTFIT_TOKENS or re.fullmatch(r"[.\-_/]+", lowered or ""):
            raise PromptValidationError("Outfit block is empty")
        if lowered in {".", "..", "...", "{}", "[]"}:
            raise PromptValidationError("Outfit block is empty")
        if lowered in {"none", "null"}:
            raise PromptValidationError("Outfit block is empty")
        if not re.search(r"[A-Za-z]", cleaned):
            raise PromptValidationError("Outfit block must contain English clothing text")
        if cls._has_invalid_plural_article(cleaned):
            raise PromptValidationError("Outfit block contains invalid article for plural garment")

        units = cls.outfit_semantic_units(cleaned, outfit_struct=outfit_struct)
        if len(units) < 3:
            raise PromptValidationError("Outfit block must contain at least three meaningful clothing units")
        if "shoes" not in units:
            raise PromptValidationError("Outfit block must include shoes")
        if "bottom_or_dress" not in units and "top" not in units:
            raise PromptValidationError("Outfit block must describe actual clothing pieces")
        return cleaned.rstrip(".")

    @classmethod
    def extract_outfit_sentence(cls, prompt: str) -> str:
        blocks = [block.strip() for block in str(prompt or "").split("\n\n") if block.strip()]
        if len(blocks) < 4 or not blocks[3].startswith("Outfit: "):
            return ""
        return blocks[3].replace("Outfit: ", "", 1).strip().rstrip(".")

    @classmethod
    def prompt_has_invalid_outfit(cls, prompt: str) -> bool:
        outfit_sentence = cls.extract_outfit_sentence(prompt)
        try:
            cls.validate_outfit_sentence(outfit_sentence)
        except PromptValidationError:
            return True
        return False

    @classmethod
    def repair_outfit_block(cls, prompt: str, outfit_sentence: str) -> str:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            return normalized_prompt
        try:
            cleaned_sentence = cls.validate_outfit_sentence(outfit_sentence)
        except PromptValidationError:
            composer = cls(None)
            fallback_sentence = composer._clean_fragment(outfit_sentence)
            if fallback_sentence:
                try:
                    cleaned_sentence = composer.validate_outfit_sentence(fallback_sentence)
                except PromptValidationError:
                    cleaned_sentence = composer.validate_outfit_sentence(
                        "soft knit top, straight trousers, comfortable sneakers; practical fit with natural fabric folds"
                    )
            else:
                cleaned_sentence = composer.validate_outfit_sentence(
                    "soft knit top, straight trousers, comfortable sneakers; practical fit with natural fabric folds"
                )
        blocks = [block.strip() for block in normalized_prompt.split("\n\n") if block.strip()]
        if len(blocks) < 4 or not blocks[3].startswith("Outfit: "):
            return normalized_prompt
        blocks[3] = f"Outfit: {cleaned_sentence}."
        return "\n\n".join(blocks)

    @staticmethod
    def _outfit_category(item: str) -> str:
        lowered = str(item or "").lower()
        if any(token in lowered for token in ["dress"]):
            return "dress"
        if any(token in lowered for token in ["jeans", "trousers", "pants", "skirt", "shorts", "denim"]):
            return "bottom"
        if any(token in lowered for token in ["sneakers", "trainers", "boots", "heels", "loafers", "sandals", "slides", "shoes"]):
            return "shoes"
        if any(token in lowered for token in ["coat", "jacket", "blazer", "cardigan", "hoodie", "trench"]):
            return "outerwear"
        if any(token in lowered for token in ["bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "cap", "belt"]):
            return "accessory"
        return "top"

    def _ensure_english_fragment(self, text: str, fallback: str) -> str:
        cleaned = self._clean_fragment(text)
        if not cleaned:
            return self._clean_fragment(fallback)
        if self.CYRILLIC_RE.search(cleaned):
            return self._clean_fragment(fallback)
        return cleaned

    @staticmethod
    def _natural_object_term(obj: str) -> str:
        return {
            "carry_on": "carry on",
            "coffee_cup": "coffee cup",
            "shoulder_bag": "bag",
        }.get(str(obj or "").strip().lower(), str(obj or "").replace("_", " ").strip())

    def _bag_is_legitimate(self, context: Dict[str, Any], scene: Any, coherence: PlaceCoherenceState) -> bool:
        if coherence.allow_wearable_bag or coherence.allow_bag_prop:
            if coherence.private_scene and not coherence.travel_context:
                return self._scene_supports_departure_bag(scene, context)
            return True
        return False

    def _object_is_legitimate(
        self,
        object_term: str,
        context: Dict[str, Any],
        scene: Any,
        coherence: PlaceCoherenceState,
    ) -> bool:
        lowered_scene = self._scene_text(scene).lower()
        behavior = context.get("behavioral_context")
        habit = str(getattr(behavior, "habit", getattr(behavior, "selected_habit", "")) or "").lower()
        lowered_term = str(object_term or "").lower()
        if lowered_term == "coffee cup":
            return (
                habit == "coffee_moment"
                or any(token in lowered_scene for token in ["coffee", "cup", "mug", "kitchen", "cafe", "breakfast", "gate"])
                or coherence.mode in {"airport_gate", "cafe_interior", "home_kitchen", "hotel_kitchenette"}
            )
        if lowered_term == "carry on":
            return coherence.travel_context or coherence.mode.startswith("airport")
        if lowered_term == "bag":
            return self._bag_is_legitimate(context, scene, coherence)
        return True

    def _behavior_object_terms(self, context: Dict[str, Any], scene: Any | None = None) -> List[str]:
        behavior = context.get("behavioral_context")
        if behavior is None:
            return []
        objects = getattr(behavior, "objects", getattr(behavior, "recurring_objects", [])) or []
        normalized = [self._natural_object_term(obj) for obj in objects if self._natural_object_term(obj)]
        if scene is None:
            return self._dedupe_phrases(normalized)
        coherence = self._resolve_place_coherence(context, scene)
        return self._dedupe_phrases(
            [term for term in normalized if self._object_is_legitimate(term, context, scene, coherence)]
        )

    def _is_kitchen_coffee_scene(self, context: Dict[str, Any], scene: Any) -> bool:
        behavior = context.get("behavioral_context")
        if behavior is None:
            return False
        lowered_scene = self._scene_text(scene).lower()
        place_anchor = str(getattr(behavior, "place_anchor", getattr(behavior, "familiar_place_anchor", "")) or "")
        habit = str(getattr(behavior, "habit", getattr(behavior, "selected_habit", "")) or "")
        object_terms = {term.lower() for term in self._behavior_object_terms(context, scene)}
        return (
            place_anchor == "kitchen_corner"
            and habit == "coffee_moment"
            and "coffee cup" in object_terms
            and any(token in lowered_scene for token in ["kitchen", "coffee", "morning"])
        )

    def _behavior_scene_cues(self, context: Dict[str, Any], scene: Any) -> tuple[str, str, str]:
        behavior = context.get("behavioral_context")
        if behavior is None:
            return "", "", ""
        energy = str(getattr(behavior, "energy_level", "medium") or "medium")
        habit = str(getattr(behavior, "habit", getattr(behavior, "selected_habit", "none")) or "none")
        self_presentation = str(getattr(behavior, "self_presentation", "") or "").lower()
        movement = {
            "low": "still posture",
            "medium": "natural pause moment",
            "high": "slow relaxed movement",
        }.get(energy, "")
        interaction = {
            "window_pause": "touching the window lightly",
            "coffee_moment": "holding cup naturally",
            "packing": "handling luggage carefully",
            "slow_walk": "walking with measured steps",
            "none": "resting hands naturally",
        }.get(habit, "")
        expression = {
            "focused": "minimal facial expression with inward attention",
            "composed": "measured expression and upright posture",
            "soft": "gentle expression and relaxed shoulders",
            "transitional": "slight distance in the gaze with a thoughtful pause",
            "relaxed": "easy expression and natural posture",
        }.get(self_presentation, "")
        if self._is_kitchen_coffee_scene(context, scene):
            movement = ""
            interaction = ""
        if "focused" in str(getattr(scene, "mood", "") or "").lower() and not expression:
            expression = "minimal facial expression with inward attention"
        return movement, interaction, expression

    def _sanitize_visual_focus(
        self,
        visual_focus: str,
        object_terms: List[str],
        coherence: PlaceCoherenceState,
    ) -> str:
        cleaned_focus = self._clean_fragment(visual_focus)
        if not cleaned_focus:
            return ""
        allowed = {term.lower() for term in object_terms}
        chunks = [self._clean_fragment(chunk) for chunk in cleaned_focus.split(",") if self._clean_fragment(chunk)]
        kept: List[str] = []
        for chunk in chunks:
            lowered = chunk.lower()
            if "carry on" in lowered and "carry on" not in allowed:
                continue
            if "bag" in lowered and "bag" not in allowed:
                continue
            if coherence.private_scene and coherence.travel_context and "bag" in lowered:
                continue
            kept.append(chunk)
        return ", ".join(self._dedupe_phrases(kept))

    def _scene_micro_detail(
        self,
        scene: Any,
        behavior: Any,
        object_terms: List[str],
        visual_focus: str,
        context: Dict[str, Any],
    ) -> str:
        del behavior
        lowered = self._scene_text(scene).lower()
        coherence = self._resolve_place_coherence(context, scene)
        if any(token in lowered for token in ["terminal", "airport", "gate", "boarding"]) and "waiting" in lowered:
            if "window" in lowered:
                return "seated near window row seating and checking the boarding screen occasionally"
            return "checking the boarding screen occasionally near the gate seating"
        if coherence.private_scene and coherence.travel_context and "bag" in {term.lower() for term in object_terms}:
            return "subtle cue of not fully unpacked travel items nearby"
        if visual_focus:
            return f"small detail: {visual_focus}"
        if object_terms:
            return f"small detail: {object_terms[0]} kept close"
        return "small detail: lived-in candid timing"

    def _object_scene_phrase(
        self,
        object_term: str,
        scene: Any,
        context: Dict[str, Any] | None = None,
        coherence: PlaceCoherenceState | None = None,
    ) -> str:
        lowered = self._scene_text(scene).lower()
        resolved_context = context or {}
        coherence = coherence or self._resolve_place_coherence(resolved_context, scene)
        lowered_term = str(object_term or "").lower()
        if lowered_term == "coffee cup":
            return "coffee cup in hand"
        if lowered_term == "carry on":
            if any(token in lowered for token in ["walking", "walk", "stroll", "moving through"]):
                return "carry on rolling alongside her"
            if coherence.mode.startswith("airport"):
                return "carry on placed beside her seat"
            return "compact carry on left nearby"
        if lowered_term == "bag":
            if not self._bag_is_legitimate(resolved_context, scene, coherence):
                return ""
            if coherence.private_scene and coherence.travel_context:
                return "subtle cue of not fully unpacked travel items nearby"
            if coherence.mode.startswith("airport"):
                return "bag kept close by her side"
            if coherence.mode == "cafe_interior":
                return "bag resting by the chair"
            return "bag resting nearby"
        return f"{object_term} visible in the scene"

    def _coherent_environment_seed(
        self,
        scene: Any,
        context: Dict[str, Any],
        coherence: PlaceCoherenceState,
    ) -> str:
        lighting = self._lighting_hint(getattr(scene, "time_of_day", "day"))
        behavior = context.get("behavioral_context")
        parts: List[str] = [
            f"photorealistic {coherence.canonical_location}",
            "real terminal architecture" if coherence.mode.startswith("airport") else "lived-in environmental detail",
            "physically plausible spatial depth",
            "accurate perspective and scale",
            f"{lighting} behaving as natural available light",
        ]
        if behavior is not None and coherence.allow_background_people:
            presence = {
                "alone": "no other people in frame",
                "light_public": "soft background people only",
                "social": "public life present but secondary",
            }.get(str(getattr(behavior, "social_mode", "alone") or "alone"), "")
            if presence:
                parts.append(presence)
        return "; ".join(self._dedupe_phrases(parts))

    def _scene_clause_conflicts_with_place(self, clause: str, coherence: PlaceCoherenceState) -> bool:
        lowered = str(clause or "").lower()
        if coherence.private_scene and any(
            token in lowered for token in ["soft background people", "public life present", "crowd", "travelers nearby"]
        ):
            return True
        if coherence.mode in {"home_kitchen", "hotel_kitchenette"}:
            if any(token in lowered for token in ["airport", "terminal", "gate", "runway"]):
                return True
            if coherence.mode == "home_kitchen" and any(token in lowered for token in ["hotel room", "hotel window", "hotel corner"]):
                return True
            if coherence.mode == "hotel_kitchenette" and "hotel room" in lowered and "kitchen" not in lowered:
                return True
        if coherence.mode.startswith("airport") and any(
            token in lowered for token in ["home kitchen", "living room", "bedside", "bathroom mirror"]
        ):
            return True
        if coherence.mode == "cafe_interior" and any(token in lowered for token in ["airport terminal", "hotel room", "home kitchen"]):
            return True
        return False

    def _scene_mentions_place(self, scene_body: str, coherence: PlaceCoherenceState) -> bool:
        lowered = str(scene_body or "").lower()
        return any(keyword in lowered for keyword in coherence.location_keywords if keyword)

    def _scene_place_clause(self, coherence: PlaceCoherenceState) -> str:
        if coherence.mode.startswith("airport"):
            return f"at the {coherence.canonical_location}"
        if coherence.mode == "cafe_interior":
            return "inside the cafe"
        if coherence.private_scene:
            return f"in the {coherence.canonical_location}"
        return f"at {coherence.canonical_location}"

    def _coherent_scene_body(
        self,
        scene_body: str,
        scene: Any,
        context: Dict[str, Any],
        coherence: PlaceCoherenceState,
    ) -> str:
        clauses = [clause["text"] for clause in self._extract_semantic_clauses("Scene", scene_body)]
        cleaned_clauses: List[str] = []
        object_terms = self._behavior_object_terms(context, scene)
        for clause in clauses:
            lowered = clause.lower()
            if self._scene_clause_conflicts_with_place(clause, coherence):
                continue
            if "bag" in lowered and "bag" not in {term.lower() for term in object_terms}:
                continue
            if "carry on" in lowered and "carry on" not in {term.lower() for term in object_terms}:
                continue
            cleaned_clauses.append(clause)
        if not cleaned_clauses:
            cleaned_clauses.append(self._scene_presence_lead(scene, scene_body))
        if self._scene_clause_conflicts_with_place(cleaned_clauses[0], coherence):
            cleaned_clauses[0] = self._scene_presence_lead(scene, scene_body)
        scene_text = ", ".join(cleaned_clauses)
        if not self._scene_mentions_place(scene_text, coherence):
            cleaned_clauses.append(self._scene_place_clause(coherence))
        if coherence.private_scene and coherence.travel_context and "bag" in {term.lower() for term in object_terms}:
            travel_cue = "subtle cue of not fully unpacked travel items nearby"
            cleaned_clauses = [clause for clause in cleaned_clauses if clause.lower() != travel_cue]
            cleaned_clauses.insert(1 if cleaned_clauses else 0, travel_cue)
        for object_term in object_terms:
            phrase = self._object_scene_phrase(object_term, scene, context=context, coherence=coherence)
            if phrase and phrase.lower() not in ", ".join(cleaned_clauses).lower():
                cleaned_clauses.append(phrase)
        return ", ".join(self._dedupe_semantic_phrases(cleaned_clauses))

    def _coherent_mood_body(
        self,
        mood_body: str,
        scene: Any,
        context: Dict[str, Any],
        coherence: PlaceCoherenceState,
        *,
        apply_in_the_moment: bool,
    ) -> str:
        time_of_day = str(getattr(scene, "time_of_day", "") or "").lower()
        if coherence.private_scene and time_of_day in {"early_morning", "morning", "late_morning"}:
            return "already happening by the time the camera catches it"
        if apply_in_the_moment:
            rewritten = self._in_the_moment_mood_body(mood_body)
            return rewritten or self._fallback_mood_presence_phrase(scene, context)
        base = mood_body or self._split_block_label(self._mood_block(context, scene, "", {}))[1]
        return self._clean_fragment(base) or "quiet confidence"

    def _apply_place_coherence_to_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str,
        shot_archetype: str,
        apply_in_the_moment: bool,
    ) -> Dict[str, Any]:
        block_map = self._prompt_block_map(prompt)
        if not block_map:
            return {"prompt": str(prompt or "").strip(), "prompt_blocks": {}, "changed": False}

        scene_body = self._split_block_label(block_map["Scene"])[1]
        environment_body = self._split_block_label(block_map["Environment"])[1]
        current_outfit = self._clean_fragment(outfit_sentence) or self._split_block_label(block_map["Outfit"])[1]
        coherence = self._resolve_place_coherence(
            context,
            scene,
            scene_body=scene_body,
            environment_body=environment_body,
            outfit_body=current_outfit,
        )
        coherent_outfit = self._coherent_outfit_sentence(
            current_outfit,
            scene=scene,
            context=context,
            shot_archetype=shot_archetype,
            coherence=coherence,
            apply_in_the_moment=apply_in_the_moment,
        )
        coherent_scene = self._coherent_scene_body(scene_body, scene, context, coherence)
        coherent_environment = self._coherent_environment_seed(scene, context, coherence)
        coherent_mood = self._coherent_mood_body(
            self._split_block_label(block_map["Mood"])[1],
            scene,
            context,
            coherence,
            apply_in_the_moment=apply_in_the_moment,
        )
        if apply_in_the_moment:
            coherent_environment = self._in_the_moment_environment_body(coherent_environment)
            coherent_scene = self._in_the_moment_scene_body(coherent_scene, scene)

        updated_blocks = dict(block_map)
        updated_blocks["Scene"] = f"Scene: {self._clean_fragment(coherent_scene)}."
        updated_blocks["Outfit"] = f"Outfit: {self._clean_fragment(coherent_outfit)}."
        updated_blocks["Environment"] = f"Environment: {self._clean_fragment(coherent_environment)}."
        updated_blocks["Mood"] = f"Mood: {self._clean_fragment(coherent_mood)}."
        updated_prompt = "\n\n".join(
            updated_blocks[name]
            for name in ["Identity", "Framing", "Scene", "Outfit", "Environment", "Mood"]
        )
        return {
            "prompt": updated_prompt,
            "prompt_blocks": updated_blocks,
            "changed": updated_prompt.strip() != str(prompt or "").strip(),
        }

    def _place_coherence_conflicts(self, block_map: Dict[str, str], scene: Any, context: Dict[str, Any]) -> List[str]:
        coherence = self._resolve_place_coherence(
            context,
            scene,
            scene_body=self._split_block_label(block_map.get("Scene", ""))[1],
            environment_body=self._split_block_label(block_map.get("Environment", ""))[1],
            outfit_body=self._split_block_label(block_map.get("Outfit", ""))[1],
        )
        scene_body = self._split_block_label(block_map.get("Scene", ""))[1].lower()
        environment_body = self._split_block_label(block_map.get("Environment", ""))[1].lower()
        outfit_body = self._split_block_label(block_map.get("Outfit", ""))[1].lower()
        conflicts: List[str] = []
        if coherence.private_scene and any(
            token in environment_body for token in ["soft background people only", "public life present"]
        ):
            conflicts.append("Place coherence conflict: private scene cannot include public background presence")
        if coherence.mode in {"home_kitchen", "hotel_kitchenette"} and any(
            token in environment_body for token in ["airport terminal", "airport gate", "terminal architecture"]
        ):
            conflicts.append("Place coherence conflict: kitchen scene cannot use transit-space environment")
        if coherence.mode.startswith("airport") and any(
            token in environment_body for token in ["home kitchen", "living room", "bathroom mirror", "bedside"]
        ):
            conflicts.append("Place coherence conflict: airport scene cannot use home-style environment")
        if coherence.mode == "home_kitchen" and "hotel room" in environment_body:
            conflicts.append("Place coherence conflict: environment label must follow the kitchen anchor")
        if coherence.mode == "hotel_kitchenette" and "hotel room" in environment_body and "kitchen" not in environment_body:
            conflicts.append("Place coherence conflict: environment label must follow the kitchen anchor")
        if "carry on" in outfit_body or "overnight bag" in outfit_body:
            conflicts.append("Place coherence conflict: outfit props must stay out of the outfit block")
        if "bag" in outfit_body and not coherence.allow_wearable_bag:
            conflicts.append("Place coherence conflict: outfit props must not contradict the scene")
        if self._scene_clause_conflicts_with_place(scene_body, coherence):
            conflicts.append("Place coherence conflict: scene anchor and environment family diverged")
        return conflicts

    def finalize_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        outfit_sentence: str = "",
        shot_archetype: str = "",
        step: str = "",
        apply_rewrite: bool,
        allow_fallback: bool,
    ) -> Dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        diagnostics: Dict[str, Any] = {
            "prompt": normalized_prompt,
            "prompt_blocks": self._prompt_block_map(normalized_prompt),
            "duplicate_clauses": [],
            "duplicate_sequence_candidates": [],
            "duplicate_sequence_removed": [],
            "duplicate_sequence_kept_reason": [],
            "sanitized_prompt_applied": False,
            "rewrite_pass_applied": False,
            "rewrite_diagnostics": {},
            "fallback_prompt_applied": False,
            "finalization_path": "main",
            "fatal_validation_reason": "",
            "garment_phrase_compaction_applied": False,
            "softened_duplicate_sequences_count": 0,
            "prompt_blocker_demoted_to_warning": False,
            "safe_fallback_used": False,
            "quality_recovery_applied": False,
            "quality_floor_met": False,
            "quality_recovery_reasons": [],
            "validation_severity": "pending",
            "outfit_validation_status": "pending",
            "outfit_repair_applied": False,
            "outfit_fallback_used": False,
            "outfit_fallback_reason": "",
            "outfit_recovery_source": "primary",
            "user_facing_prompt_placeholder_used": False,
            "post_sanitize_prompt_length": len(normalized_prompt),
            "post_sanitize_validation_result": "pending",
            "sanitization_step": step,
        }

        working_prompt = normalized_prompt
        preferred_outfit = self._clean_fragment(outfit_sentence) or self.extract_outfit_sentence(working_prompt)

        resolved_shot = shot_archetype or self._resolve_shot_archetype(scene, context, context.get("recent_moment_memory") or [])
        if apply_rewrite:
            rewritten = self.rewrite_canonical_prompt(
                working_prompt,
                scene,
                context,
                shot_archetype=resolved_shot,
            )
            working_prompt = str(rewritten.get("prompt") or working_prompt).strip()
            diagnostics["rewrite_pass_applied"] = bool(rewritten.get("rewrite_pass_applied"))
            diagnostics["prompt_blocks"] = dict(rewritten.get("prompt_blocks") or diagnostics["prompt_blocks"])

        coherent_prompt = self._apply_place_coherence_to_prompt(
            working_prompt,
            scene,
            context,
            outfit_sentence=preferred_outfit,
            shot_archetype=resolved_shot,
            apply_in_the_moment=True,
        )
        working_prompt = str(coherent_prompt.get("prompt") or working_prompt).strip()
        diagnostics["prompt_blocks"] = dict(coherent_prompt.get("prompt_blocks") or diagnostics["prompt_blocks"])
        diagnostics["sanitized_prompt_applied"] = (
            diagnostics["sanitized_prompt_applied"]
            or bool(coherent_prompt.get("changed"))
        )
        diagnostics["rewrite_diagnostics"] = self._rewrite_pass_diagnostics(diagnostics["prompt_blocks"]) if diagnostics["prompt_blocks"] else {}

        if self.prompt_has_invalid_outfit(working_prompt):
            recovered_outfit_prompt = self.recover_prompt_outfit_block(
                working_prompt,
                scene,
                context,
                outfit_sentence=preferred_outfit,
                outfit_struct=context.get("outfit_struct"),
                shot_archetype=resolved_shot,
                apply_in_the_moment=True,
            )
            working_prompt = str(recovered_outfit_prompt.get("prompt") or working_prompt).strip()
            preferred_outfit = self._clean_fragment(
                str(recovered_outfit_prompt.get("outfit_sentence") or preferred_outfit or self.extract_outfit_sentence(working_prompt))
            )
            diagnostics["prompt_blocks"] = dict(recovered_outfit_prompt.get("prompt_blocks") or diagnostics["prompt_blocks"])
            diagnostics["sanitized_prompt_applied"] = (
                diagnostics["sanitized_prompt_applied"]
                or bool(recovered_outfit_prompt.get("changed"))
            )
            diagnostics["outfit_validation_status"] = str(recovered_outfit_prompt.get("outfit_validation_status") or "pending")
            diagnostics["outfit_repair_applied"] = bool(recovered_outfit_prompt.get("outfit_repair_applied"))
            diagnostics["outfit_fallback_used"] = bool(recovered_outfit_prompt.get("outfit_fallback_used"))
            diagnostics["outfit_fallback_reason"] = str(recovered_outfit_prompt.get("outfit_fallback_reason") or "")
            diagnostics["outfit_recovery_source"] = str(recovered_outfit_prompt.get("outfit_recovery_source") or "primary")
            diagnostics["user_facing_prompt_placeholder_used"] = False
        else:
            diagnostics["outfit_validation_status"] = "passed"

        clause_sanitized = self.sanitize_canonical_prompt(
            working_prompt,
            scene,
            context,
            outfit_sentence=preferred_outfit,
            step=f"{step or 'finalize'}:duplicate_clauses",
        )
        working_prompt = str(clause_sanitized.get("prompt") or working_prompt).strip()
        diagnostics["duplicate_clauses"] = list(clause_sanitized.get("duplicate_clauses", []))
        diagnostics["sanitized_prompt_applied"] = (
            diagnostics["sanitized_prompt_applied"]
            or bool(clause_sanitized.get("sanitized_prompt_applied"))
        )
        diagnostics["prompt_blocks"] = dict(clause_sanitized.get("prompt_blocks") or diagnostics["prompt_blocks"])

        last_error: PromptValidationError | None = None
        for attempt_index, aggressive in enumerate((False, True), start=1):
            sequence_sanitized = self._sanitize_duplicate_sequences_in_canonical_prompt(
                working_prompt,
                scene,
                context,
                aggressive=aggressive,
                outfit_sentence=preferred_outfit,
                step=f"{step or 'finalize'}:duplicate_sequence_attempt_{attempt_index}",
            )
            candidate_prompt = str(sequence_sanitized.get("prompt") or working_prompt).strip()
            diagnostics["duplicate_sequence_candidates"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_candidates"] + list(sequence_sanitized.get("duplicate_sequence_candidates", []))
            )
            diagnostics["duplicate_sequence_removed"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_removed"] + list(sequence_sanitized.get("duplicate_sequence_removed", []))
            )
            diagnostics["duplicate_sequence_kept_reason"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_kept_reason"] + list(sequence_sanitized.get("duplicate_sequence_kept_reason", []))
            )
            diagnostics["sanitized_prompt_applied"] = (
                diagnostics["sanitized_prompt_applied"]
                or bool(sequence_sanitized.get("sanitized_prompt_applied"))
            )
            if sequence_sanitized.get("prompt_blocks"):
                diagnostics["prompt_blocks"] = dict(sequence_sanitized.get("prompt_blocks") or diagnostics["prompt_blocks"])

            simplified = self._soft_simplify_canonical_prompt(
                candidate_prompt,
                scene,
                context,
                outfit_sentence=preferred_outfit,
                aggressive=aggressive,
            )
            candidate_prompt = str(simplified.get("prompt") or candidate_prompt).strip()
            diagnostics["garment_phrase_compaction_applied"] = (
                diagnostics["garment_phrase_compaction_applied"]
                or bool(simplified.get("garment_phrase_compaction_applied"))
            )
            diagnostics["softened_duplicate_sequences_count"] = int(
                diagnostics["softened_duplicate_sequences_count"]
                + int(simplified.get("softened_duplicate_sequences_count") or 0)
            )
            diagnostics["sanitized_prompt_applied"] = (
                diagnostics["sanitized_prompt_applied"]
                or bool(simplified.get("changed"))
            )
            if simplified.get("prompt_blocks"):
                diagnostics["prompt_blocks"] = dict(simplified.get("prompt_blocks") or diagnostics["prompt_blocks"])

            quality_before = self._prompt_quality_floor_diagnostics(candidate_prompt, scene, context)
            if not quality_before.get("passed"):
                diagnostics["quality_recovery_reasons"] = self._dedupe_phrases(
                    diagnostics["quality_recovery_reasons"] + list(quality_before.get("failed_checks", []))
                )
                quality_recovered = self._recover_canonical_prompt_quality(
                    candidate_prompt,
                    scene,
                    context,
                    outfit_sentence=preferred_outfit,
                    shot_archetype=resolved_shot,
                )
                candidate_prompt = str(quality_recovered.get("prompt") or candidate_prompt).strip()
                diagnostics["quality_recovery_applied"] = (
                    diagnostics["quality_recovery_applied"]
                    or bool(quality_recovered.get("quality_recovery_applied"))
                )
                diagnostics["garment_phrase_compaction_applied"] = (
                    diagnostics["garment_phrase_compaction_applied"]
                    or bool(quality_recovered.get("outfit_recovered"))
                )
                if quality_recovered.get("prompt_blocks"):
                    diagnostics["prompt_blocks"] = dict(quality_recovered.get("prompt_blocks") or diagnostics["prompt_blocks"])
                if quality_recovered.get("quality_recovery_applied"):
                    diagnostics["sanitized_prompt_applied"] = True

                recovery_sanitized = self._sanitize_duplicate_sequences_in_canonical_prompt(
                    candidate_prompt,
                    scene,
                    context,
                    aggressive=False,
                    outfit_sentence=preferred_outfit,
                    step=f"{step or 'finalize'}:quality_recovery_duplicate_sequence_{attempt_index}",
                )
                candidate_prompt = str(recovery_sanitized.get("prompt") or candidate_prompt).strip()
                diagnostics["duplicate_sequence_candidates"] = self._dedupe_phrases(
                    diagnostics["duplicate_sequence_candidates"] + list(recovery_sanitized.get("duplicate_sequence_candidates", []))
                )
                diagnostics["duplicate_sequence_removed"] = self._dedupe_phrases(
                    diagnostics["duplicate_sequence_removed"] + list(recovery_sanitized.get("duplicate_sequence_removed", []))
                )
                diagnostics["duplicate_sequence_kept_reason"] = self._dedupe_phrases(
                    diagnostics["duplicate_sequence_kept_reason"] + list(recovery_sanitized.get("duplicate_sequence_kept_reason", []))
                )
                diagnostics["sanitized_prompt_applied"] = (
                    diagnostics["sanitized_prompt_applied"]
                    or bool(recovery_sanitized.get("sanitized_prompt_applied"))
                )
                if recovery_sanitized.get("prompt_blocks"):
                    diagnostics["prompt_blocks"] = dict(recovery_sanitized.get("prompt_blocks") or diagnostics["prompt_blocks"])

            try:
                self._validate_canonical_prompt_core(candidate_prompt, scene, context)
                quality_after = self._prompt_quality_floor_diagnostics(candidate_prompt, scene, context)
                diagnostics["quality_recovery_reasons"] = self._dedupe_phrases(
                    diagnostics["quality_recovery_reasons"] + list(quality_after.get("failed_checks", []))
                )
                if not quality_after.get("passed"):
                    raise PromptValidationError(
                        "Quality floor not met: " + ", ".join(quality_after.get("failed_checks", []))
                    )
                diagnostics["prompt"] = candidate_prompt
                diagnostics["post_sanitize_prompt_length"] = len(candidate_prompt)
                diagnostics["post_sanitize_validation_result"] = "passed"
                diagnostics["prompt_blocks"] = self._prompt_block_map(candidate_prompt) or diagnostics["prompt_blocks"]
                diagnostics["quality_floor_met"] = True
                diagnostics["garment_phrase_compaction_applied"] = (
                    diagnostics["garment_phrase_compaction_applied"]
                    or self.extract_outfit_sentence(candidate_prompt) != self.extract_outfit_sentence(normalized_prompt)
                )
                if (
                    diagnostics["outfit_validation_status"] == "passed"
                    and self.extract_outfit_sentence(candidate_prompt) != self.extract_outfit_sentence(normalized_prompt)
                ):
                    diagnostics["outfit_validation_status"] = "recoverable"
                    diagnostics["outfit_repair_applied"] = True
                diagnostics["sanitized_prompt_applied"] = (
                    diagnostics["sanitized_prompt_applied"]
                    or candidate_prompt != normalized_prompt
                    or bool(diagnostics["duplicate_sequence_removed"])
                )
                soft_duplicate_entries = [entry for entry in self._duplicate_clause_entries(candidate_prompt) if entry.get("severity") != "fatal"]
                softened_sequences = [
                    entry["sequence"]
                    for entry in self._detect_duplicate_sequence_candidates(candidate_prompt)
                    if not self._is_fatal_duplicate_sequence(entry)
                ]
                had_blocker = bool(
                    diagnostics["duplicate_clauses"]
                    or diagnostics["duplicate_sequence_candidates"]
                    or diagnostics["duplicate_sequence_removed"]
                )
                if soft_duplicate_entries or softened_sequences or had_blocker:
                    diagnostics["prompt_blocker_demoted_to_warning"] = True
                    diagnostics["validation_severity"] = "warning"
                else:
                    diagnostics["validation_severity"] = "clean"
                diagnostics["finalization_path"] = "sanitized" if diagnostics["sanitized_prompt_applied"] else "main"
                logger.info(
                    "prompt_duplicate_sequence_trace scene=%s step=%s duplicate_sequence_candidates=%s duplicate_sequence_removed=%s duplicate_sequence_kept_reason=%s post_sanitize_prompt_length=%s post_sanitize_validation_result=%s",
                    str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or "unknown_scene"),
                    step or "finalize",
                    ", ".join(diagnostics["duplicate_sequence_candidates"]) or "-",
                    ", ".join(diagnostics["duplicate_sequence_removed"]) or "-",
                    ", ".join(diagnostics["duplicate_sequence_kept_reason"]) or "-",
                    diagnostics["post_sanitize_prompt_length"],
                    diagnostics["post_sanitize_validation_result"],
                )
                return diagnostics
            except PromptValidationError as exc:
                last_error = exc
                diagnostics["fatal_validation_reason"] = str(exc)
                diagnostics["post_sanitize_prompt_length"] = len(candidate_prompt)
                diagnostics["post_sanitize_validation_result"] = f"retry_needed:{exc}"
                working_prompt = candidate_prompt

        if allow_fallback:
            fallback = self._build_safe_fallback_canonical_prompt(
                working_prompt,
                scene,
                context,
                outfit_sentence=preferred_outfit,
                shot_archetype=resolved_shot,
            )
            fallback_prompt = str(fallback.get("prompt") or working_prompt).strip()
            fallback_sanitized = self._sanitize_duplicate_sequences_in_canonical_prompt(
                fallback_prompt,
                scene,
                context,
                aggressive=True,
                outfit_sentence=preferred_outfit,
                step=f"{step or 'finalize'}:fallback_duplicate_sequence",
            )
            fallback_prompt = str(fallback_sanitized.get("prompt") or fallback_prompt).strip()
            coherent_fallback = self._apply_place_coherence_to_prompt(
                fallback_prompt,
                scene,
                context,
                outfit_sentence=preferred_outfit,
                shot_archetype=resolved_shot,
                apply_in_the_moment=True,
            )
            fallback_prompt = str(coherent_fallback.get("prompt") or fallback_prompt).strip()
            fallback_simplified = self._soft_simplify_canonical_prompt(
                fallback_prompt,
                scene,
                context,
                outfit_sentence=preferred_outfit,
                aggressive=True,
            )
            fallback_prompt = str(fallback_simplified.get("prompt") or fallback_prompt).strip()
            fallback_quality = self._prompt_quality_floor_diagnostics(fallback_prompt, scene, context)
            if not fallback_quality.get("passed"):
                diagnostics["quality_recovery_reasons"] = self._dedupe_phrases(
                    diagnostics["quality_recovery_reasons"] + list(fallback_quality.get("failed_checks", []))
                )
                recovered_fallback = self._recover_canonical_prompt_quality(
                    fallback_prompt,
                    scene,
                    context,
                    outfit_sentence=preferred_outfit,
                    shot_archetype=resolved_shot,
                )
                fallback_prompt = str(recovered_fallback.get("prompt") or fallback_prompt).strip()
                diagnostics["quality_recovery_applied"] = (
                    diagnostics["quality_recovery_applied"]
                    or bool(recovered_fallback.get("quality_recovery_applied"))
                )
                diagnostics["garment_phrase_compaction_applied"] = (
                    diagnostics["garment_phrase_compaction_applied"]
                    or bool(recovered_fallback.get("outfit_recovered"))
                )
                if recovered_fallback.get("prompt_blocks"):
                    diagnostics["prompt_blocks"] = dict(recovered_fallback.get("prompt_blocks") or diagnostics["prompt_blocks"])
            diagnostics["duplicate_sequence_candidates"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_candidates"] + list(fallback_sanitized.get("duplicate_sequence_candidates", []))
            )
            diagnostics["duplicate_sequence_removed"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_removed"] + list(fallback_sanitized.get("duplicate_sequence_removed", []))
            )
            diagnostics["duplicate_sequence_kept_reason"] = self._dedupe_phrases(
                diagnostics["duplicate_sequence_kept_reason"] + list(fallback_sanitized.get("duplicate_sequence_kept_reason", []))
            )
            diagnostics["sanitized_prompt_applied"] = (
                diagnostics["sanitized_prompt_applied"]
                or bool(fallback_sanitized.get("sanitized_prompt_applied"))
                or bool(coherent_fallback.get("changed"))
                or bool(fallback_simplified.get("changed"))
            )
            diagnostics["garment_phrase_compaction_applied"] = (
                diagnostics["garment_phrase_compaction_applied"]
                or bool(fallback_simplified.get("garment_phrase_compaction_applied"))
            )
            diagnostics["softened_duplicate_sequences_count"] = int(
                diagnostics["softened_duplicate_sequences_count"]
                + int(fallback_simplified.get("softened_duplicate_sequences_count") or 0)
            )
            try:
                self._validate_canonical_prompt_core(fallback_prompt, scene, context)
                fallback_quality = self._prompt_quality_floor_diagnostics(fallback_prompt, scene, context)
                diagnostics["quality_recovery_reasons"] = self._dedupe_phrases(
                    diagnostics["quality_recovery_reasons"] + list(fallback_quality.get("failed_checks", []))
                )
                if not fallback_quality.get("passed"):
                    raise PromptValidationError(
                        "Quality floor not met: " + ", ".join(fallback_quality.get("failed_checks", []))
                    )
                diagnostics["prompt"] = fallback_prompt
                diagnostics["prompt_blocks"] = (
                    dict(fallback_simplified.get("prompt_blocks") or {})
                    or dict(coherent_fallback.get("prompt_blocks") or {})
                    or self._prompt_block_map(fallback_prompt)
                    or dict(fallback.get("prompt_blocks") or {})
                )
                diagnostics["fallback_prompt_applied"] = True
                diagnostics["sanitized_prompt_applied"] = True
                diagnostics["finalization_path"] = "fallback"
                diagnostics["safe_fallback_used"] = True
                diagnostics["validation_severity"] = "hard_fallback"
                diagnostics["outfit_validation_status"] = "degraded"
                diagnostics["outfit_repair_applied"] = True
                diagnostics["outfit_fallback_used"] = True
                diagnostics["outfit_recovery_source"] = "fallback"
                diagnostics["outfit_fallback_reason"] = diagnostics["outfit_fallback_reason"] or diagnostics["fatal_validation_reason"] or "fallback_prompt_path"
                diagnostics["quality_floor_met"] = True
                diagnostics["garment_phrase_compaction_applied"] = (
                    diagnostics["garment_phrase_compaction_applied"]
                    or self.extract_outfit_sentence(fallback_prompt) != self.extract_outfit_sentence(normalized_prompt)
                )
                diagnostics["post_sanitize_prompt_length"] = len(fallback_prompt)
                diagnostics["post_sanitize_validation_result"] = "passed_with_fallback"
                logger.warning(
                    "prompt_duplicate_sequence_fallback_applied scene=%s step=%s duplicate_sequence_candidates=%s duplicate_sequence_removed=%s duplicate_sequence_kept_reason=%s post_sanitize_prompt_length=%s",
                    str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or "unknown_scene"),
                    step or "finalize",
                    ", ".join(diagnostics["duplicate_sequence_candidates"]) or "-",
                    ", ".join(diagnostics["duplicate_sequence_removed"]) or "-",
                    ", ".join(diagnostics["duplicate_sequence_kept_reason"]) or "-",
                    diagnostics["post_sanitize_prompt_length"],
                )
                return diagnostics
            except PromptValidationError as exc:
                last_error = exc
                diagnostics["fatal_validation_reason"] = str(exc)
                diagnostics["post_sanitize_prompt_length"] = len(fallback_prompt)
                diagnostics["post_sanitize_validation_result"] = f"fallback_failed:{exc}"

        diagnostics["validation_severity"] = "fatal"
        logger.warning(
            "prompt_duplicate_sequence_unresolved scene=%s step=%s duplicate_sequence_candidates=%s duplicate_sequence_removed=%s duplicate_sequence_kept_reason=%s post_sanitize_prompt_length=%s post_sanitize_validation_result=%s",
            str(getattr(scene, "scene_moment", "") or getattr(scene, "description", "") or "unknown_scene"),
            step or "finalize",
            ", ".join(diagnostics["duplicate_sequence_candidates"]) or "-",
            ", ".join(diagnostics["duplicate_sequence_removed"]) or "-",
            ", ".join(diagnostics["duplicate_sequence_kept_reason"]) or "-",
            diagnostics["post_sanitize_prompt_length"],
            diagnostics["post_sanitize_validation_result"],
        )
        if last_error is not None:
            raise last_error
        return diagnostics

    def _validate_canonical_prompt(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        allow_repair: bool = True,
        allow_fallback: bool = False,
        step: str = "validate_canonical_prompt",
    ) -> Dict[str, Any]:
        if allow_repair:
            try:
                self._validate_canonical_prompt_core(prompt, scene, context)
            except PromptValidationError as exc:
                repairable_markers = (
                    "Duplicate ",
                    "Required object missing",
                    "Rewrite pass failed",
                    "Place coherence conflict",
                    "Outfit block",
                )
                if not any(marker in str(exc) for marker in repairable_markers):
                    raise
            return self.finalize_canonical_prompt(
                prompt,
                scene,
                context,
                outfit_sentence=self.extract_outfit_sentence(prompt),
                shot_archetype="",
                step=step,
                apply_rewrite=False,
                allow_fallback=allow_fallback,
            )
        self._validate_canonical_prompt_core(prompt, scene, context)
        return {
            "prompt": str(prompt or "").strip(),
            "prompt_blocks": self._prompt_block_map(prompt),
            "duplicate_clauses": [],
            "duplicate_sequence_candidates": [],
            "duplicate_sequence_removed": [],
            "duplicate_sequence_kept_reason": [],
            "sanitized_prompt_applied": False,
            "rewrite_pass_applied": False,
            "rewrite_diagnostics": {},
            "fallback_prompt_applied": False,
            "finalization_path": "main",
            "fatal_validation_reason": "",
            "garment_phrase_compaction_applied": False,
            "softened_duplicate_sequences_count": 0,
            "prompt_blocker_demoted_to_warning": False,
            "safe_fallback_used": False,
            "quality_recovery_applied": False,
            "quality_floor_met": True,
            "quality_recovery_reasons": [],
            "validation_severity": "clean",
            "outfit_validation_status": "passed",
            "outfit_repair_applied": False,
            "outfit_fallback_used": False,
            "outfit_fallback_reason": "",
            "outfit_recovery_source": "primary",
            "user_facing_prompt_placeholder_used": False,
            "post_sanitize_prompt_length": len(str(prompt or "").strip()),
            "post_sanitize_validation_result": "passed",
        }

    def _validate_canonical_prompt_core(
        self,
        prompt: str,
        scene: Any,
        context: Dict[str, Any],
        *,
        strict_duplicate_validation: bool = False,
    ) -> None:
        raw_blocks = [block.strip() for block in prompt.split("\n\n")]
        if len(raw_blocks) != 6 or any(not block for block in raw_blocks):
            raise PromptValidationError("Canonical prompt must contain exactly six non-empty blocks.")
        blocks = raw_blocks
        if not blocks[0].startswith("Identity: "):
            raise PromptValidationError("Canonical prompt must start with the identity block.")
        if not blocks[2].startswith("Scene: "):
            raise PromptValidationError("Canonical prompt must contain a scene block in third position.")
        if not blocks[3].startswith("Outfit: "):
            raise PromptValidationError("Canonical prompt must contain an outfit block in fourth position.")
        if not blocks[4].startswith("Environment: "):
            raise PromptValidationError("Canonical prompt must contain an environment block in fifth position.")
        if not blocks[5].startswith("Mood: "):
            raise PromptValidationError("Canonical prompt must contain a mood block in sixth position.")
        if self.CYRILLIC_RE.search(prompt):
            raise PromptValidationError("Cyrillic detected in prompt")
        for index, block in enumerate(blocks):
            _, _, body = block.partition(":")
            body_text = body.strip() or block.strip()
            if index != 1 and not body.strip():
                raise PromptValidationError("Canonical prompt contains an empty block body")
            if self._is_placeholder_body(body_text):
                if index == 3:
                    raise PromptValidationError("Outfit block is empty")
                raise PromptValidationError("Canonical prompt contains a placeholder block body")

        outfit_body = blocks[3].replace("Outfit: ", "").strip().rstrip(".")
        self.validate_outfit_sentence(outfit_body)

        lowered = prompt.lower()
        for phrase in self.BANNED_SYNTHETIC_PATTERNS + self.FORBIDDEN_POSITIVE_PHRASES:
            if phrase in lowered:
                raise PromptValidationError(f"Forbidden phrase in positive prompt: {phrase}")

        rewrite_diagnostics = self._rewrite_pass_diagnostics(
            {
                "Identity": blocks[0],
                "Framing": blocks[1],
                "Scene": blocks[2],
                "Outfit": blocks[3],
                "Environment": blocks[4],
                "Mood": blocks[5],
            }
        )
        if not rewrite_diagnostics.get("passed"):
            raise PromptValidationError("Rewrite pass failed to remove prompt anti-patterns")

        place_conflicts = self._place_coherence_conflicts(
            {
                "Identity": blocks[0],
                "Framing": blocks[1],
                "Scene": blocks[2],
                "Outfit": blocks[3],
                "Environment": blocks[4],
                "Mood": blocks[5],
            },
            scene,
            context,
        )
        if place_conflicts:
            raise PromptValidationError("; ".join(place_conflicts))

        duplicate_clause_entries = self._duplicate_clause_entries(prompt)
        if any(entry.get("severity") == "fatal" for entry in duplicate_clause_entries):
            raise PromptValidationError("Duplicate clauses detected in prompt")

        if self._is_travel_walk(self._scene_text(scene).lower()):
            if blocks[1] != "3/4 body walking shot":
                raise PromptValidationError("Travel walk framing must be exactly '3/4 body walking shot'.")
            for token in ("waist-up", "half-body", "full body"):
                if token in lowered:
                    raise PromptValidationError(f"Forbidden framing alternative detected: {token}")

        framing_block = blocks[1].lower()
        for block in blocks[2:]:
            for token in self.FRAMING_TOKENS:
                if token in block.lower() and token not in framing_block:
                    raise PromptValidationError("Conflicting framing detected outside framing block")

        required_objects = self._behavior_object_terms(context, scene)
        for object_term in required_objects:
            lowered_object = object_term.lower() if object_term else ""
            if not lowered_object:
                continue
            if lowered_object in lowered:
                continue
            if lowered_object == "bag" and any(
                alias in lowered
                for alias in [
                    "travel items nearby",
                    "not fully unpacked travel items nearby",
                    "overnight bag",
                    "shoulder bag",
                    "crossbody bag",
                    "bag resting",
                ]
            ):
                continue
            raise PromptValidationError(f"Required object missing from prompt: {object_term}")

        duplicate_sequence_candidates = self._detect_duplicate_sequence_candidates(prompt)
        if any(self._is_fatal_duplicate_sequence(entry) for entry in duplicate_sequence_candidates):
            raise PromptValidationError("Duplicate word sequence detected in canonical prompt.")
        if strict_duplicate_validation and duplicate_clause_entries:
            raise PromptValidationError("Duplicate clauses detected in prompt")

    def _is_placeholder_body(self, text: str) -> bool:
        cleaned = self._clean_fragment(text).lower()
        if not cleaned:
            return True
        if cleaned in self.PLACEHOLDER_TOKENS:
            return True
        if re.fullmatch(r"[.\-_/]+", cleaned):
            return True
        return False

    @staticmethod
    def _extract_continuity_hint(continuity_block: str) -> str:
        for part in continuity_block.replace("continuity: ", "").split(";"):
            cleaned = part.strip()
            if cleaned.startswith("hint="):
                return cleaned.replace("hint=", "").strip()
        return ""

    @staticmethod
    def _travel_luggage_phrase(lowered_scene_text: str, visual_focus: str) -> str:
        if "suitcase" in lowered_scene_text or "carry-on" in lowered_scene_text or "carry on" in lowered_scene_text:
            return ", pulling a wheeled carry-on suitcase"
        if "luggage" in lowered_scene_text:
            return ", pulling her luggage"
        if "shoulder bag" in lowered_scene_text or "bag" in visual_focus.lower():
            return ", carrying a shoulder bag"
        return ""

    @staticmethod
    def _time_scene_phrase(scene: Any) -> str:
        time_of_day = str(getattr(scene, "time_of_day", "") or "").strip().lower()
        mapping = {
            "early_morning": "a calm early morning",
            "morning": "a calm morning",
            "late_morning": "a calm late morning",
            "noon": "midday",
            "afternoon": "a calm afternoon",
            "golden_hour": "golden hour",
            "evening": "a quiet evening",
            "night": "a quiet night",
        }
        return mapping.get(time_of_day, "a calm day")

    @staticmethod
    def _is_travel_walk(lowered_scene_text: str) -> bool:
        return (
            any(token in lowered_scene_text for token in ["airport", "terminal", "travel", "flight", "layover", "boarding"])
            and any(token in lowered_scene_text for token in ["walking", "walk", "stroll", "moving through", "crossing"])
            and any(token in lowered_scene_text for token in ["luggage", "suitcase", "carry-on", "carry on", "roller bag", "shoulder bag"])
        )

    @staticmethod
    def _scene_tag_prefix(scene_tags: List[str]) -> str:
        for tag in scene_tags:
            lowered = tag.lower()
            if "off-duty crew member between flights" in lowered:
                return "Off-duty flight attendant between flights"
            if "off-duty crew member" in lowered:
                return "Off-duty flight attendant"
        return ""

    @staticmethod
    def _compose_scene_line(scene_line: str, scene_tags: List[str]) -> str:
        clean_tags = [tag.strip() for tag in scene_tags if tag.strip()]
        if not clean_tags:
            return scene_line
        return ", ".join([scene_line] + clean_tags[:4])

    @staticmethod
    def _compress_identity_anchor(identity_anchor: str) -> str:
        text = identity_anchor.replace("stable identity anchor: ", "")
        text = text.replace("recurring same woman; ", "")
        text = text.replace("preserve same face geometry and recognizable proportions across generations.", "recognizable face geometry across generations")
        return text

    @staticmethod
    def _compress_body_anchor(body_anchor: str, shot_archetype: str) -> str:
        text = body_anchor.replace("body consistency anchor: ", "")
        text = text.replace("preferred_reference=", "reference=")
        if shot_archetype == "full_body":
            return text.replace("full-body framing keeps ", "full-body consistency, ")
        return text

    @staticmethod
    def _compress_continuity(continuity_block: str) -> str:
        text = continuity_block.replace("continuity: ", "")
        text = text.replace("hint=", "")
        return f"continuity hint: {text}"

    @staticmethod
    def _compress_device_identity(device_identity: str) -> str:
        return device_identity.replace("capture chain consistent with ", "")

    @staticmethod
    def _compact_identity_signature(identity_anchor: str) -> str:
        values = {}
        for chunk in identity_anchor.replace("stable identity anchor: ", "").split(";"):
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            values[key.strip()] = value.strip()
        summary = [
            f"age={values.get('age', '22')}",
            f"face={values.get('face', 'soft oval')}",
            f"eyes={values.get('eyes', 'calm almond eyes')}",
            f"hair={values.get('hair', 'light chestnut medium-length hair')}",
            f"makeup={values.get('makeup', 'soft everyday makeup')}",
        ]
        return "; ".join(summary)

    @staticmethod
    def _compact_continuity_hint(continuity_block: str) -> str:
        lowered = continuity_block.replace("continuity: ", "")
        for token in ["arc=", "hint=", "previous_evening=", "signature="]:
            lowered = lowered.replace(token, "")
        parts = [part.strip() for part in lowered.split(";") if part.strip()]
        return f"continuity: {'; '.join(parts[:2])}"

    BANNED_SYNTHETIC_PATTERNS: tuple[str, ...] = (
        "beautiful young woman",
        "photorealistic 8k",
        "8k",
        "highly detailed",
        "stunning beauty",
        "flawless skin",
        "fashion magazine vibe",
        "editorial glamour",
        "studio-level symmetry",
        "luxury campaign tone",
        "pristine environment",
        "perfect lighting",
        "fashion model pose",
        "editorial fashion shoot",
        "microscopic details",
        "perfect composition",
        "cinematic lighting",
        "hyper-detailed beauty",
        "editorial symmetry",
    )



