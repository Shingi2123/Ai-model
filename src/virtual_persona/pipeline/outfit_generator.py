from __future__ import annotations

import re
from typing import Any, Dict, List


class OutfitGenerationError(ValueError):
    pass


class ManualOutfitValidationError(OutfitGenerationError):
    pass


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

    def generate(self, *, outfit_summary: str, scene: Any, context: Dict[str, Any]) -> str:
        manual_outfit = self._resolve_manual_override(scene, context)
        if manual_outfit:
            return self.validate_manual_outfit(manual_outfit)

        descriptor = self._build_descriptor(scene, context, outfit_summary)
        generated = self._compose_contextual_outfit(descriptor)
        try:
            return self._validate_generated_outfit(generated, descriptor)
        except OutfitGenerationError:
            fallback = self._fallback_outfit(descriptor)
            return self._validate_generated_outfit(fallback, descriptor)

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

    def _build_descriptor(self, scene: Any, context: Dict[str, Any], outfit_summary: str) -> Dict[str, Any]:
        weather = context.get("weather")
        behavior = context.get("behavioral_context")
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
        )
        style_intensity = self._normalize_style_intensity(
            self._first_value(
                getattr(scene, "style_intensity", ""),
                context.get("style_intensity"),
                context.get("outfit_style_intensity"),
            )
        )
        style_hint = self._normalize_style_hint(
            self._first_value(
                getattr(scene, "outfit_style", ""),
                getattr(scene, "style_hint", ""),
                context.get("outfit_style"),
                context.get("style_hint"),
                context.get("manual_style"),
            )
        )
        appeal_boost = bool(
            self._first_value(
                getattr(scene, "enhance_attractiveness", False),
                getattr(scene, "attractiveness_boost", False),
                context.get("enhance_attractiveness", False),
                context.get("attractiveness_boost", False),
            )
        )
        temp_c = getattr(weather, "temp_c", 18)
        condition = self._clean_text(getattr(weather, "condition", "")).lower() or "clear"
        time_of_day = self._clean_text(getattr(scene, "time_of_day", "") or context.get("time_of_day") or "").lower()
        social_presence = self._clean_text(
            context.get("social_presence")
            or getattr(behavior, "social_mode", "")
            or getattr(getattr(behavior, "daily_state", None), "social_presence_mode", "")
        ).lower()
        objects = list(getattr(behavior, "objects", getattr(behavior, "recurring_objects", [])) or [])

        return {
            "scene": scene,
            "context": context,
            "source_items": self._parse_source_items(outfit_summary),
            "city": self._clean_text(context.get("city", "")),
            "day_type": self._clean_text(context.get("day_type", "")).lower(),
            "place_text": place_text,
            "place_type": self._place_type(scene_text),
            "activity_text": activity_text,
            "time_of_day": time_of_day,
            "weather_condition": condition,
            "temp_c": temp_c if isinstance(temp_c, (int, float)) else 18,
            "is_cold": float(temp_c if isinstance(temp_c, (int, float)) else 18) <= 10,
            "is_cool": float(temp_c if isinstance(temp_c, (int, float)) else 18) <= 18,
            "is_warm": float(temp_c if isinstance(temp_c, (int, float)) else 18) >= 24,
            "is_evening": time_of_day in {"evening", "night"},
            "is_morning": "morning" in time_of_day,
            "is_rainy": condition in {"rain", "drizzle", "snow"},
            "style_intensity": style_intensity,
            "style_hint": style_hint,
            "appeal_boost": appeal_boost,
            "mood": self._clean_text(getattr(scene, "mood", "") or context.get("mood") or "").lower(),
            "behavior_mode": self._clean_text(
                getattr(behavior, "self_presentation", "")
                or getattr(behavior, "outfit_behavior_mode", "")
                or getattr(getattr(behavior, "daily_state", None), "self_presentation_mode", "")
            ).lower(),
            "social_presence": social_presence,
            "objects": [self._natural_object_term(obj) for obj in objects if self._natural_object_term(obj)],
        }

    def _compose_contextual_outfit(self, descriptor: Dict[str, Any]) -> str:
        source_map = self._source_map(descriptor["source_items"])
        use_dress = self._should_use_dress(descriptor, source_map)

        if use_dress:
            fragments = [
                self._choose_dress(descriptor, source_map),
                self._choose_layer(descriptor, source_map),
                self._choose_shoes(descriptor, source_map),
                self._choose_accessory(descriptor),
            ]
            if descriptor["style_intensity"] == "bold":
                fragments.append("soft fabric following natural body lines without looking overstyled")
            else:
                fragments.append("natural fabric drape with a few soft wrinkles from real movement")
        else:
            fragments = [
                self._choose_top(descriptor, source_map),
                self._choose_layer(descriptor, source_map),
                self._choose_bottom(descriptor, source_map),
                self._choose_shoes(descriptor, source_map),
                self._choose_accessory(descriptor),
            ]
        fragments = [fragment for fragment in fragments if fragment]
        return self._join_fragments(fragments)

    def _fallback_outfit(self, descriptor: Dict[str, Any]) -> str:
        place_type = descriptor["place_type"]
        if place_type == "airport":
            return self._join_fragments(
                [
                    "neutral travel outfit with a soft knit top",
                    "light jacket worn open with natural sleeve creases",
                    "straight trousers with easy fabric folds",
                    "comfortable sneakers",
                    "minimal crossbody bag and compact carry on kept close",
                ]
            )
        if place_type == "cafe":
            return self._join_fragments(
                [
                    "relaxed casual outfit with a soft cotton top",
                    "light cardigan with slight wrinkles at the elbows",
                    "straight jeans with natural creasing from sitting",
                    "clean low sneakers",
                    "small shoulder bag kept near the table",
                ]
            )
        if place_type == "hotel":
            return self._join_fragments(
                [
                    "soft indoor outfit with a ribbed top",
                    "light cardigan sitting loosely on the shoulders",
                    "easy lounge trousers with gentle rumpling",
                    "flat slides near the bed",
                    "small overnight bag nearby",
                ]
            )
        if place_type == "street":
            return self._join_fragments(
                [
                    "urban casual outfit with a light knit top",
                    "easy jacket with subtle wear at the cuffs",
                    "straight denim with natural movement in the fabric",
                    "walkable sneakers",
                    "crossbody bag resting close to the body",
                ]
            )
        return self._join_fragments(
            [
                "everyday outfit with a soft knit top",
                "light outer layer with slight creases",
                "straight trousers with natural fabric folds",
                "simple sneakers",
                "minimal bag kept nearby",
            ]
        )

    def _validate_generated_outfit(self, outfit: str, descriptor: Dict[str, Any]) -> str:
        cleaned = self._clean_text(outfit)
        if self._is_invalid_value(cleaned):
            raise OutfitGenerationError("Generated outfit is empty")
        if self.CYRILLIC_RE.search(cleaned):
            raise OutfitGenerationError("Generated outfit contains Cyrillic")
        if "." in cleaned:
            raise OutfitGenerationError("Generated outfit must not contain periods")

        parts = [self._clean_text(part) for part in cleaned.split(",") if self._clean_text(part)]
        if len(parts) < 4:
            raise OutfitGenerationError("Generated outfit must contain at least four contextual elements")
        if not re.search(r"[A-Za-z]", cleaned):
            raise OutfitGenerationError("Generated outfit must contain English text")
        lowered = cleaned.lower()
        if any(token in lowered for token in self.EXPLICIT_TOKENS):
            raise OutfitGenerationError("Generated outfit became too explicit")
        if descriptor["place_type"] == "airport" and not any(token in lowered for token in ["bag", "carry on", "sneakers", "jacket", "coat", "layer"]):
            raise OutfitGenerationError("Airport outfit is missing travel-ready context")
        if descriptor["place_type"] == "hotel" and any(token in lowered for token in ["boarding pass", "runway", "gate seating"]):
            raise OutfitGenerationError("Hotel outfit conflicts with the scene")
        if descriptor["is_warm"] and any(token in lowered for token in ["heavy coat", "puffer", "thick wool coat"]):
            raise OutfitGenerationError("Warm-weather outfit is too heavy")
        if descriptor["is_cold"] and not any(token in lowered for token in ["jacket", "cardigan", "coat", "boots", "knit", "layer"]):
            raise OutfitGenerationError("Cold-weather outfit is missing layering")
        if "carry on" in descriptor["objects"] and "carry on" not in lowered and descriptor["place_type"] == "airport":
            raise OutfitGenerationError("Outfit is not aligned with airport objects")
        return cleaned

    def _choose_top(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> str:
        hinted = source_map.get("top")
        if hinted:
            return self._enrich_source_piece(hinted, "top", descriptor)
        style_hint = descriptor["style_hint"]
        intensity = descriptor["style_intensity"]
        if style_hint == "sporty":
            return "clean performance zip top with a relaxed real-life fit"
        if descriptor["place_type"] == "work":
            return "clean knit top with a neat natural fit"
        if intensity == "bold" and (descriptor["is_warm"] or descriptor["place_type"] in {"hotel", "cafe"}):
            return "soft fitted knit top with an open neckline and slight creasing at the waist"
        if style_hint == "elegant":
            return "light blouse with a soft drape and a few natural folds"
        if style_hint == "intimate_soft":
            return "soft ribbed top sitting close to the body with gentle rumpling"
        if descriptor["is_warm"]:
            return "light cotton top with an easy fit and a little fabric movement"
        if descriptor["is_morning"]:
            return "soft knit top with a relaxed fit and slight sleeve wrinkles"
        return "soft knit top with a natural fit and subtle fabric folds"

    def _choose_bottom(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> str:
        hinted = source_map.get("bottom")
        if hinted:
            return self._enrich_source_piece(hinted, "bottom", descriptor)
        style_hint = descriptor["style_hint"]
        if style_hint == "sporty":
            return "tapered joggers with natural bunching at the ankles"
        if descriptor["place_type"] == "work":
            return "tailored trousers with soft creases from sitting and moving"
        if descriptor["style_intensity"] == "bold" and descriptor["is_warm"] and style_hint in {"bold_minimal", "elegant", ""}:
            return "high waisted straight trousers following the silhouette in a natural way"
        if style_hint == "intimate_soft":
            return "easy lounge trousers with gentle wrinkles through the legs"
        if descriptor["is_warm"]:
            return "light straight trousers with natural fabric folds"
        return "straight jeans with natural creasing through the knees"

    def _choose_layer(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> str:
        hinted = source_map.get("layer")
        if hinted:
            return self._enrich_source_piece(hinted, "layer", descriptor)
        if not self._needs_layer(descriptor):
            return ""
        style_hint = descriptor["style_hint"]
        place_type = descriptor["place_type"]
        if descriptor["is_rainy"]:
            return "light weatherproof jacket with lived-in sleeve creases"
        if place_type == "airport":
            return "light jacket worn open with slight wrinkles at the elbows"
        if place_type == "work":
            return "easy blazer sitting naturally rather than perfectly pressed"
        if style_hint == "intimate_soft":
            return "light cardigan slipping loosely over the shoulders"
        if descriptor["style_intensity"] == "bold" and descriptor["is_warm"]:
            return "thin layer left open for shape and movement"
        if descriptor["is_cold"]:
            return "soft cardigan with natural bunching at the sleeves"
        return "light layer worn casually with a few natural folds"

    def _choose_dress(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> str:
        hinted = source_map.get("dress")
        if hinted:
            return self._enrich_source_piece(hinted, "dress", descriptor)
        style_hint = descriptor["style_hint"]
        if descriptor["style_intensity"] == "bold":
            return "soft fitted knit dress with a gentle drape and slight rumpling where the fabric settles"
        if style_hint == "elegant":
            return "simple midi dress with a clean line and natural fabric movement"
        return "soft knit dress with a relaxed fall and lived-in wrinkles"

    def _choose_shoes(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> str:
        hinted = source_map.get("shoes")
        if hinted:
            return self._enrich_source_piece(hinted, "shoes", descriptor)
        place_type = descriptor["place_type"]
        style_hint = descriptor["style_hint"]
        if place_type == "hotel":
            return "flat slides"
        if style_hint == "sporty":
            return "clean trainers"
        if descriptor["is_rainy"] or descriptor["is_cold"]:
            return "comfortable ankle boots"
        if descriptor["style_intensity"] == "bold" and descriptor["is_warm"]:
            return "minimal sandals"
        if place_type == "work" or style_hint == "elegant":
            return "sleek loafers"
        return "comfortable sneakers"

    def _choose_accessory(self, descriptor: Dict[str, Any]) -> str:
        objects = descriptor["objects"]
        place_type = descriptor["place_type"]
        style_hint = descriptor["style_hint"]
        if "carry on" in objects or place_type == "airport":
            return "crossbody bag and compact carry on kept close"
        if place_type == "hotel":
            return "small overnight bag nearby"
        if "coffee cup" in objects or place_type == "cafe":
            if descriptor["social_presence"] == "light_public":
                return "small shoulder bag with sunglasses set aside naturally"
            return "small shoulder bag kept near the table"
        if style_hint == "sporty":
            return "simple cap and crossbody pouch"
        if descriptor["style_intensity"] == "bold":
            return "minimal shoulder bag and one understated piece of jewelry"
        if descriptor["is_evening"]:
            return "small shoulder bag kept close"
        return "minimal bag kept nearby"

    def _enrich_source_piece(self, piece: str, category: str, descriptor: Dict[str, Any]) -> str:
        cleaned = self._clean_text(piece).lower()
        if category == "top":
            if "blouse" in cleaned:
                return "light blouse with a soft drape and a few natural folds"
            if any(token in cleaned for token in ["tank", "camisole"]):
                if descriptor["style_intensity"] == "bold":
                    return "soft fitted tank with clean lines and slight creasing at the waist"
                return "soft tank top with a natural fit and light fabric movement"
            if any(token in cleaned for token in ["shirt", "button"]):
                return "easy shirt worn naturally with relaxed sleeve creases"
            return f"{cleaned} with a natural fit and soft fabric folds"
        if category == "bottom":
            if "jeans" in cleaned or "denim" in cleaned:
                return "straight denim with natural creasing through the knees"
            if "skirt" in cleaned:
                return "simple skirt with soft movement and a slightly lived-in fall"
            if any(token in cleaned for token in ["trousers", "pants"]):
                return "straight trousers with natural fabric folds and a relaxed break at the hem"
            return f"{cleaned} with natural movement in the fabric"
        if category == "layer":
            if any(token in cleaned for token in ["trench", "coat"]):
                return "light coat worn open with slight creases at the sleeves"
            if any(token in cleaned for token in ["cardigan", "hoodie"]):
                return "soft layer worn casually with natural sleeve wrinkles"
            if any(token in cleaned for token in ["blazer", "jacket"]):
                return "easy jacket sitting naturally instead of looking too sharp"
            return f"{cleaned} with a few lived-in creases"
        if category == "dress":
            if descriptor["style_intensity"] == "bold":
                return "soft fitted dress with a gentle drape and slight rumpling where it settles"
            return f"{cleaned} with natural fabric movement and a few real-life wrinkles"
        if category == "shoes":
            if any(token in cleaned for token in ["sneakers", "trainers"]):
                return "comfortable sneakers"
            if any(token in cleaned for token in ["boots", "boot"]):
                return "comfortable ankle boots"
            if any(token in cleaned for token in ["sandals", "heels", "slides", "loafers", "shoes"]):
                return cleaned
            return cleaned
        return cleaned

    def _should_use_dress(self, descriptor: Dict[str, Any], source_map: Dict[str, str]) -> bool:
        if source_map.get("dress"):
            return True
        if descriptor["place_type"] == "airport":
            return False
        if descriptor["style_hint"] == "sporty":
            return False
        if descriptor["style_hint"] == "intimate_soft" and descriptor["place_type"] in {"hotel", "home"}:
            return descriptor["temp_c"] >= 16
        if descriptor["style_hint"] in {"elegant", "bold_minimal"} and not descriptor["is_cold"]:
            return True
        return descriptor["style_intensity"] == "bold" and descriptor["place_type"] in {"hotel", "cafe"} and not descriptor["is_cold"]

    def _needs_layer(self, descriptor: Dict[str, Any]) -> bool:
        if descriptor["place_type"] == "airport":
            return True
        if descriptor["is_cold"] or descriptor["is_rainy"]:
            return True
        if descriptor["place_type"] in {"work", "street"} and descriptor["is_cool"]:
            return True
        if descriptor["style_hint"] == "intimate_soft" and descriptor["place_type"] == "hotel":
            return True
        return descriptor["is_evening"] and not descriptor["is_warm"]

    def _source_map(self, source_items: List[str]) -> Dict[str, str]:
        mapped: Dict[str, str] = {}
        for item in source_items:
            category = self._outfit_category(item)
            if category == "outerwear":
                category = "layer"
            mapped.setdefault(category, item)
        return mapped

    def _parse_source_items(self, outfit_summary: str) -> List[str]:
        cleaned = self._clean_text(outfit_summary)
        if self._is_invalid_value(cleaned):
            return []
        parts = re.split(r"\s*(?:,|\+|/|;)\s*", cleaned)
        normalized: List[str] = []
        for part in parts:
            candidate = self._clean_text(part)
            if not candidate or self._is_invalid_value(candidate) or self.CYRILLIC_RE.search(candidate):
                continue
            key = candidate.lower()
            if key not in {item.lower() for item in normalized}:
                normalized.append(candidate)
        return normalized

    def _resolve_manual_override(self, scene: Any, context: Dict[str, Any]) -> str:
        return self._clean_text(
            self._first_value(
                getattr(scene, "outfit_override", ""),
                getattr(scene, "manual_outfit", ""),
                context.get("outfit_override"),
                context.get("manual_outfit"),
                context.get("outfit"),
                "",
            )
        )

    def _normalize_style_intensity(self, value: Any) -> str:
        token = self._clean_text(value).lower()
        if token in {"expressive", "bold"}:
            return token
        return "normal"

    def _normalize_style_hint(self, value: Any) -> str:
        token = self._clean_text(value).lower().replace(" ", "_")
        allowed = {"casual", "elegant", "sporty", "intimate_soft", "bold_minimal"}
        return token if token in allowed else ""

    def _place_type(self, scene_text: str) -> str:
        lowered = scene_text.lower()
        if any(token in lowered for token in ["airport", "terminal", "boarding", "gate", "flight"]):
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
        if any(token in lowered for token in ["bag", "tote", "scarf", "watch", "glasses", "sunglasses", "jewelry", "necklace", "earrings", "cap", "belt"]):
            return "accessory"
        return "top"

    def _join_fragments(self, fragments: List[str]) -> str:
        deduped: List[str] = []
        seen: set[str] = set()
        for fragment in fragments:
            cleaned = self._clean_text(fragment)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return ", ".join(deduped)

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
