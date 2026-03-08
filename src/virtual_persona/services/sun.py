from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from virtual_persona.config.settings import AppSettings
from virtual_persona.models.domain import SunSnapshot
from virtual_persona.services.weather import city_coordinates

logger = logging.getLogger(__name__)


class SunService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def _fetch(self, lat: float, lng: float) -> dict:
        query = urlencode({"lat": lat, "lng": lng, "formatted": 0})
        with urlopen(f"{self.settings.sun_api_url}?{query}", timeout=self.settings.request_timeout_seconds) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def today(self, city: str) -> SunSnapshot:
        lat, lng = city_coordinates(city)
        try:
            payload = self._fetch(lat, lng)
            results = payload["results"]
            sunrise = datetime.fromisoformat(results["sunrise"].replace("Z", "+00:00")).astimezone(ZoneInfo(self.settings.timezone))
            sunset = datetime.fromisoformat(results["sunset"].replace("Z", "+00:00")).astimezone(ZoneInfo(self.settings.timezone))
            return SunSnapshot(sunrise_local=sunrise, sunset_local=sunset, source="sunrise-sunset")
        except Exception as exc:
            logger.warning("Sun API failed: %s", exc)
            now = datetime.now(ZoneInfo(self.settings.timezone))
            return SunSnapshot(
                sunrise_local=now.replace(hour=7, minute=0, second=0, microsecond=0),
                sunset_local=now.replace(hour=18, minute=30, second=0, microsecond=0),
                source="fallback",
            )
