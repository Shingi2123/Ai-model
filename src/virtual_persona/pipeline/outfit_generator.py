from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List


class OutfitGenerationError(ValueError):
    pass


class ManualOutfitValidationError(OutfitGenerationError):
    pass


@dataclass
class OutfitBundle:
    top: str = ""
    bottom: str = ""
    outerwear: str = ""
    shoes: str = ""
    accessories: str = ""
    fit: str = ""
    fabric: str = ""
    condition: str = ""
    styling: str = ""
    sentence: str = ""
    outfit_sentence: str = ""
    style_profile: List[str] | None = None
    place: str = ""
    activity: str = ""
    time_of_day: str = ""
    weather_context: str = ""
    social_presence: str = ""
    energy: str = ""
    habit: str = ""
    style_intensity: float = 0.0
    outfit_style: str = ""
    enhance_attractiveness: float = 0.0
    outfit_override_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["style_profile"] = list(self.style_profile or [])
        payload["sentence"] = self.outfit_sentence or self.sentence
        payload["outfit_sentence"] = self.outfit_sentence or self.sentence
        return payload


class OutfitGenerator:
    CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
    INVALID_TOKENS = {
        "",
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
        "outfit",
        "look",
    }
    EXPLICIT_TOKENS = {
        "sexy",
        "provocative",
        "lingerie",
        "bikini",
        "fetish",
        "erotic",
        "explicit",
        "porn",
    }
    OVERRIDE_HINTS = {
        "more_feminine": {"min_enhance": 0.55},
        "slightly_sexy": {"min_enhance": 0.68},
        "intimate_home": {"min_enhance": 0.86, "style_hint": "intimate_soft"},
        "tight_silhouette": {"min_enhance": 0.62, "fit_hint": "tight_silhouette"},
        "open_shoulders": {"min_enhance": 0.72, "top_hint": "open_shoulders"},
    }
    NEGATIVE_OUTFIT_RULES = (
        "fashion catalog outfit",
        "perfect styling",
        "overly trendy outfit",
        "runway fashion",
        "influencer outfit",
        "studio fashion look",
        "over coordinated clothing",
        "impractical clothing for context",
    )

    def generate(self, *, outfit_summary: str, scene: Any, context: Dict[str, Any]) -> str:
        bundle = self.generate_bundle(outfit_summary=outfit_summary, scene=scene, context=context)
        return bundle.outfit_sentence or bundle.sentence

    def generate_bundle(self, *, outfit_summary: str, scene: Any, context: Dict[str, Any]) -> OutfitBundle:
        manual_outfit = self._resolve_manual_override(scene, context)
        override_hint = self._override_hint_key(manual_outfit)
        descriptor = self._build_descriptor(scene, context, outfit_summary, override_hint=override_hint)

        if manual_outfit and not override_hint:
            validated = self.validate_manual_outfit(manual_outfit)
            bundle = self._bundle_from_manual_override(validated, descriptor)
            return self._validate_bundle(bundle, descriptor)

        try:
            bundle = self._compose_contextual_bundle(descriptor)
            bundle = self._validate_bundle(bundle, descriptor)
        except OutfitGenerationError:
            fallback = self._fallback_bundle(descriptor)
            bundle = self._validate_bundle(fallback, descriptor)
        if override_hint and not bundle.outfit_override_used:
            bundle.outfit_override_used = override_hint
        return bundle

    def validate_manual_outfit(self, manual_outfit: str) -> str:
        cleaned = self._clean_text(manual_outfit)
        if self._is_invalid_value(cleaned):
            raise ManualOutfitValidationError("Manual outfit override is empty or contains a placeholder")
        if self.CYRILLIC_RE.search(cleaned):
            raise ManualOutfitValidationError("Manual outfit override must be in English only")
        if "." in cleaned:
            raise ManualOutfitValidationError("Manual outfit override must not contain periods")
        if not re.search(r"[A-Za-z]", cleaned):
            raise ManualOutfitValidationError("Manual outfit override must contain English text")
        return cleaned

    def _build_descriptor(
        self,
        scene: Any,
        context: Dict[str, Any],
        outfit_summary: str,
        *,
        override_hint: str = "",
    ) -> Dict[str, Any]:
        weather = context.get("weather")
        behavior = context.get("behavioral_context")
        profile = context.get("character_profile") or {}

        place_text = self._clean_text(
            getattr(scene, "location", "")
            or context.get("place")
            or getattr(scene, "scene_moment", "")
            or getattr(scene, "description", "")
        ).lower()
        activity_text = self._clean_text(
            getattr(scene, "activity", "")
            or context.get("activity")
            or getattr(scene, "description", "")
            or getattr(scene, "scene_moment", "")
        ).lower()
        scene_text = " ".join(
            [
                place_text,
                activity_text,
                self._clean_text(getattr(scene, "scene_moment", "")).lower(),
                self._clean_text(getattr(scene, "description", "")).lower(),
            ]
        ).strip()
        time_of_day = self._clean_text(getattr(scene, "time_of_day", "") or context.get("time_of_day") or "").lower() or "day"
        social_presence = self._normalize_social_presence(
            self._first_value(
                getattr(scene, "social_presence", ""),
                context.get("social_presence"),
                getattr(behavior, "social_mode", ""),
                getattr(getattr(behavior, "daily_state", None), "social_presence_mode", ""),
            )
        )
        energy = self._normalize_energy(
            self._first_value(
                context.get("energy"),
                getattr(behavior, "energy_level", ""),
                getattr(getattr(behavior, "daily_state", None), "energy_level", ""),
                getattr(context.get("life_state"), "energy_state", ""),
            )
        )
        habit = self._clean_text(
            self._first_value(
                context.get("habit"),
                getattr(behavior, "habit", ""),
                getattr(behavior, "selected_habit", ""),
            )
        ).lower() or "none"
        objects = list(getattr(behavior, "objects", getattr(behavior, "recurring_objects", [])) or [])
        style_intensity = self._normalize_scalar(
            self._first_value(
                getattr(scene, "style_intensity", ""),
                context.get("style_intensity"),
                context.get("outfit_style_intensity"),
                profile.get("default_style_intensity"),
            ),
            default=0.25,
        )
        style_hint = self._normalize_style_hint(
            self._first_value(
                getattr(scene, "outfit_style", ""),
                getattr(scene, "style_hint", ""),
                context.get("outfit_style"),
                context.get("style_hint"),
                context.get("manual_style"),
                profile.get("default_outfit_style"),
            )
        )
        enhance_attractiveness = self._normalize_scalar(
            self._first_value(
                getattr(scene, "enhance_attractiveness", ""),
                getattr(scene, "attractiveness_boost", ""),
                context.get("enhance_attractiveness"),
                context.get("attractiveness_boost"),
            ),
            default=0.0,
        )

        override_cfg = self.OVERRIDE_HINTS.get(override_hint, {})
        style_hint = str(override_cfg.get("style_hint") or style_hint or "")
        enhance_attractiveness = max(enhance_attractiveness, float(override_cfg.get("min_enhance") or 0.0))
        temp_c = getattr(weather, "temp_c", 18)
        if not isinstance(temp_c, (int, float)):
            temp_c = 18
        condition = self._clean_text(getattr(weather, "condition", "")).lower() or "clear"
        place_type = self._place_type(scene_text)
        if place_type not in {"home", "hotel"} and enhance_attractiveness > 0.8:
            enhance_attractiveness = 0.78

        return {
            "scene": scene,
            "context": context,
            "source_items": self._parse_source_items(outfit_summary),
            "recent_outfit_memory": list(context.get("recent_outfit_memory") or [])[-20:],
            "place": place_text,
            "place_type": place_type,
            "activity": activity_text,
            "time_of_day": time_of_day,
            "weather_condition": condition,
            "weather_context": f"{condition}, {temp_c}C",
            "temp_c": float(temp_c),
            "is_cold": float(temp_c) <= 10,
            "is_cool": float(temp_c) <= 18,
            "is_warm": float(temp_c) >= 24,
            "is_evening": time_of_day in {"evening", "night"},
            "is_morning": "morning" in time_of_day,
            "is_rainy": condition in {"rain", "drizzle", "snow"},
            "style_intensity": max(0.0, min(style_intensity, 1.0)),
            "style_hint": style_hint,
            "enhance_attractiveness": max(0.0, min(enhance_attractiveness, 1.0)),
            "mood": self._clean_text(getattr(scene, "mood", "") or context.get("mood") or "").lower(),
            "social_presence": social_presence,
            "energy": energy,
            "habit": habit,
            "behavior_mode": self._clean_text(
                getattr(behavior, "self_presentation", "")
                or getattr(behavior, "outfit_behavior_mode", "")
                or getattr(getattr(behavior, "daily_state", None), "self_presentation_mode", "")
            ).lower(),
            "objects": [self._natural_object_term(obj) for obj in objects if self._natural_object_term(obj)],
            "style_profile": self._style_profile(context),
            "override_hint": override_hint,
            "override_fit_hint": str(override_cfg.get("fit_hint") or ""),
            "override_top_hint": str(override_cfg.get("top_hint") or ""),
            "outfit_override_used": "",
            "outfit_style": style_hint,
        }

    def _compose_contextual_bundle(self, descriptor: Dict[str, Any]) -> OutfitBundle:
        source_map = self._source_map(descriptor["source_items"])
        memory_map = self._memory_map(descriptor["recent_outfit_memory"], descriptor["place_type"])
        use_dress = self._should_use_dress(descriptor, source_map)

        if use_dress:
            top = self._choose_dress(descriptor, source_map, memory_map)
            bottom = ""
        else:
            top = self._choose_top(descriptor, source_map, memory_map)
            bottom = self._choose_bottom(descriptor, source_map, memory_map)

        outerwear = self._choose_outerwear(descriptor, source_map, memory_map)
        shoes = self._choose_shoes(descriptor, source_map, memory_map)
        accessories = self._choose_accessories(descriptor, memory_map)
        fit = self._choose_fit(descriptor)
        fabric = self._choose_fabric(descriptor)
        condition = self._choose_condition(descriptor)
        styling = self._choose_styling(descriptor)
        sentence = self._sentence_from_structure(
            top=top,
            bottom=bottom,
            outerwear=outerwear,
            shoes=shoes,
            accessories=accessories,
            fit=fit,
            fabric=fabric,
            condition=condition,
            styling=styling,
        )

        return OutfitBundle(
            top=top,
            bottom=bottom,
            outerwear=outerwear,
            shoes=shoes,
            accessories=accessories,
            fit=fit,
            fabric=fabric,
            condition=condition,
            styling=styling,
            sentence=sentence,
            outfit_sentence=sentence,
            style_profile=list(descriptor["style_profile"]),
            place=str(descriptor["place"]),
            activity=str(descriptor["activity"]),
            time_of_day=str(descriptor["time_of_day"]),
            weather_context=str(descriptor["weather_context"]),
            social_presence=str(descriptor["social_presence"]),
            energy=str(descriptor["energy"]),
            habit=str(descriptor["habit"]),
            style_intensity=float(descriptor["style_intensity"]),
            outfit_style=str(descriptor["outfit_style"]),
            enhance_attractiveness=float(descriptor["enhance_attractiveness"]),
            outfit_override_used="",
        )

    def _fallback_bundle(self, descriptor: Dict[str, Any]) -> OutfitBundle:
        top = "soft fitted knit dress" if self._should_use_dress(descriptor, {}) else "soft knit top"
        bottom = "" if "dress" in top else ("relaxed straight trousers" if descriptor["place_type"] == "airport" else "straight trousers")
        outerwear = ""
        if descriptor["place_type"] == "airport" or descriptor["is_cold"] or descriptor["is_rainy"]:
            outerwear = "light neutral coat" if descriptor["place_type"] == "airport" else "soft light jacket"
        shoes = "comfortable sneakers" if descriptor["place_type"] != "hotel" else "flat slides"
        accessories = self._choose_accessories(descriptor, {})
        fit = self._choose_fit(descriptor)
        fabric = self._choose_fabric(descriptor)
        condition = self._choose_condition(descriptor)
        styling = self._choose_styling(descriptor)
        return OutfitBundle(
            top=top,
            bottom=bottom,
            outerwear=outerwear,
            shoes=shoes,
            accessories=accessories,
            fit=fit,
            fabric=fabric,
            condition=condition,
            styling=styling,
            sentence=self._sentence_from_structure(
                top=top,
                bottom=bottom,
                outerwear=outerwear,
                shoes=shoes,
                accessories=accessories,
                fit=fit,
                fabric=fabric,
                condition=condition,
                styling=styling,
            ),
            outfit_sentence=self._sentence_from_structure(
                top=top,
                bottom=bottom,
                outerwear=outerwear,
                shoes=shoes,
                accessories=accessories,
                fit=fit,
                fabric=fabric,
                condition=condition,
                styling=styling,
            ),
            style_profile=list(descriptor["style_profile"]),
            place=str(descriptor["place"]),
            activity=str(descriptor["activity"]),
            time_of_day=str(descriptor["time_of_day"]),
            weather_context=str(descriptor["weather_context"]),
            social_presence=str(descriptor["social_presence"]),
            energy=str(descriptor["energy"]),
            habit=str(descriptor["habit"]),
            style_intensity=float(descriptor["style_intensity"]),
            outfit_style=str(descriptor["outfit_style"]),
            enhance_attractiveness=float(descriptor["enhance_attractiveness"]),
            outfit_override_used="",
        )

    def _bundle_from_manual_override(self, manual_outfit: str, descriptor: Dict[str, Any]) -> OutfitBundle:
        mapped = {"top": "", "bottom": "", "outerwear": "", "shoes": "", "accessories": ""}
        for item in self._parse_source_items(manual_outfit):
            category = self._outfit_category(item)
            if category == "dress":
                mapped["top"] = mapped["top"] or item
                continue
            if category == "accessories":
                mapped["accessories"] = mapped["accessories"] or item
            elif category == "outerwear":
                mapped["outerwear"] = mapped["outerwear"] or item
            elif category in mapped:
                mapped[category] = mapped[category] or item

        return OutfitBundle(
            top=mapped["top"],
            bottom=mapped["bottom"],
            outerwear=mapped["outerwear"],
            shoes=mapped["shoes"],
            accessories=mapped["accessories"],
            fit=self._choose_fit(descriptor),
            fabric=self._choose_fabric(descriptor),
            condition=self._choose_condition(descriptor),
            styling=self._choose_styling(descriptor),
            sentence=manual_outfit,
            outfit_sentence=manual_outfit,
            style_profile=list(descriptor["style_profile"]),
            place=str(descriptor["place"]),
            activity=str(descriptor["activity"]),
            time_of_day=str(descriptor["time_of_day"]),
            weather_context=str(descriptor["weather_context"]),
            social_presence=str(descriptor["social_presence"]),
            energy=str(descriptor["energy"]),
            habit=str(descriptor["habit"]),
            style_intensity=float(descriptor["style_intensity"]),
            outfit_style=str(descriptor["outfit_style"]),
            enhance_attractiveness=float(descriptor["enhance_attractiveness"]),
            outfit_override_used=manual_outfit,
        )

    def _validate_bundle(self, bundle: OutfitBundle, descriptor: Dict[str, Any]) -> OutfitBundle:
        sentence = self._clean_text(bundle.outfit_sentence or bundle.sentence)
        if self._is_invalid_value(sentence):
            raise OutfitGenerationError("Generated outfit is empty")
        if self.CYRILLIC_RE.search(sentence):
            raise OutfitGenerationError("Generated outfit contains Cyrillic")
        if "." in sentence:
            raise OutfitGenerationError("Generated outfit must not contain periods")
        lowered = sentence.lower()
        if any(token in lowered for token in self.EXPLICIT_TOKENS):
            raise OutfitGenerationError("Generated outfit became too explicit")
        if any(rule in lowered for rule in self.NEGATIVE_OUTFIT_RULES):
            raise OutfitGenerationError("Generated outfit leaked negative-rule phrasing")

        clothing_present = [bundle.top, bundle.bottom, bundle.outerwear, bundle.shoes, bundle.accessories]
        if len([item for item in clothing_present if self._clean_text(item)]) < 3:
            raise OutfitGenerationError("Generated outfit must contain enough contextual elements")
        if not bundle.shoes:
            raise OutfitGenerationError("Generated outfit must include shoes")
        if not (bundle.top and bundle.bottom) and "dress" not in bundle.top.lower():
            raise OutfitGenerationError("Generated outfit must include a top and bottom or a dress")

        if descriptor["place_type"] == "airport" and not any(token in lowered for token in ["bag", "carry on", "sneakers", "coat", "jacket", "travel"]):
            raise OutfitGenerationError("Airport outfit is missing travel-ready context")
        if descriptor["place_type"] == "hotel" and any(token in lowered for token in ["boarding pass", "runway", "gate seating"]):
            raise OutfitGenerationError("Hotel outfit conflicts with the scene")
        if descriptor["is_warm"] and any(token in lowered for token in ["heavy coat", "puffer", "thick wool coat"]):
            raise OutfitGenerationError("Warm-weather outfit is too heavy")
        if descriptor["is_cold"] and not any(token in lowered for token in ["jacket", "cardigan", "coat", "boots", "knit", "layer"]):
            raise OutfitGenerationError("Cold-weather outfit is missing layering")
        if "carry on" in descriptor["objects"] and "carry on" not in lowered and descriptor["place_type"] == "airport":
            raise OutfitGenerationError("Outfit is not aligned with airport objects")

        bundle.sentence = sentence
        bundle.outfit_sentence = sentence
        return bundle

    def _choose_top(self, descriptor: Dict[str, Any], source_map: Dict[str, str], memory_map: Dict[str, str]) -> str:
        hinted = source_map.get("top") or memory_map.get("top")
        if hinted:
            return self._enrich_source_piece(hinted, "top", descriptor)
        place_type = descriptor["place_type"]
        enhance = descriptor["enhance_attractiveness"]
        style_intensity = descriptor["style_intensity"]
        style_hint = descriptor["style_hint"]
        if descriptor["override_top_hint"] == "open_shoulders" and place_type in {"home", "hotel", "cafe"}:
            return "soft knit top slipping slightly off the shoulders"
        if style_hint == "sporty":
            return "clean performance zip top with a relaxed real-life fit"
        if place_type == "airport":
            return "soft fitted knit top"
        if place_type == "work":
            return "clean knit top with a neat natural fit"
        if style_hint == "intimate_soft" or (enhance >= 0.8 and place_type in {"home", "hotel"}):
            return "soft ribbed top sitting close to the body"
        if (enhance >= 0.6 or style_intensity >= 0.65 or style_hint == "bold_minimal") and place_type in {"cafe", "street", "hotel"}:
            return "soft fitted knit top with an open neckline"
        if descriptor["is_warm"]:
            return "light cotton top with an easy fit"
        return "soft knit top with a natural fit"

    def _choose_bottom(self, descriptor: Dict[str, Any], source_map: Dict[str, str], memory_map: Dict[str, str]) -> str:
        hinted = source_map.get("bottom") or memory_map.get("bottom")
        if hinted:
            return self._enrich_source_piece(hinted, "bottom", descriptor)
        place_type = descriptor["place_type"]
        enhance = descriptor["enhance_attractiveness"]
        style_hint = descriptor["style_hint"]
        if style_hint == "sporty":
            return "tapered joggers with natural bunching at the ankles"
        if place_type == "airport":
            return "relaxed straight trousers"
        if place_type == "work":
            return "tailored trousers with soft creases from sitting"
        if style_hint == "intimate_soft":
            return "easy lounge trousers with gentle wrinkles through the legs"
        if (enhance >= 0.6 or descriptor["style_intensity"] >= 0.65 or style_hint == "bold_minimal") and descriptor["is_warm"] and place_type in {"cafe", "street", "hotel"}:
            return "high waisted straight trousers"
        if descriptor["is_warm"]:
            return "light straight trousers"
        return "straight trousers"

    def _choose_outerwear(self, descriptor: Dict[str, Any], source_map: Dict[str, str], memory_map: Dict[str, str]) -> str:
        hinted = source_map.get("outerwear") or memory_map.get("outerwear")
        if hinted:
            return self._enrich_source_piece(hinted, "outerwear", descriptor)
        if not self._needs_layer(descriptor):
            return ""
        place_type = descriptor["place_type"]
        style_hint = descriptor["style_hint"]
        if descriptor["is_rainy"]:
            return "light weatherproof jacket"
        if place_type == "airport":
            return "light neutral coat"
        if place_type == "work":
            return "easy blazer sitting naturally"
        if style_hint == "intimate_soft":
            return "light cardigan slipping loosely over the shoulders"
        if descriptor["is_cold"]:
            return "soft cardigan with natural bunching at the sleeves"
        return "light layer worn casually"

    def _choose_dress(self, descriptor: Dict[str, Any], source_map: Dict[str, str], memory_map: Dict[str, str]) -> str:
        hinted = source_map.get("dress") or memory_map.get("dress")
        if hinted:
            return self._enrich_source_piece(hinted, "dress", descriptor)
        enhance = descriptor["enhance_attractiveness"]
        if enhance >= 0.8:
            return "soft fitted knit dress with a gentle drape"
        if enhance >= 0.6:
            return "simple midi dress with an open neckline"
        return "soft knit dress with a relaxed fall"

    def _choose_shoes(self, descriptor: Dict[str, Any], source_map: Dict[str, str], memory_map: Dict[str, str]) -> str:
        hinted = source_map.get("shoes") or memory_map.get("shoes")
        if hinted:
            return self._enrich_source_piece(hinted, "shoes", descriptor)
        place_type = descriptor["place_type"]
        style_hint = descriptor["style_hint"]
        if place_type == "hotel" and descriptor["enhance_attractiveness"] >= 0.8:
            return "flat slides"
        if style_hint == "sporty":
            return "clean trainers"
        if descriptor["is_rainy"] or descriptor["is_cold"]:
            return "comfortable ankle boots"
        if descriptor["enhance_attractiveness"] >= 0.65 and descriptor["is_warm"] and place_type in {"home", "hotel"}:
            return "minimal sandals"
        if place_type == "work":
            return "sleek loafers"
        return "comfortable sneakers"

    def _choose_accessories(self, descriptor: Dict[str, Any], memory_map: Dict[str, str]) -> str:
        remembered = memory_map.get("accessories")
        if remembered and descriptor["place_type"] != "airport":
            return remembered
        objects = descriptor["objects"]
        place_type = descriptor["place_type"]
        social_presence = descriptor["social_presence"]
        enhance = descriptor["enhance_attractiveness"]
        if "carry on" in objects or place_type == "airport":
            return "small crossbody bag and compact carry on"
        if place_type == "hotel":
            if enhance >= 0.8:
                return "small overnight bag set aside naturally"
            return "small overnight bag nearby"
        if "coffee cup" in objects or place_type == "cafe":
            if social_presence == "light_public":
                return "small everyday bag and coffee cup"
            return "small shoulder bag and coffee cup"
        if enhance >= 0.6:
            return "small everyday bag and one understated piece of jewelry"
        return "small everyday bag"

    def _choose_fit(self, descriptor: Dict[str, Any]) -> str:
        enhance = descriptor["enhance_attractiveness"]
        energy = descriptor["energy"]
        fit_hint = descriptor["override_fit_hint"]
        style_intensity = descriptor["style_intensity"]
        if fit_hint == "tight_silhouette":
            return "gently body-skimming silhouette that still feels self-chosen"
        if enhance >= 0.8:
            return "soft close fit with natural drape"
        if enhance >= 0.6 or style_intensity >= 0.65:
            return "more feminine silhouette with easy movement"
        if enhance >= 0.35:
            return "slightly defined silhouette with natural drape"
        if energy == "low":
            return "slightly relaxed fit with a lived-in fall"
        return "slightly relaxed fit with natural drape"

    def _choose_fabric(self, descriptor: Dict[str, Any]) -> str:
        style_profile = " ".join(descriptor["style_profile"]).lower()
        enhance = descriptor["enhance_attractiveness"]
        if enhance >= 0.75:
            return "soft matte fabric with gentle movement"
        if "soft" in style_profile:
            return "soft matte everyday textures"
        if descriptor["is_warm"]:
            return "light breathable everyday fabrics"
        return "soft matte everyday fabrics"

    def _choose_condition(self, descriptor: Dict[str, Any]) -> str:
        place_type = descriptor["place_type"]
        if place_type == "airport":
            return "lightly worn, natural folds from sitting and moving"
        if descriptor["energy"] == "low":
            return "slightly rumpled in a believable way"
        return "lightly worn, natural folds"

    def _choose_styling(self, descriptor: Dict[str, Any]) -> str:
        enhance = descriptor["enhance_attractiveness"]
        if enhance >= 0.8:
            return "effortless and private, softly attractive without looking staged"
        if enhance >= 0.6:
            return "effortless, slightly feminine, not styled for attention"
        if enhance >= 0.35:
            return "effortless, just a little more put together than usual"
        return "effortless, slightly imperfect"

    def _should_use_dress(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> bool:
        if source_map.get("dress"):
            return True
        if descriptor["place_type"] == "airport":
            return False
        if descriptor["style_hint"] == "sporty":
            return False
        if descriptor["style_hint"] == "intimate_soft" and descriptor["place_type"] in {"hotel", "home"}:
            return descriptor["temp_c"] >= 16
        return descriptor["enhance_attractiveness"] >= 0.62 and descriptor["place_type"] in {"hotel", "home", "cafe"} and not descriptor["is_cold"]

    def _needs_layer(self, descriptor: Dict[str, Any]) -> bool:
        if descriptor["place_type"] == "airport":
            return True
        if descriptor["is_cold"] or descriptor["is_rainy"]:
            return True
        if descriptor["place_type"] in {"work", "street"} and descriptor["is_cool"]:
            return True
        return descriptor["is_evening"] and not descriptor["is_warm"]

    def _sentence_from_structure(
        self,
        *,
        top: str,
        bottom: str,
        outerwear: str,
        shoes: str,
        accessories: str,
        fit: str,
        fabric: str,
        condition: str,
        styling: str,
    ) -> str:
        clothing = [piece for piece in [top, bottom, outerwear, shoes, accessories] if self._clean_text(piece)]
        if not clothing:
            return ""
        phrased: List[str] = []
        for index, piece in enumerate(clothing):
            normalized = self._clean_text(piece)
            if index == 0 and not normalized.lower().startswith(("a ", "an ")):
                phrased.append(f"a {normalized}")
            else:
                phrased.append(normalized)
        base = self._human_join(phrased)
        details = [detail for detail in [fit, fabric, condition, styling] if self._clean_text(detail)]
        if details:
            return f"{base}; {', '.join(self._dedupe_phrases(details))}"
        return base

    def _memory_map(self, recent_memory: List[Dict[str, Any]], place_type: str) -> Dict[str, str]:
        for row in reversed(recent_memory[-10:]):
            row_place = self._place_type(
                " ".join(
                    [
                        str(row.get("place") or ""),
                        str(row.get("occasion") or ""),
                        str(row.get("notes") or ""),
                    ]
                )
            )
            if row_place and row_place not in {place_type, "daily"}:
                continue
            mapped = {
                "top": self._clean_text(row.get("top")),
                "bottom": self._clean_text(row.get("bottom")),
                "outerwear": self._clean_text(row.get("outerwear")),
                "dress": self._clean_text(row.get("dress")),
                "shoes": self._clean_text(row.get("shoes")),
                "accessories": self._clean_text(row.get("accessories")),
            }
            if any(mapped.values()):
                return {key: value for key, value in mapped.items() if value}
        return {}

    def _source_map(self, source_items: List[str]) -> Dict[str, str]:
        mapped: Dict[str, str] = {}
        for item in source_items:
            category = self._outfit_category(item)
            mapped.setdefault(category, item)
        return mapped

    def _parse_source_items(self, outfit_summary: str) -> List[str]:
        cleaned = self._clean_text(outfit_summary)
        if self._is_invalid_value(cleaned):
            return []
        items_part = cleaned.split("||")[0].strip()
        parts = re.split(r"\s*(?:,|\+|/)\s*", items_part)
        normalized: List[str] = []
        seen: set[str] = set()
        for part in parts:
            candidate = self._clean_text(part)
            if not candidate or self._is_invalid_value(candidate) or self.CYRILLIC_RE.search(candidate):
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
        return normalized

    def _resolve_manual_override(self, scene: Any, context: Dict[str, Any]) -> str:
        return self._clean_text(
            self._first_value(
                getattr(scene, "outfit_override", ""),
                getattr(scene, "manual_outfit", ""),
                context.get("outfit_override"),
                context.get("manual_outfit"),
                "",
            )
        )

    def _override_hint_key(self, value: str) -> str:
        key = self._clean_text(value).lower().replace(" ", "_")
        return key if key in self.OVERRIDE_HINTS else ""

    def _normalize_style_hint(self, value: Any) -> str:
        token = self._clean_text(value).lower().replace(" ", "_")
        allowed = {"casual", "elegant", "sporty", "intimate_soft", "bold_minimal", "travel_soft", "minimal"}
        return token if token in allowed else ""

    def _normalize_scalar(self, value: Any, *, default: float = 0.0) -> float:
        if isinstance(value, bool):
            return 0.65 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        token = self._clean_text(value).lower()
        mapping = {
            "none": 0.0,
            "low": 0.2,
            "medium": 0.5,
            "normal": 0.35,
            "soft": 0.35,
            "high": 0.8,
            "bold": 0.72,
            "expressive": 0.78,
        }
        if token in mapping:
            return mapping[token]
        try:
            return float(token)
        except Exception:
            return default

    def _normalize_social_presence(self, value: Any) -> str:
        token = self._clean_text(value).lower().replace(" ", "_")
        mapping = {
            "alone_but_in_public": "light_public",
            "quiet_public": "light_public",
            "light_public": "light_public",
            "public": "social",
            "social_public": "social",
            "social": "social",
            "alone": "alone",
            "private": "alone",
        }
        return mapping.get(token, "light_public" if "public" in token else (token or "alone"))

    def _normalize_energy(self, value: Any) -> str:
        if isinstance(value, (int, float)):
            if float(value) < 0.35:
                return "low"
            if float(value) > 0.68:
                return "high"
            return "medium"
        token = self._clean_text(value).lower()
        return token if token in {"low", "medium", "high"} else "medium"

    def _style_profile(self, context: Dict[str, Any]) -> List[str]:
        profile = context.get("character_profile") or {}
        raw = (
            profile.get("style_profile")
            or profile.get("favorite_clothing_styles")
            or ",".join(context.get("persona_voice", {}).get("style_identity", []) or [])
            or "minimalism, soft fabrics, neutral colors, natural ease"
        )
        values = [self._clean_text(part).lower() for part in str(raw).split(",") if self._clean_text(part)]
        if not values:
            return ["minimalism", "soft fabrics", "neutral colors", "natural ease"]
        deduped: List[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped[:4]

    def _place_type(self, scene_text: str) -> str:
        lowered = scene_text.lower()
        if any(token in lowered for token in ["airport", "terminal", "boarding", "gate", "flight", "layover"]):
            return "airport"
        if any(token in lowered for token in ["hotel", "room", "suite"]):
            return "hotel"
        if "cafe" in lowered or "coffee shop" in lowered:
            return "cafe"
        if any(token in lowered for token in ["office", "cowork", "meeting", "desk"]):
            return "work"
        if any(token in lowered for token in ["street", "walk", "boulevard", "avenue", "outside", "city"]):
            return "street"
        if any(token in lowered for token in ["home", "bedroom", "kitchen", "living room"]):
            return "home"
        return "daily"

    def _outfit_category(self, item: str) -> str:
        lowered = self._clean_text(item).lower()
        if "dress" in lowered:
            return "dress"
        if any(token in lowered for token in ["coat", "jacket", "blazer", "cardigan", "hoodie", "trench", "layer"]):
            return "outerwear"
        if any(token in lowered for token in ["jeans", "trousers", "pants", "skirt", "shorts", "denim", "joggers", "leggings"]):
            return "bottom"
        if any(token in lowered for token in ["sneakers", "trainers", "boots", "heels", "loafers", "sandals", "slides", "shoes"]):
            return "shoes"
        if any(token in lowered for token in ["bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "cap", "belt", "carry on"]):
            return "accessories"
        return "top"

    def _enrich_source_piece(self, piece: str, category: str, descriptor: Dict[str, Any]) -> str:
        cleaned = self._clean_text(piece).lower()
        if category == "top":
            if any(token in cleaned for token in ["tank", "camisole"]):
                return "soft fitted tank" if descriptor["enhance_attractiveness"] >= 0.6 else "soft tank top"
            if any(token in cleaned for token in ["shirt", "button"]):
                return "easy shirt worn naturally"
            return cleaned
        if category == "bottom":
            if "jeans" in cleaned or "denim" in cleaned:
                return "straight denim"
            if "skirt" in cleaned:
                return "simple skirt with soft movement"
            return cleaned
        if category in {"outerwear", "layer"}:
            if any(token in cleaned for token in ["trench", "coat"]):
                return "light neutral coat"
            if any(token in cleaned for token in ["cardigan", "hoodie"]):
                return "soft cardigan"
            return cleaned
        if category == "dress":
            return cleaned
        if category == "shoes":
            if any(token in cleaned for token in ["sneakers", "trainers"]):
                return "comfortable sneakers"
            if any(token in cleaned for token in ["boots", "boot"]):
                return "comfortable ankle boots"
            return cleaned
        if category == "accessories":
            return cleaned
        return cleaned

    def _human_join(self, parts: List[str]) -> str:
        cleaned = [self._clean_text(part) for part in parts if self._clean_text(part)]
        if not cleaned:
            return ""
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} and {cleaned[1]}"
        return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"

    def _dedupe_phrases(self, phrases: List[str]) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        for phrase in phrases:
            cleaned = self._clean_text(phrase)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _is_invalid_value(self, value: str) -> bool:
        cleaned = self._clean_text(value).lower()
        if cleaned in self.INVALID_TOKENS:
            return True
        return not cleaned or re.fullmatch(r"[.\-_/]+", cleaned) is not None

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = " ".join(str(value or "").replace("_", " ").split())
        return text.strip(" ,;:")

    @staticmethod
    def _first_value(*values: Any) -> Any:
        for value in values:
            if value not in (None, "", []):
                return value
        return ""

    @staticmethod
    def _natural_object_term(obj: str) -> str:
        return {
            "carry_on": "carry on",
            "coffee_cup": "coffee cup",
        }.get(str(obj or "").strip().lower(), str(obj or "").replace("_", " ").strip())
