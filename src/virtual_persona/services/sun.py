from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from virtual_persona.config.settings import AppSettings
from virtual_persona.models.domain import SunSnapshot
from virtual_persona.services.weather import city_coordinates

logger = logging.getLogger(__name__)


class SunService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def _fetch(self, lat: float, lng: float) -> dict:
        query = urlencode(
            {
                "lat": lat,
                "lng": lng,
                "date": "today",
                "formatted": 0,
                "tzid": self.settings.timezone,
            }
        )
        url = f"{self.settings.sun_api_url}?{query}"

        request = Request(
            url,
            headers={
                "User-Agent": "virtual-persona/1.0 (+local-dev)",
                "Accept": "application/json",
            },
        )

        with urlopen(request, timeout=self.settings.request_timeout_seconds) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        status = payload.get("status")
        if status != "OK":
            raise RuntimeError(f"Sun API status is not OK: {status!r}")

        return payload

    def today(self, city: str) -> SunSnapshot:
        lat, lng = city_coordinates(city)
        try:
            payload = self._fetch(lat, lng)
            results = payload["results"]

            sunrise = datetime.fromisoformat(results["sunrise"])
            sunset = datetime.fromisoformat(results["sunset"])

            return SunSnapshot(
                sunrise_local=sunrise,
                sunset_local=sunset,
                source="sunrise-sunset",
            )
        except Exception as exc:
            logger.warning("Sun API failed: %s", exc)
            now = datetime.now(ZoneInfo(self.settings.timezone))
            return SunSnapshot(
                sunrise_local=now.replace(hour=7, minute=0, second=0, microsecond=0),
                sunset_local=now.replace(hour=18, minute=30, second=0, microsecond=0),
                source="fallback",
            )