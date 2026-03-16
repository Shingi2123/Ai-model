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
                "front_selfie": {"perspective": "front phone camera perspective", "framing": "head-and-shoulders", "device": "smartphone handheld"},
                "mirror_selfie": {"perspective": "mirror reflection perspective", "framing": "phone visible in reflection", "device": "mirror geometry consistent"},
                "candid_handheld": {"perspective": "observer handheld perspective", "framing": "off-center candid", "device": "consumer smartphone"},
                "friend_shot": {"perspective": "friend-shot social distance", "framing": "natural social framing", "device": "consumer smartphone"},
                "close_portrait": {"perspective": "tight close portrait", "framing": "face dominant", "device": "real lens behavior"},
                "seated_table_shot": {"perspective": "seated eye-level", "framing": "mid-shot with table context", "device": "lifestyle available light"},
                "full_body": {"perspective": "full body eye-level", "framing": "head-to-toe", "device": "realistic smartphone lens"},
                "waist_up": {"perspective": "waist-up framing", "framing": "torso centered with environment", "device": "natural handheld"},
            }
        if self.GENERATION_MODE_REGISTRY is None:
            self.GENERATION_MODE_REGISTRY = {
                "portrait_mode": {"shot_archetypes": ["close_portrait", "front_selfie"], "negative": ["wax skin", "beauty filter"]},
                "waist-up_mode": {"shot_archetypes": ["waist_up", "seated_table_shot"], "negative": ["broken torso proportions"]},
                "seated_lifestyle_mode": {"shot_archetypes": ["seated_table_shot"], "negative": ["impossible seated geometry", "feet on table unless explicitly requested"]},
                "full-body_mode": {"shot_archetypes": ["full_body", "friend_shot"], "negative": ["floating shoe", "broken ankle angle"]},
                "selfie_mode": {"shot_archetypes": ["front_selfie"], "negative": ["rear-camera perspective"]},
                "mirror_selfie_mode": {"shot_archetypes": ["mirror_selfie"], "negative": ["broken mirror reflection", "floating phone"]},
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
        platform_behavior = self._platform_behavior_intent(content_type, platform_intent)
        profile = context.get("character_profile") or {}
        identity_manager = CharacterIdentityManager()
        identity_pack = identity_manager.load_pack()
        prompt_mode = self._prompt_mode(shot_archetype, content_type, getattr(scene, "scene_moment", ""))

        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_desc = getattr(scene, "scene_moment", "") or getattr(scene, "description", "daily lifestyle moment")
        item_ids_text = ", ".join(outfit_item_ids or [])

        identity_anchor = identity_manager.identity_anchor(context, identity_pack)
        body_anchor = identity_manager.body_anchor(shot_archetype, context, identity_pack)
        scene_action = f"scene action: {scene_desc}; location={scene_loc}; activity={getattr(scene, 'activity', '')}; mood={getattr(scene, 'mood', '')}."
        wardrobe_block = self._wardrobe_context(outfit_summary, shot_archetype, item_ids_text)
        camera_block = self._camera_context(shot_archetype, context)
        realism_block = self._realism_cues(shot_archetype, scene_loc)
        continuity_block = self._continuity_cues(context, scene)
        platform_block = self._platform_intent(context, content_type, platform_intent, platform_behavior)
        negative_prompt = self._negative_prompt(shot_archetype, scene_loc, platform_behavior, generation_mode)
        reference_bundle = self._reference_bundle(identity_pack, shot_archetype)

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
            "reference_bundle": reference_bundle,
            "life_continuity_context": continuity_block,
            "scene_context": scene_action,
            "wardrobe_context": wardrobe_block,
            "camera_context": camera_block,
            "framing_style": "imperfect framing, real handheld balance",
            "camera_physics": "handheld motion with gravity-consistent body pose",
            "sensor_realism": "smartphone dynamic range with mild grain in low light",
            "smartphone_behavior": "natural smartphone photo, candid realism, no studio perfection",
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
            "persona_voice_cues": f"voice restraint={profile.get('voice_restrain', 'medium')}",
            "negative_prompt": negative_prompt,
            "video_motion": "subtle body movement with stable identity",
            "video_camera_motion": "light handheld or slow tripod drift",
        }

        prefix = blocks.get("prompt_v2_prefix", "Prompt System v4")
        include_negative_prompt = content_type.lower() in {"photo", "carousel", "video", "reel", "story", "stories"}
        final_prompt = (
            f"{prefix}: "
            + " ".join(
                f"[{k}] {v}"
                for k, v in ordered_blocks.items()
                if k
                in {
                    "identity_anchor",
                    "body_anchor",
                    "scene_action",
                    "wardrobe_block",
                    "camera_block",
                    "realism_block",
                    "continuity_block",
                    "platform_intent",
                    "prompt_mode",
                    "generation_mode",
                    "reference_bundle",
                    "face_consistency",
                    "social_behavior",
                }
            )
            + (f" [negative_prompt] {negative_prompt}" if include_negative_prompt else "")
        )
        final_prompt = self._clean_generic_prompt_terms(final_prompt)
        ordered_blocks["final_prompt"] = final_prompt
        ordered_blocks["shot_archetype"] = shot_archetype
        ordered_blocks["platform_behavior"] = platform_behavior
        return ordered_blocks

    @staticmethod
    def _prompt_mode(shot_archetype: str, content_type: str, scene_text: str) -> str:
        simple = shot_archetype in {"front_selfie", "mirror_selfie", "close_portrait"} and content_type in {"photo", "story"}
        simple = simple and len(str(scene_text or "").split()) < 12
        return "compact" if simple else "dense"

    def _resolve_generation_mode(self, scene: Any, shot_archetype: str) -> str:
        explicit = getattr(scene, "generation_mode", "")
        if explicit and explicit in self.GENERATION_MODE_REGISTRY:
            return explicit
        for mode, cfg in self.GENERATION_MODE_REGISTRY.items():
            if shot_archetype in cfg.get("shot_archetypes", []):
                return mode
        return "portrait_mode"

    @staticmethod
    def _reference_bundle(identity_pack: Any, shot_archetype: str) -> str:
        refs = identity_pack.references if identity_pack else {}
        preferred = "face_reference"
        if shot_archetype in {"seated_table_shot", "waist_up"}:
            preferred = "half_body_reference"
        if shot_archetype in {"full_body", "friend_shot", "candid_handheld"}:
            preferred = "full_body_reference"
        selected = refs.get(preferred) or refs.get("face_reference") or "fallback_character_dna"
        return f"preferred={preferred}; selected={selected}; pack_ready={getattr(identity_pack, 'ready', False)}"

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
        visible_scope = "upper-body focus" if shot_archetype in {"front_selfie", "close_portrait", "mirror_selfie", "seated_table_shot"} else "full outfit coherence"
        return f"wardrobe: {outfit_summary}; {visible_scope}; item_ids={outfit_item_ids}."

    def _camera_context(self, shot_archetype: str, context: Dict[str, Any]) -> str:
        camera_profile = self.CAMERA_ARCHETYPES.get(shot_archetype, self.CAMERA_ARCHETYPES["friend_shot"])
        device_profile = self._primary_device_profile(context)
        return (
            f"{camera_profile['perspective']}; {camera_profile['framing']}; {camera_profile['device']}; "
            f"{self._device_profile(device_profile, shot_archetype)}"
        )

    @staticmethod
    def _primary_device_profile(context: Dict[str, Any]) -> Dict[str, str]:
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
            f"realism: natural smartphone photo, candid realism, imperfect framing, real home light, lived-in environment, natural posture; "
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

    def _negative_prompt(self, shot_archetype: str, scene_loc: str, platform_behavior: str, generation_mode: str) -> str:
        universal = [
            "extra fingers", "deformed hands", "duplicate person", "plastic skin", "bad anatomy", "wrong limb placement",
            "generic model photo", "fashion catalog symmetry", "sterile beauty campaign polish", "wrong phone shape",
        ]
        shot_specific = {
            "mirror_selfie": ["wrong reflection", "floating phone", "impossible reflection geometry"],
            "front_selfie": ["rear-camera perspective", "detached floating arm"],
            "seated_table_shot": ["impossible seated geometry", "feet on table unless explicitly requested", "broken ankle angle", "floating shoe"],
            "full_body": ["broken body proportions", "misaligned shoes"],
        }
        location_specific: List[str] = []
        loc = scene_loc.lower()
        if "kitchen" in loc:
            location_specific.extend(["broken mug handle", "impossible cup grip"])
        if "street" in loc or "city" in loc:
            location_specific.append("impossible pedestrian scale")
        mode_negative = self.GENERATION_MODE_REGISTRY.get(generation_mode, {}).get("negative", [])
        platform_negative = ["overproduced ad lighting"] if platform_behavior == "story_lifestyle" else []
        return ", ".join(universal + shot_specific.get(shot_archetype, []) + location_specific + platform_negative + mode_negative)

    @staticmethod
    def _continuity_cues(context: Dict[str, Any], scene: Any) -> str:
        continuity = context.get("continuity_context") or {}
        arc = continuity.get("arc_hint", "stable_routine")
        hint = "steady day-to-day continuity"
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
        base = ["slightly shifted chair angle", "book or notebook not perfectly centered", "blanket or coat crease consistent with recent use"]
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
        favorites = [x.strip() for x in str(profile.get("favorite_locations") or "kitchen window corner, favorite café table").split(",") if x.strip()]
        recurring = [x.strip() for x in str(profile.get("recurring_spaces") or "living room sofa, hallway mirror").split(",") if x.strip()]
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
        if "table" in text or "coffee" in text:
            return "seated_table_shot"
        if "full body" in text or "full-body" in text:
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
