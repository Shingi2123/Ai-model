from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from virtual_persona.pipeline.identity import CharacterIdentityManager


@dataclass
class PromptComposer:
    state_store: Any

    CAMERA_ARCHETYPES: Dict[str, Dict[str, str]] = None  # type: ignore[assignment]
    GENERATION_MODE_REGISTRY: Dict[str, Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
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
        prompt_mode = self._prompt_mode(shot_archetype, content_type, getattr(scene, "scene_moment", ""))
        framing_mode = str(scene_alignment["framing_mode"])

        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_desc = getattr(scene, "scene_moment", "") or getattr(scene, "description", "daily lifestyle moment")
        item_ids_text = ", ".join(outfit_item_ids or [])
        reference_selection = identity_manager.select_reference_bundle(shot_archetype, generation_mode, identity_pack)

        identity_anchor = identity_manager.identity_anchor(context, identity_pack)
        body_anchor_shot = "full_body" if generation_mode == "full-body_mode" and shot_archetype == "friend_shot" else shot_archetype
        body_anchor = identity_manager.body_anchor(body_anchor_shot, context, identity_pack)
        scene_action = self._scene_action(scene, scene_desc, scene_loc)
        wardrobe_block = self._wardrobe_context(outfit_summary, shot_archetype, item_ids_text)
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
        }

        prefix = blocks.get("prompt_v2_prefix", "Prompt System v5")
        final_prompt = self._build_final_prompt(
            prefix=prefix,
            prompt_mode=prompt_mode,
            identity_anchor=identity_anchor,
            body_anchor=body_anchor,
            framing_mode=framing_mode,
            shot_archetype=shot_archetype,
            scene=scene,
            scene_desc=scene_desc,
            scene_loc=scene_loc,
            wardrobe_block=wardrobe_block,
            realism_block=realism_block,
            continuity_block=continuity_block,
            device_identity=ordered_blocks["device_identity"],
            social_behavior=ordered_blocks["social_behavior"],
            scene_tags=scene_alignment.get("scene_tags", []),
        )
        ordered_blocks["final_prompt"] = self._clean_generic_prompt_terms(final_prompt)
        ordered_blocks["shot_archetype"] = shot_archetype
        ordered_blocks["platform_behavior"] = platform_behavior
        ordered_blocks["generation_mode"] = generation_mode
        ordered_blocks["framing_mode"] = framing_mode
        ordered_blocks["reference_type"] = str(reference_selection.get("requested_type", ""))
        ordered_blocks["primary_anchors"] = primary_anchors
        ordered_blocks["secondary_anchors"] = secondary_anchors
        ordered_blocks["manual_generation_step"] = manual_step
        return ordered_blocks

    @staticmethod
    def _prompt_mode(shot_archetype: str, content_type: str, scene_text: str) -> str:
        simple_shots = {"front_selfie", "mirror_selfie", "close_portrait", "waist_up", "seated_table_shot"}
        simple_tokens = {"selfie", "portrait", "coffee", "airport", "seated", "waiting"}
        lowered = str(scene_text or "").lower()
        is_simple_scene = len(lowered.split()) < 14 or any(token in lowered for token in simple_tokens)
        if shot_archetype in simple_shots and content_type in {"photo", "story", "stories"} and is_simple_scene:
            return "compact"
        return "dense"

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
            return "friend-shot, 3/4 body walking candid with luggage visible"
        if generation_mode == "full-body_mode" and shot_archetype in {"friend_shot", "candid_handheld"}:
            return "3/4 body candid with full stance readable"
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
        if is_travel and not is_uniform:
            if any(token in lowered_scene_text for token in ["layover", "between flights", "between-flight"]):
                tags.append("off-duty crew member between flights in a casual travel look")
            else:
                tags.append("off-duty crew member in a casual layover travel look")
        if shot_archetype in {"friend_shot", "full_body", "candid_handheld"} and any(
            token in lowered_scene_text for token in ["luggage", "suitcase", "carry-on", "carry on"]
        ):
            tags.append("carry-on luggage stays visible in frame")
        if any(token in lowered_scene_text for token in ["terminal", "airport"]):
            tags.append("real terminal depth with soft reflections and passing travelers")
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
    def _wardrobe_context(outfit_summary: str, shot_archetype: str, outfit_item_ids: str) -> str:
        visible_scope = "upper-body focus" if shot_archetype in {"front_selfie", "close_portrait", "mirror_selfie", "seated_table_shot", "waist_up"} else "full outfit coherence"
        return f"outfit: {outfit_summary}; {visible_scope}; item_ids={outfit_item_ids}."

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
        return " ".join(cleaned.split())

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
        prefix: str,
        prompt_mode: str,
        identity_anchor: str,
        body_anchor: str,
        framing_mode: str,
        shot_archetype: str,
        scene: Any,
        scene_desc: str,
        scene_loc: str,
        wardrobe_block: str,
        realism_block: str,
        continuity_block: str,
        device_identity: str,
        social_behavior: str,
        scene_tags: List[str],
    ) -> str:
        lighting = self._lighting_hint(getattr(scene, "time_of_day", "day"))
        visual_focus = str(getattr(scene, "visual_focus", "") or "").strip()
        mood = str(getattr(scene, "mood", "") or "").strip()
        action = str(getattr(scene, "activity", "") or "").strip()
        scene_line = f"{scene_desc} in {scene_loc}"
        if action:
            scene_line += f", {action}"
        if visual_focus:
            scene_line += f", {visual_focus}"
        if mood:
            scene_line += f", facial mood {mood}"

        compact_parts = [
            f"{prefix}: same recurring woman, stable face geometry, same body proportions",
            self._compress_identity_anchor(identity_anchor),
            self._compress_body_anchor(body_anchor, shot_archetype),
            f"{framing_mode}; {shot_archetype}",
            self._compose_scene_line(scene_line, scene_tags),
            wardrobe_block.replace("outfit: ", "").replace("item_ids=", "items="),
            f"lived-in environment, {lighting}",
            "natural smartphone photo, candid realism, natural skin texture, real fabric folds, grounded lifestyle styling",
            self._compress_continuity(continuity_block),
        ]
        dense_parts = compact_parts[:]
        dense_parts.insert(5, self._compress_device_identity(device_identity))
        dense_parts.insert(6, social_behavior)
        dense_parts.insert(7, realism_block.replace("realism: ", "").rstrip("."))
        parts = compact_parts if prompt_mode == "compact" else dense_parts
        return ". ".join(part.strip().rstrip(".") for part in parts if part.strip()) + "."

    @staticmethod
    def _compose_scene_line(scene_line: str, scene_tags: List[str]) -> str:
        clean_tags = [tag.strip() for tag in scene_tags if tag.strip()]
        if not clean_tags:
            return scene_line
        return ", ".join([scene_line] + clean_tags[:2])

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



