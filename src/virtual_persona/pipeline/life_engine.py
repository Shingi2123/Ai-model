from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from virtual_persona.models.domain import LifeState
from virtual_persona.pipeline.route_engine import RouteEngine


@dataclass
class LifeEngine:
    state_store: Any

    def __post_init__(self) -> None:
        self.route_engine = RouteEngine(self.state_store)

    def build(
        self,
        target_date: date,
        profile: Dict[str, Any],
        calendar: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
    ) -> LifeState:
        home_city = str(profile.get("home_city") or "Prague")
        route = self.route_engine.decide(target_date=target_date, home_city=home_city, calendar=calendar, profile=profile)

        season = self._season(target_date.month)
        holiday_name = self._holiday_name(target_date)
        fatigue_level = self._fatigue(history, target_date)
        mood_base = self._mood(route.day_type, fatigue_level)

        return LifeState(
            date=target_date,
            weekday=target_date.strftime("%A"),
            month=target_date.month,
            season=season,
            is_holiday=bool(holiday_name),
            holiday_name=holiday_name,
            home_city=home_city,
            current_city=route.current_city,
            day_type=route.day_type,
            day_type_reason=route.reason,
            fatigue_level=fatigue_level,
            mood_base=mood_base,
            continuity_note=self._continuity_note(history, route.current_city),
        )

    @staticmethod
    def _season(month: int) -> str:
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"

    @staticmethod
    def _holiday_name(target_date: date) -> str:
        if (target_date.month, target_date.day) == (12, 25):
            return "christmas"
        if (target_date.month, target_date.day) == (1, 1):
            return "new_year"
        return ""

    @staticmethod
    def _fatigue(history: List[Dict[str, Any]], target_date: date) -> int:
        start = target_date - timedelta(days=4)
        recent = [row for row in history if row.get("date") and date.fromisoformat(row["date"]) >= start]
        work_like = sum(1 for row in recent if str(row.get("day_type", "")).strip() in {"work_day", "airport_transfer", "travel_day"})
        return min(10, 2 + work_like * 2)

    @staticmethod
    def _mood(day_type: str, fatigue_level: int) -> str:
        if fatigue_level >= 7:
            return "tired_reflective"
        if day_type in {"layover_day", "travel_day"}:
            return "quiet_curious"
        if day_type == "work_day":
            return "focused"
        return "calm"

    @staticmethod
    def _continuity_note(history: List[Dict[str, Any]], current_city: str) -> str:
        if not history:
            return "fresh_start"
        last_city = str(history[-1].get("city") or "").strip()
        if last_city and last_city != current_city:
            return f"city_transition:{last_city}->{current_city}"
        return "stable_city_arc"
