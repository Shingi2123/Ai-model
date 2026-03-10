from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from virtual_persona.config.settings import AppSettings
from virtual_persona.models.domain import CharacterBible
from virtual_persona.services.sun import SunService
from virtual_persona.services.weather import WeatherService
from virtual_persona.storage.state_store import LocalStateStore


class ContextBuilder:
    def __init__(self, settings: AppSettings, state_store: LocalStateStore) -> None:
        self.settings = settings
        self.state_store = state_store
        self.weather_service = WeatherService(settings)
        self.sun_service = SunService(settings)

    def _split_csv(self, value: Any) -> list[str]:
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def _build_character_from_profile(self, profile: Dict[str, Any]) -> CharacterBible:
        payload = {
            "name": profile.get("display_name") or profile.get("display_name_latin") or "Alina Volkova",
            "age": int(profile.get("age") or 22),
            "bio": profile.get("bio_long") or profile.get("bio_short") or "Virtual flight attendant based in Prague.",
            "appearance": {
                "hair_color": profile.get("appearance_hair_color") or "светло-каштановые",
                "hair_length": profile.get("appearance_hair_length") or "длинные",
                "eye_color": profile.get("appearance_eye_color") or "зелёные",
                "skin_tone": profile.get("appearance_skin_tone") or "светлая кожа",
                "body_type": profile.get("appearance_body_type") or "стройное",
            },
            "personality": self._split_csv(
                profile.get("personality_core") or profile.get("personality_traits")
            ),
            "interests": self._split_csv(profile.get("interests")),
            "favorite_places": self._split_csv(
                profile.get("favorite_hobbies") or profile.get("comfort_zones") or profile.get("home_city")
            ),
            "style": {
                "preferred": self._split_csv(
                    profile.get("style_profile") or profile.get("favorite_clothing_styles")
                ),
                "disliked": self._split_csv(
                    profile.get("disliked_situations")
                ),
                "palette": self._split_csv(
                    profile.get("favorite_colors") or profile.get("visual_palette")
                ),
            },
            "canon_rules": self._split_csv(
                profile.get("hard_constraints")
            ),
            "boundaries": self._split_csv(
                profile.get("hard_constraints")
            ),
        }

        # страховка от пустых списков
        if not payload["personality"]:
            payload["personality"] = ["спокойная", "наблюдательная", "романтичная"]
        if not payload["interests"]:
            payload["interests"] = ["путешествия", "кофе", "прогулки по городам"]
        if not payload["favorite_places"]:
            payload["favorite_places"] = ["Прага", "кофейни", "аэропорты"]
        if not payload["style"]["preferred"]:
            payload["style"]["preferred"] = ["элегантный повседневный стиль"]
        if not payload["style"]["palette"]:
            payload["style"]["palette"] = ["бежевый", "кремовый", "белый"]
        if not payload["canon_rules"]:
            payload["canon_rules"] = ["внешность должна оставаться стабильной"]
        if not payload["boundaries"]:
            payload["boundaries"] = ["без нереалистичной роскоши"]

        return CharacterBible.from_dict(payload)

    def build(self, target_date: date | None = None, override_city: str | None = None) -> Dict[str, Any]:
        target_date = target_date or date.today()

        profile = self.state_store.load_character_profile()
        character = self._build_character_from_profile(profile)

        calendar = self.state_store.load_calendar()

        entry = next(
            (e for e in calendar if e.get("date") == target_date.isoformat()),
            None
        )

        if override_city:
            city = override_city
        elif entry:
            city = entry.get("city", self.settings.default_city)
        else:
            city = profile.get("home_city") or self.settings.default_city

        if entry:
            day_type = entry.get("day_type", "day_off")
        else:
            day_type = "day_off"

        weather = self.weather_service.current(city)
        sun = self.sun_service.today(city)

        history = self.state_store.load_content_history()
        history_cutoff = target_date - timedelta(days=5)

        recent_history = [
            h for h in history
            if date.fromisoformat(h["date"]) >= history_cutoff
        ]

        return {
            "date": target_date,
            "character": character,
            "city": city,
            "day_type": day_type,
            "weather": weather,
            "sun": sun,
            "recent_history": recent_history,
        }