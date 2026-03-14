from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PromptComposer:
    state_store: Any

    CAMERA_ARCHETYPES: Dict[str, Dict[str, str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.CAMERA_ARCHETYPES is None:
            self.CAMERA_ARCHETYPES = {
                "front_selfie": {
                    "perspective": "front phone camera perspective, arm-length framing, subtle lens distortion near edges",
                    "framing": "upper torso or head-and-shoulders crop, imperfect but natural alignment",
                    "device": "smartphone-origin realism, handheld micro-movement feel",
                },
                "mirror_selfie": {
                    "perspective": "mirror reflection perspective, camera looking into mirror",
                    "framing": "phone visible in reflection, one hand holding phone, practical bathroom/room mirror framing",
                    "device": "phone model consistency in reflection, believable mirror geometry",
                },
                "candid_handheld": {
                    "perspective": "handheld documentary perspective, observer at human eye level",
                    "framing": "slightly off-center candid crop, natural motion imperfections",
                    "device": "street-level smartphone camera realism, non-studio rendering",
                },
                "candid_observer": {
                    "perspective": "captured from nearby observer distance, unposed interaction",
                    "framing": "asymmetric candid composition, environmental context visible",
                    "device": "natural capture feel, no studio or catalog perfection",
                },
                "tripod_photo": {
                    "perspective": "fixed tripod perspective with realistic focal distance",
                    "framing": "balanced full-body or 3/4 framing with visible environment depth",
                    "device": "phone or compact camera timer-shot realism",
                },
                "friend_shot": {
                    "perspective": "shot by a friend from conversational distance",
                    "framing": "natural social framing, slight perspective drift, lived-in scene blocking",
                    "device": "consumer smartphone realism, authentic skin and texture response",
                },
                "close_portrait": {
                    "perspective": "tight close portrait perspective with shallow but realistic depth",
                    "framing": "face-dominant frame, neck and shoulders partially visible",
                    "device": "real lens behavior, natural skin detail and pores",
                },
                "seated_table_shot": {
                    "perspective": "seated eye-level perspective across table or at slight side angle",
                    "framing": "mid-shot with tabletop context and hands interacting with objects",
                    "device": "lifestyle café realism, practical available light",
                },
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

    def compose(
        self,
        context: Dict[str, Any],
        scene: Any,
        outfit_summary: str,
        content_type: str,
        outfit_item_ids: List[str] | None = None,
        platform_intent: str | None = None,
    ) -> str:
        return self.compose_package(
            context=context,
            scene=scene,
            outfit_summary=outfit_summary,
            content_type=content_type,
            outfit_item_ids=outfit_item_ids,
            platform_intent=platform_intent,
        )["final_prompt"]

    def compose_package(
        self,
        context: Dict[str, Any],
        scene: Any,
        outfit_summary: str,
        content_type: str,
        outfit_item_ids: List[str] | None = None,
        platform_intent: str | None = None,
    ) -> Dict[str, str]:
        blocks = self.load_blocks()
        continuity = context.get("continuity_context") or {}
        recent_moment_memory = context.get("recent_moment_memory") or []
        persona_voice = context.get("persona_voice") or {}
        shot_archetype = self._resolve_shot_archetype(scene)
        platform_behavior = self._platform_behavior_intent(content_type, platform_intent)
        camera_profile = self.CAMERA_ARCHETYPES.get(shot_archetype, self.CAMERA_ARCHETYPES["friend_shot"])

        item_ids_text = ", ".join(outfit_item_ids or [])
        scene_loc = getattr(scene, "location", context.get("city", "city"))
        scene_desc = getattr(scene, "scene_moment", "") or getattr(scene, "description", "daily lifestyle moment")
        time_of_day = getattr(scene, "time_of_day", "day")

        identity_core = self._identity_core(context)
        life_continuity_context = (
            f"day_type={getattr(context.get('life_state'), 'day_type', context.get('day_type', 'daily_life'))}; "
            f"season={getattr(context.get('life_state'), 'season', 'all-season')}; "
            f"fatigue={getattr(context.get('life_state'), 'fatigue_level', 4)}/10; "
            f"arc_hint={continuity.get('arc_hint', 'stable_routine')}; previous_evening={continuity.get('previous_evening_moment', '')}."
        )
        scene_context = (
            f"{scene_desc}; location={scene_loc}, city={context.get('city')}, activity={getattr(scene, 'activity', '')}, "
            f"mood={getattr(scene, 'mood', 'calm')}, time_of_day={time_of_day}, visual_focus={getattr(scene, 'visual_focus', '')}."
        )
        wardrobe_context = self._wardrobe_context(outfit_summary, shot_archetype, item_ids_text)
        camera_context = (
            f"camera_archetype={shot_archetype}; perspective={camera_profile['perspective']}; "
            f"framing={camera_profile['framing']}; device_realism={camera_profile['device']}; {self._device_profile(context)}"
        )
        camera_behavior_memory = self._camera_behavior_memory(shot_archetype, continuity, recent_moment_memory)
        camera_physics = self._camera_physics_layer(shot_archetype, scene_loc)
        sensor_realism = self._sensor_realism_layer(time_of_day, scene_loc)
        smartphone_behavior = self._smartphone_behavior_layer(scene_loc, time_of_day)
        micro_imperfections = self._micro_imperfections_layer(shot_archetype, platform_behavior)
        face_consistency = self._face_consistency_layer(context)
        device_identity = self._device_identity_layer(shot_archetype, context, platform_behavior)
        favorite_location_memory = self._favorite_location_memory_layer(context, scene_loc)
        platform_intent_block = self._platform_intent(context, content_type, platform_intent, platform_behavior)
        composition_and_lighting = (
            f"composition: layered foreground/background, believable depth, no studio symmetry. "
            f"lighting: {self._lighting_hint(time_of_day)} with natural exposure and practical light sources."
        )
        realism_cues = (
            "realism: natural skin texture with pores, subtle under-eye detail, realistic fabric folds, "
            "coherent city/background geometry, grounded body language and hand placement."
        )
        continuity_cues = self._continuity_cues(context, scene)
        persona_voice_cues = (
            f"persona tone: restrained={persona_voice.get('restraint', 0.7)}, reflective={persona_voice.get('reflection', 0.65)}, "
            f"self_irony={persona_voice.get('self_irony', 0.3)}, understated lifestyle delivery."
        )
        anti_generic_constraints = self._anti_generic_constraints_layer()
        negative_prompt = self._negative_prompt(shot_archetype, scene_loc, platform_behavior)

        ordered_blocks = {
            "identity_core": identity_core,
            "life_continuity_context": life_continuity_context,
            "scene_context": scene_context,
            "wardrobe_context": wardrobe_context,
            "camera_context": camera_context,
            "camera_behavior_memory": camera_behavior_memory,
            "camera_physics": camera_physics,
            "sensor_realism": sensor_realism,
            "smartphone_behavior": smartphone_behavior,
            "micro_imperfections": micro_imperfections,
            "face_consistency": face_consistency,
            "device_identity": device_identity,
            "favorite_locations": favorite_location_memory,
            "platform_intent": platform_intent_block,
            "composition_and_lighting": composition_and_lighting,
            "realism_cues": realism_cues,
            "continuity_cues": continuity_cues,
            "anti_generic_constraints": anti_generic_constraints,
            "persona_voice_cues": persona_voice_cues,
            "negative_prompt": negative_prompt,
        }

        prefix = blocks.get("prompt_v2_prefix", "Prompt System v2")
        include_negative_prompt = content_type.lower() in {"photo", "carousel", "video", "reel", "story", "stories"}
        final_prompt = (
            f"{prefix}: "
            + " ".join(f"[{key}] {value}" for key, value in ordered_blocks.items() if key != "negative_prompt")
            + (f" [negative_prompt] {negative_prompt}" if include_negative_prompt else "")
        )
        final_prompt = self._clean_generic_prompt_terms(final_prompt)
        return {
            **ordered_blocks,
            "final_prompt": final_prompt,
            "shot_archetype": shot_archetype,
            "platform_behavior": platform_behavior,
        }

    def _identity_core(self, context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        character = context.get("character")
        name = getattr(character, "name", None) or profile.get("display_name") or "Alina Volkova"
        age = str(getattr(character, "age", None) or profile.get("age") or "22")
        hair = profile.get("appearance_hair_color") or "light chestnut hair"
        eyes = profile.get("appearance_eye_color") or "green eyes"
        face = profile.get("appearance_face_shape") or "soft oval face"
        body = profile.get("appearance_body_type") or "slim natural build"
        makeup = profile.get("makeup_profile") or "soft everyday makeup"
        skin = profile.get("skin_realism_profile") or "natural skin texture"
        signature = profile.get("signature_appearance_cues") or "same recurring person across days"
        return (
            f"{name}, {age} years old; identity DNA: {hair}, {eyes}, {face}, {body}; "
            f"makeup={makeup}; skin={skin}; signature cues={signature}."
        )

    @staticmethod
    def _wardrobe_context(outfit_summary: str, shot_archetype: str, outfit_item_ids: str) -> str:
        visible_scope = "focus on visible upper-body pieces" if shot_archetype in {"front_selfie", "close_portrait", "mirror_selfie", "seated_table_shot"} else "full outfit coherence"
        return f"outfit={outfit_summary}; {visible_scope}; item_ids={outfit_item_ids}."

    @staticmethod
    def _device_profile(context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        device = profile.get("device_profile") or "Alina's personal smartphone"
        return f"device_profile={device}"

    @staticmethod
    def _platform_intent(context: Dict[str, Any], content_type: str, platform_intent: str | None, behavior_mode: str) -> str:
        intent = PromptComposer._platform_behavior_intent(content_type, platform_intent)
        mapping = {
            "instagram_feed": "slightly curated hero moment, coherent framing, social-ready but still lived-in.",
            "story_lifestyle": "spontaneous, intimate, less polished, diary-like everyday authenticity.",
            "reel_cover": "clear focal subject, energetic framing, thumbnail readability with realistic movement context.",
            "private_mirror": "private-feeling mirror documentation, casual posture, lived-in environment.",
            "travel_candid": "travel diary realism, environmental context matters more than perfection.",
        }
        return (
            f"platform=Instagram; intent={intent}; behavior_mode={behavior_mode}; "
            f"direction={mapping.get(intent, mapping['instagram_feed'])}"
        )

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

    def _continuity_cues(self, context: Dict[str, Any], scene: Any) -> str:
        continuity = context.get("continuity_context") or {}
        arc = continuity.get("arc_hint", "stable_routine")
        if arc == "arrival_and_adaptation":
            hint = "subtle arrival cues like not fully unpacked luggage or adaptation-to-space mood"
        elif arc == "same_mode_continuation":
            hint = "routine confidence, settled posture, familiar environment handling"
        elif arc == "recovery_continuation":
            hint = "gentle pace, low-energy body language, quiet environment choices"
        else:
            hint = "steady day-to-day continuity with believable micro-variation"
        scene_source = getattr(scene, "scene_source", "") or getattr(scene, "source", "library")
        return f"arc={arc}; continuity_hint={hint}; scene_source={scene_source}; signature={getattr(scene, 'moment_signature', '')}."

    def _negative_prompt(self, shot_archetype: str, scene_loc: str, platform_behavior: str) -> str:
        universal_negative = [
            "extra fingers",
            "deformed hands",
            "duplicate person",
            "plastic skin",
            "doll face",
            "bad anatomy",
            "broken hand pose",
            "wrong limb placement",
            "generic model photo",
            "fashion catalog symmetry",
            "sterile beauty campaign polish",
            "perfect lighting",
            "fashion model pose",
        ]
        shot_negative = {
            "mirror_selfie": ["wrong reflection", "floating phone", "broken mirror reflection", "impossible reflection geometry"],
            "front_selfie": ["rear-camera perspective", "detached floating arm"],
            "candid_handheld": ["posed studio stance", "perfect catalog centering", "tripod-like static shot"],
            "friend_shot": ["subject looking directly at lens in every frame", "editorial posing"],
            "close_portrait": ["wax skin", "beauty filter look"],
        }
        platform_negative = {
            "story_lifestyle": ["overproduced ad lighting", "commercial hero framing"],
            "travel_candid": ["duplicate pedestrians", "background motion incoherence", "floating bag straps"],
            "private_mirror": ["public street crowd", "non-mirror perspective"],
        }
        location_negative: list[str] = []
        loc = str(scene_loc).lower()
        if any(token in loc for token in ["street", "city", "outdoor"]):
            location_negative.extend(["empty fake street", "background perspective mismatch", "impossible pedestrian scale"])
        if any(token in loc for token in ["hotel", "room", "indoor"]):
            location_negative.extend(["impossible room layout", "floating furniture", "impossible window lighting"])
        if "kitchen" in loc:
            location_negative.extend(["broken mug handle", "impossible cup grip"])
        return ", ".join(universal_negative + shot_negative.get(shot_archetype, []) + platform_negative.get(platform_behavior, []) + location_negative)

    @staticmethod
    def _device_identity_layer(shot_archetype: str, context: Dict[str, Any], platform_behavior: str) -> str:
        profile = context.get("character_profile") or {}
        recurring_device = profile.get("recurring_phone_device") or profile.get("device_profile") or "Alina's personal smartphone"
        if shot_archetype in {"front_selfie", "mirror_selfie"}:
            return f"captured on Alina's personal smartphone device ({recurring_device}); phone visible in mirror reflection and consistent with prior posts"
        if shot_archetype in {"candid_handheld", "friend_shot", "candid_observer"}:
            return f"observer capture plausibly from friend-held consumer phone; account device identity remains {recurring_device}"
        return f"capture chain consistent with recurring account device identity={recurring_device}; mode={platform_behavior}"

    @staticmethod
    def _camera_behavior_memory(shot_archetype: str, continuity: Dict[str, Any], recent_moment_memory: List[Dict[str, Any]]) -> str:
        behavior = continuity.get("camera_behavior_memory") if isinstance(continuity.get("camera_behavior_memory"), dict) else {}
        recent_archetypes = [str(row.get("shot_archetype") or "").strip() for row in recent_moment_memory[:4] if str(row.get("shot_archetype") or "").strip()]
        preferred_archetypes = behavior.get("preferred_shot_archetypes") or ["candid_handheld", "friend_shot"]
        avg_distance = behavior.get("average_camera_distance") or "about 1.2m social distance"
        framing_style = behavior.get("preferred_framing_style") or "mostly eye-level with slight off-center framing"
        selfie_freq = behavior.get("selfie_frequency") or "rare"
        candid_freq = behavior.get("candid_frequency") or "frequent"
        repetition_note = "avoid near-duplicate framing from previous day" if recent_archetypes and recent_archetypes[0] == shot_archetype else "allow controlled variation"
        return (
            "camera behavior memory: "
            f"preferred_shot_archetypes={preferred_archetypes}; average_camera_distance={avg_distance}; "
            f"preferred_framing_style={framing_style}; selfie_frequency={selfie_freq}; candid_frequency={candid_freq}; "
            f"recent_archetypes={recent_archetypes}; current={shot_archetype}; {repetition_note}."
        )

    @staticmethod
    def _camera_physics_layer(shot_archetype: str, scene_loc: str) -> str:
        cues = [
            "subtle handheld motion",
            "natural smartphone lens perspective",
            "slight imperfect framing",
            "natural depth falloff typical of phone optics",
            "mild smartphone sensor noise",
        ]
        if shot_archetype in {"candid_handheld", "friend_shot", "candid_observer"}:
            cues.append("minor motion softness from live movement")
        if "street" in str(scene_loc).lower():
            cues.append("observer alignment not perfectly level")
        return f"camera physics: {', '.join(cues)}."

    @staticmethod
    def _sensor_realism_layer(time_of_day: str, scene_loc: str) -> str:
        cues = ["natural dynamic range behavior", "highlight rolloff", "soft shadow clipping"]
        loc = str(scene_loc).lower()
        tod = str(time_of_day).lower()
        if tod in {"morning", "late_morning"} and any(token in loc for token in ["window", "room", "kitchen", "indoor"]):
            cues.append("natural HDR balancing window highlights and interior shadows")
        if tod in {"evening", "night"}:
            cues.extend(["slightly warmer white balance", "mild sensor grain in low light"])
        return f"sensor realism: {', '.join(cues)}."

    @staticmethod
    def _smartphone_behavior_layer(scene_loc: str, time_of_day: str) -> str:
        cue = "subtle sharpening behavior of smartphone computational photography"
        if str(time_of_day).lower() in {"night", "evening"}:
            cue += ", denoising kept mild and realistic"
        if "window" in str(scene_loc).lower():
            cue += ", local HDR near bright window edges"
        return f"smartphone behavior: {cue}."

    @staticmethod
    def _micro_imperfections_layer(shot_archetype: str, platform_behavior: str) -> str:
        base = [
            "tiny loose hair strands",
            "slight facial-expression asymmetry",
            "believable fabric fold tension",
            "natural posture imperfections",
            "non-model-like hand placement",
        ]
        if shot_archetype in {"seated_table_shot", "friend_shot", "candid_handheld"}:
            base.append("mild casual disorder in environment")
            base.append("lived-in contact points like mug grip, book angle, bag strap")
        if platform_behavior == "instagram_feed":
            base.append("still clean enough for feed but not commercial perfect")
        return f"micro imperfections: {', '.join(base)}."

    @staticmethod
    def _face_consistency_layer(context: Dict[str, Any]) -> str:
        profile = context.get("character_profile") or {}
        signature = profile.get("face_signature") or profile.get("signature_appearance_cues") or "soft brows, gentle cheek contour, familiar lip shape"
        face_shape = profile.get("face_shape") or profile.get("appearance_face_shape") or "soft oval"
        nose_bridge = profile.get("nose_bridge") or "straight delicate nose bridge"
        cheekbone_softness = profile.get("cheekbone_softness") or "soft cheekbone transitions"
        lip_fullness = profile.get("lip_fullness") or "medium-full lips"
        brow_style = profile.get("brow_style") or "natural softly straight brows"
        return (
            f"face consistency signature: {signature}; face_shape={face_shape}; nose_bridge={nose_bridge}; "
            f"cheekbone_softness={cheekbone_softness}; lip_fullness={lip_fullness}; brow_style={brow_style}; "
            "preserve recurring face proportions and habitual expression style."
        )

    @staticmethod
    def _favorite_location_memory_layer(context: Dict[str, Any], scene_loc: str) -> str:
        profile = context.get("character_profile") or {}
        favorites_raw = profile.get("favorite_locations") or profile.get("favorite_locations_memory") or "kitchen window corner, favorite café table"
        recurring_raw = profile.get("recurring_spaces") or profile.get("favorite_spaces") or "living room sofa, hallway mirror"
        favorites = [chunk.strip() for chunk in str(favorites_raw).split(",") if chunk.strip()]
        recurring_spaces = [chunk.strip() for chunk in str(recurring_raw).split(",") if chunk.strip()]
        current = str(scene_loc).lower()
        anchors = favorites + [spot for spot in recurring_spaces if spot not in favorites]
        recurrence = next((spot for spot in anchors if spot.lower() in current), anchors[0] if anchors else "familiar recurring micro-location")
        return f"favorite location memory: favorite_locations={favorites}; recurring_spaces={recurring_spaces}; selected_recurring_anchor={recurrence}."

    @staticmethod
    def _anti_generic_constraints_layer() -> str:
        return (
            "forbid generic AI wording and campaign aesthetics: no 'beautiful young woman', no fashion catalog mood, "
            "no sterile luxury vibe, no beauty-campaign language, no editorial over-posing, no '8k photorealistic', no 'perfect lighting', no 'fashion model pose'."
        )

    @staticmethod
    def _clean_generic_prompt_terms(text: str) -> str:
        cleaned = text
        banned = ["beautiful young woman", "photorealistic 8k", "8k", "highly detailed", "luxury campaign", "editorial fashion shoot", "perfect lighting", "fashion model pose"]
        for token in banned:
            cleaned = cleaned.replace(token, "")
            cleaned = cleaned.replace(token.title(), "")
            cleaned = cleaned.replace(token.upper(), "")
        return " ".join(cleaned.split())

    def _resolve_shot_archetype(self, scene: Any) -> str:
        explicit = getattr(scene, "camera_archetype", "") or getattr(scene, "shot_archetype", "")
        if explicit and explicit in self.CAMERA_ARCHETYPES:
            return explicit
        text = " ".join(
            [
                str(getattr(scene, "scene_moment", "") or "").lower(),
                str(getattr(scene, "description", "") or "").lower(),
                str(getattr(scene, "scene_moment_type", "") or "").lower(),
            ]
        )
        if "mirror" in text:
            return "mirror_selfie"
        if "selfie" in text:
            return "front_selfie"
        if "candid" in text:
            return "candid_handheld"
        if "portrait" in text:
            return "close_portrait"
        if "table" in text or "coffee" in text:
            return "seated_table_shot"
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
