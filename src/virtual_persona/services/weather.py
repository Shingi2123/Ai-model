from __future__ import annotations

import json
import logging
from typing import Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from virtual_persona.config.settings import AppSettings, load_settings_yaml
from virtual_persona.models.domain import WeatherSnapshot

logger = logging.getLogger(__name__)


class WeatherService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.fallback_config = load_settings_yaml()["fallbacks"]

    @staticmethod
    def normalize_condition(main: str, cloudiness: int, rain_mm: float = 0.0) -> str:
        main_l = main.lower()
        if "rain" in main_l or rain_mm > 0:
            return "rain_light" if rain_mm < 3 else "rain_heavy"
        if "snow" in main_l:
            return "snow"
        if cloudiness > 70:
            return "cloudy"
        if cloudiness > 35:
            return "mild_clouds"
        return "clear"

    def _fetch(self, city: str) -> dict:
        query = urlencode({"q": city, "appid": self.settings.openweather_api_key, "units": "metric"})
        url = f"{self.settings.openweather_base_url}/weather?{query}"
        with urlopen(url, timeout=self.settings.request_timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def current(self, city: str) -> WeatherSnapshot:
        if not self.settings.openweather_api_key:
            return self._fallback(city, reason="missing_api_key")
        try:
            payload = self._fetch(city)
            main = payload["weather"][0]["main"]
            cloudiness = int(payload["clouds"]["all"])
            rain_mm = float(payload.get("rain", {}).get("1h", 0.0))
            return WeatherSnapshot(
                city=city,
                temp_c=float(payload["main"]["temp"]),
                condition=self.normalize_condition(main, cloudiness, rain_mm),
                humidity=int(payload["main"]["humidity"]),
                wind_speed=float(payload["wind"].get("speed", 0.0)),
                cloudiness=cloudiness,
                source="openweather",
            )
        except (URLError, KeyError, ValueError) as exc:
            logger.warning("Weather API failed for %s: %s", city, exc)
            return self._fallback(city, reason="api_failure")

    def _fallback(self, city: str, reason: str) -> WeatherSnapshot:
        weather_fallback = self.fallback_config["weather"]
        return WeatherSnapshot(
            city=city,
            temp_c=float(weather_fallback["temp_c"]),
            condition=weather_fallback["condition"],
            humidity=55,
            wind_speed=2.0,
            cloudiness=35,
            source=f"fallback:{reason}",
        )


def city_coordinates(city: str) -> Tuple[float, float]:
    fallback = load_settings_yaml()["fallbacks"]["city_coordinates"]
    lat, lng = fallback.get(city, fallback["Paris"])
    return float(lat), float(lng)
