from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from virtual_persona.models.domain import RouteDecision


@dataclass
class RouteEngine:
    state_store: Any

    def decide(self, target_date: date, home_city: str, calendar: List[Dict[str, Any]], profile: Dict[str, Any]) -> RouteDecision:
        if target_date.weekday() >= 5:
            return RouteDecision(current_city=home_city, day_type="day_off", reason="weekend_home_recovery")

        yday = target_date - timedelta(days=1)
        prev = next((row for row in calendar if row.get("date") == yday.isoformat()), None)
        prev_city = str(prev.get("city", "")).strip() if prev else ""
        prev_day_type = str(prev.get("day_type", "")).strip() if prev else ""

        if prev_day_type == "work_day" and prev_city and prev_city != home_city:
            return RouteDecision(
                current_city=prev_city,
                day_type="layover_day",
                reason="continue_layover_after_work_day",
            )

        route_pool = []
        if self.state_store and hasattr(self.state_store, "load_route_pool"):
            try:
                route_pool = self.state_store.load_route_pool() or []
            except Exception:
                route_pool = []

        city = self._pick_city(route_pool, home_city, target_date.day)
        if city != home_city:
            return RouteDecision(current_city=city, day_type="work_day", reason="scheduled_route_pool_rotation")

        return RouteDecision(current_city=home_city, day_type="day_off", reason="default_home_day")

    @staticmethod
    def _pick_city(route_pool: List[Dict[str, Any]], home_city: str, seed_day: int) -> str:
        if not route_pool:
            return home_city

        normalized = []
        for row in route_pool:
            destination = str(row.get("destination_city", "")).strip()
            active = str(row.get("active", "1")).strip().lower()
            if destination and active not in {"0", "false", "no"}:
                normalized.append(destination)

        if not normalized:
            return home_city

        return normalized[(seed_day - 1) % len(normalized)]
