from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Dict, List, Mapping

from virtual_persona.pipeline.identity import CharacterIdentityManager
from virtual_persona.pipeline.outfit_generator import ManualOutfitValidationError, OutfitBundle, OutfitGenerationError, OutfitGenerator


class PromptValidationError(ValueError):
    pass


@dataclass
class PromptComposer:
    state_store: Any
    CANONICAL_PROMPT_VERSION = "v6"
    COMPACT_PROMPT_THRESHOLD = 740
    DENSE_PROMPT_MIN_LENGTH = 728
    DENSE_PROMPT_EXPANDED_BLOCKS = 4
    EXPANDED_BLOCK_BODY_THRESHOLD = 28
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
        outfit_bundle = self._resolve_outfit_bundle(context, scene, outfit_summary)
        normalized_outfit = outfit_bundle.outfit_sentence or outfit_bundle.sentence
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
            "outfit_sentence": normalized_outfit,
            "outfit_summary": normalized_outfit,
            "camera_block": camera_block,
            "realism_block": realism_block,
            "continuity_block": continuity_block,
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

        final_prompt = self._build_final_prompt(
            prompt_mode=prompt_mode,
            identity_anchor=identity_anchor,
            body_anchor=body_anchor,
            framing_mode=framing_mode,
            context=context,
            shot_archetype=shot_archetype,
            scene=scene,
            scene_desc=scene_desc,
            scene_loc=scene_loc,
            outfit_sentence=normalized_outfit,
            realism_block=realism_block,
            continuity_block=continuity_block,
            device_identity=ordered_blocks["device_identity"],
            social_behavior=ordered_blocks["social_behavior"],
            scene_tags=scene_alignment.get("scene_tags", []),
        )
        prompt_mode = self._prompt_mode(final_prompt)
        ordered_blocks["final_prompt"] = final_prompt
        ordered_blocks["prompt_format_version"] = self.CANONICAL_PROMPT_VERSION
        ordered_blocks["shot_archetype"] = shot_archetype
        ordered_blocks["platform_behavior"] = platform_behavior
        ordered_blocks["generation_mode"] = generation_mode
        ordered_blocks["framing_mode"] = framing_mode
        ordered_blocks["reference_type"] = str(reference_selection.get("requested_type", ""))
        ordered_blocks["primary_anchors"] = primary_anchors
        ordered_blocks["secondary_anchors"] = secondary_anchors
        ordered_blocks["manual_generation_step"] = manual_step
        ordered_blocks["prompt_mode"] = prompt_mode
        return ordered_blocks

    @staticmethod
    def _prompt_mode(prompt: str) -> str:
        normalized = (prompt or "").strip()
        blocks = [block.strip() for block in normalized.split("\n\n") if block.strip()]
        framing_block = blocks[1].lower() if len(blocks) > 1 else ""
        if len(normalized) > PromptComposer.COMPACT_PROMPT_THRESHOLD:
            return "dense"
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

        if len(normalized) >= PromptComposer.DENSE_PROMPT_MIN_LENGTH and expanded_blocks >= PromptComposer.DENSE_PROMPT_EXPANDED_BLOCKS:
            return "dense"
        if "selfie" in framing_block and len(normalized) < 1000:
            return "compact"
        return "compact"

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
        is_travel = any(token in lowered for token in ["airport", "terminal", "travel", "flight", "layover", "boarding"])
        has_luggage = any(token in lowered for token in ["luggage", "suitcase", "carry-on", "carry on", "roller bag", "shoulder bag"])
        is_walking = any(token in lowered for token in ["walking", "walk", "stroll", "moving through", "crossing"])
        is_seated = any(token in lowered for token in ["seated", "sitting", "table", "coffee", "window seat", "waiting"])
        is_selfie = (
            "selfie" in lowered_core
            or "mirror" in lowered_core
            or (lowered_moment_type in {"selfie", "diary_mirror"} and not (is_travel and is_walking and has_luggage))
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

    def _resolve_outfit_bundle(self, context: Dict[str, Any], scene: Any, outfit_summary: str) -> OutfitBundle:
        manual_override = self.outfit_generator._resolve_manual_override(scene, context)
        canonical_sentence = self._clean_fragment(str(context.get("outfit_sentence") or ""))
        canonical_struct = self._coerce_outfit_struct(context.get("outfit_struct"), context.get("outfit_struct_json"))

        if manual_override:
            return self._generate_outfit_bundle(context, scene, outfit_summary)

        if canonical_sentence:
            try:
                return self._bundle_from_canonical_sentence(
                    canonical_sentence,
                    canonical_struct,
                    scene=scene,
                    context=context,
                    fallback_summary=outfit_summary,
                )
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
                    )
                except PromptValidationError:
                    pass

        return self._generate_outfit_bundle(context, scene, outfit_summary)

    def _generate_outfit_bundle(self, context: Dict[str, Any], scene: Any, outfit_summary: str) -> OutfitBundle:
        try:
            bundle = self.outfit_generator.generate_bundle(outfit_summary=outfit_summary, scene=scene, context=context)
        except ManualOutfitValidationError as exc:
            raise PromptValidationError(str(exc)) from exc
        except OutfitGenerationError:
            fallback_outfit = self.generate_default_outfit(
                scene,
                str(context.get("city", "") or ""),
                context.get("weather"),
                day_type=str(context.get("day_type", "") or ""),
                behavior_mode=str(
                    getattr(context.get("behavioral_context"), "outfit_behavior_mode", "")
                    or getattr(context.get("behavioral_context"), "self_presentation", "")
                    or getattr(getattr(context.get("behavioral_context"), "daily_state", None), "self_presentation_mode", "")
                    or ""
                ),
            )
            try:
                bundle = self.outfit_generator.generate_bundle(
                    outfit_summary=", ".join(fallback_outfit),
                    scene=scene,
                    context=context,
                )
            except (ManualOutfitValidationError, OutfitGenerationError) as exc:
                raise PromptValidationError("Outfit validation failed after fallback recovery") from exc
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
            regenerated = self._generate_outfit_bundle(context, scene, fallback_summary)
            return regenerated
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
        clothing_text, _, detail_text = outfit_sentence.partition(";")
        pieces = []
        for chunk in re.split(r"\s*(?:,| and )\s*", clothing_text):
            cleaned = self._clean_fragment(chunk)
            if cleaned:
                pieces.append(cleaned)

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

        detail_parts = [self._clean_fragment(chunk) for chunk in detail_text.split(",") if self._clean_fragment(chunk)]
        for detail in detail_parts:
            lowered = detail.lower()
            if not payload["fit"] and any(token in lowered for token in ["fit", "fitted", "relaxed", "silhouette", "drape"]):
                payload["fit"] = detail
            elif not payload["fabric"] and any(token in lowered for token in ["fabric", "fabrics", "texture", "textures", "matte", "cotton", "knit", "linen", "wool"]):
                payload["fabric"] = detail
            elif not payload["condition"] and any(token in lowered for token in ["fold", "folds", "worn", "wrinkle", "wrinkles", "crease", "creases", "bunching"]):
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
            "generic model photo", "fashion catalog symmetry", "sterile beauty campaign polish", "wrong phone shape",
            "identity drift", "unstable face geometry", "inconsistent body proportions",
            "fashion catalog outfit", "perfect styling", "overly trendy outfit", "runway fashion",
            "influencer outfit", "studio fashion look", "over-coordinated clothing", "impractical clothing for context",
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
        return "forbid generic AI wording and campaign aesthetics: no fashion catalog mood, no sterile luxury vibe, no editorial over-posing."

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
    ) -> str:
        del prompt_mode, device_identity, social_behavior

        identity_block = self._identity_block(identity_anchor=identity_anchor, body_anchor=body_anchor)
        framing_block = self._framing_block(framing_mode, shot_archetype, scene)
        scene_block = self._scene_block(context, scene, scene_desc, scene_loc, scene_tags)
        outfit_block = self._outfit_block(outfit_sentence)
        environment_block = self._environment_block(context, scene, scene_loc, scene_tags, continuity_block)
        mood_block = self._mood_block(context, scene, continuity_block)

        blocks = [
            identity_block,
            framing_block,
            scene_block,
            outfit_block,
            environment_block,
            mood_block,
        ]
        prompt = "\n\n".join(block.strip() for block in blocks if block.strip())
        self._validate_canonical_prompt(prompt, scene, context)
        return prompt

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

    def _framing_block(self, framing_mode: str, shot_archetype: str, scene: Any) -> str:
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
        return canonical.get(shot_archetype, "candid 3/4 body shot")

    def _scene_block(self, context: Dict[str, Any], scene: Any, scene_desc: str, scene_loc: str, scene_tags: List[str]) -> str:
        lowered = self._scene_text(scene).lower()
        visual_focus = self._strip_scene_noise(str(getattr(scene, "visual_focus", "") or "").strip())
        tag_prefix = self._scene_tag_prefix(scene_tags)
        behavior = context.get("behavioral_context")
        object_terms = self._behavior_object_terms(context)
        movement, interaction, expression = self._behavior_scene_cues(context, scene)
        micro_detail = self._scene_micro_detail(scene, behavior, object_terms, visual_focus)
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
            for object_term in object_terms:
                if object_term.lower() not in " ".join(pieces).lower():
                    pieces.append(self._object_scene_phrase(object_term, scene))
            return f"Scene: {', '.join(self._dedupe_phrases(pieces))}."

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
        for object_term in object_terms:
            if object_term.lower() not in " ".join(pieces).lower():
                pieces.append(self._object_scene_phrase(object_term, scene))
        return f"Scene: {', '.join(self._dedupe_phrases(pieces))}."

    def _outfit_block(self, outfit_sentence: str) -> str:
        cleaned = self.validate_outfit_sentence(outfit_sentence)
        return f"Outfit: {cleaned}."

    def _environment_block(self, context: Dict[str, Any], scene: Any, scene_loc: str, scene_tags: List[str], continuity_block: str) -> str:
        del continuity_block, scene_tags
        lighting = self._lighting_hint(getattr(scene, "time_of_day", "day"))
        lowered_loc = str(scene_loc or "").lower()
        location_phrase = "airport terminal" if any(token in lowered_loc for token in ["airport", "terminal"]) else self._clean_fragment(scene_loc)
        behavior = context.get("behavioral_context")
        parts: List[str] = [
            f"Environment: photorealistic {location_phrase}",
            "physically plausible spatial depth",
            "accurate perspective and scale",
            f"{lighting} behaving as natural available light",
        ]
        if any(token in lowered_loc for token in ["airport", "terminal"]):
            parts.insert(1, "real terminal architecture")
        else:
            parts.insert(1, "lived-in environmental detail")
        if behavior is not None:
            presence = {
                "alone": "no other people in frame",
                "light_public": "soft background people only",
                "social": "public life present but secondary",
            }.get(str(getattr(behavior, "social_mode", "alone") or "alone"), "")
            if presence:
                parts.append(presence)
        return f"{'; '.join(self._dedupe_phrases(parts))}."

    def _mood_block(self, context: Dict[str, Any], scene: Any, continuity_block: str) -> str:
        del continuity_block
        mood = str(getattr(scene, "mood", "") or "").strip().lower()
        behavior = context.get("behavioral_context")
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
            if arc_mood:
                details.append(arc_mood)
            if self_presentation:
                details.append(f"{self_presentation} self-presentation")
            return f"Mood: {', '.join(self._dedupe_phrases(details))}."
        return f"Mood: {base}."

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

    def _has_duplicate_clauses(self, prompt: str) -> bool:
        seen: set[str] = set()
        for block in [block.strip() for block in prompt.split("\n\n") if block.strip()]:
            _, _, body = block.partition(":")
            chunks = re.split(r"\s*[;,]\s*", body or block)
            for chunk in chunks:
                key = self._normalize_phrase_key(chunk)
                if not key:
                    continue
                if key in seen:
                    return True
                seen.add(key)
        return False

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
        if any(struct.get(key) for key in ("accessories",)) or any(token in lowered for token in ["bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "belt", "carry on"]):
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
        cleaned_sentence = cls.validate_outfit_sentence(outfit_sentence)
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
        return {"carry_on": "carry on", "coffee_cup": "coffee cup"}.get(str(obj or "").strip().lower(), str(obj or "").replace("_", " ").strip())

    def _behavior_object_terms(self, context: Dict[str, Any]) -> List[str]:
        behavior = context.get("behavioral_context")
        if behavior is None:
            return []
        objects = getattr(behavior, "objects", getattr(behavior, "recurring_objects", [])) or []
        return [self._natural_object_term(obj) for obj in objects if self._natural_object_term(obj)]

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
        if "focused" in str(getattr(scene, "mood", "") or "").lower() and not expression:
            expression = "minimal facial expression with inward attention"
        return movement, interaction, expression

    def _scene_micro_detail(self, scene: Any, behavior: Any, object_terms: List[str], visual_focus: str) -> str:
        del behavior
        lowered = self._scene_text(scene).lower()
        if any(token in lowered for token in ["terminal", "airport", "gate", "boarding"]) and "waiting" in lowered:
            if "window" in lowered:
                return "seated near window row seating and checking the boarding screen occasionally"
            return "checking the boarding screen occasionally near the gate seating"
        if visual_focus:
            return f"small detail: {visual_focus}"
        if object_terms:
            return f"small detail: {object_terms[0]} kept close"
        return "small detail: lived-in candid timing"

    @staticmethod
    def _object_scene_phrase(object_term: str, scene: Any) -> str:
        lowered = PromptComposer._scene_text(scene).lower()
        mapping = {
            "coffee cup": "coffee cup in hand",
            "carry on": "carry on placed nearby",
            "bag": "bag resting beside her",
        }
        if object_term == "carry on" and any(token in lowered for token in ["walking", "walk", "stroll", "moving through"]):
            return "carry on rolling alongside her"
        return mapping.get(object_term, f"{object_term} visible in the scene")

    def _validate_canonical_prompt(self, prompt: str, scene: Any, context: Dict[str, Any]) -> None:
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

        if self._has_duplicate_clauses(prompt):
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

        required_objects = self._behavior_object_terms(context)
        for object_term in required_objects:
            if object_term and object_term.lower() not in lowered:
                raise PromptValidationError(f"Required object missing from prompt: {object_term}")

        if re.search(r"\b([a-z]+)(?:\s+\1\b)+", lowered):
            raise PromptValidationError("Duplicate word sequence detected in canonical prompt.")

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
        "fashion catalog",
        "cinematic lighting",
        "hyper-detailed beauty",
        "editorial symmetry",
    )



