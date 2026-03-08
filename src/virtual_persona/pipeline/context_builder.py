from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

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

    def build(self, target_date: date | None = None, override_city: str | None = None) -> Dict[str, Any]:
        target_date = target_date or date.today()
        with Path("config/character_bible.example.json").open("r", encoding="utf-8") as f:
            character = CharacterBible.from_dict(json.load(f))

        calendar = self.state_store.load_calendar()
        entry = next((e for e in calendar if e["date"] == target_date.isoformat()), None)
        city = override_city or (entry["city"] if entry else self.settings.default_city)
        day_type = entry["day_type"] if entry else "city_walk"

        weather = self.weather_service.current(city)
        sun = self.sun_service.today(city)

        history = self.state_store.load_content_history()
        history_cutoff = target_date - timedelta(days=5)
        recent_history = [h for h in history if date.fromisoformat(h["date"]) >= history_cutoff]

        return {
            "date": target_date,
            "character": character,
            "city": city,
            "day_type": day_type,
            "weather": weather,
            "sun": sun,
            "recent_history": recent_history,
        }
