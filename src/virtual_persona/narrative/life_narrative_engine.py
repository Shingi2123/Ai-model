from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Sequence


@dataclass
class NarrativeContext:
    narrative_phase: str = "routine_stability"
    energy_state: str = "medium"
    rhythm_state: str = "stable"
    novelty_pressure: float = 0.0
    recovery_need: float = 0.0
    social_balance: float = 0.5
    activity_balance: float = 0.5
    location_variation: float = 0.5
    reason: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LifeVariationController:
    scene_repeat_cooldown: int = 3
    activity_repeat_cooldown: int = 2
    location_repeat_cooldown: int = 3

    def _recent_keys(self, memory_rows: Sequence[Dict[str, Any]], key_name: str) -> List[str]:
        rows = sorted(memory_rows, key=lambda r: str(r.get("last_used") or ""), reverse=True)
        return [str(r.get(key_name) or "").strip().lower() for r in rows if str(r.get(key_name) or "").strip()]

    @staticmethod
    def _run_length(values: Sequence[str], target: str) -> int:
        count = 0
        for value in values:
            if value != target:
                break
            count += 1
        return count

    def scene_allowed(self, scene_key: str, scene_memory: Sequence[Dict[str, Any]]) -> bool:
        recent = self._recent_keys(scene_memory, "scene_id")
        return self._run_length(recent, scene_key.lower()) < (self.scene_repeat_cooldown - 1)

    def activity_allowed(self, activity_key: str, activity_memory: Sequence[Dict[str, Any]]) -> bool:
        recent = self._recent_keys(activity_memory, "activity_id")
        return self._run_length(recent, activity_key.lower()) < (self.activity_repeat_cooldown - 1)

    def location_allowed(self, location_key: str, location_memory: Sequence[Dict[str, Any]]) -> bool:
        recent = self._recent_keys(location_memory, "location_id")
        return self._run_length(recent, location_key.lower()) < (self.location_repeat_cooldown - 1)

    def filter_scenes(
        self,
        day_type: str,
        city: str,
        scenes: Sequence[Any],
        scene_memory: Sequence[Dict[str, Any]],
        activity_memory: Sequence[Dict[str, Any]],
        location_memory: Sequence[Dict[str, Any]],
    ) -> List[Any]:
        out: List[Any] = []
        for scene in scenes:
            block = str(getattr(scene, "block", "")).strip()
            location = str(getattr(scene, "location", "")).strip()
            mood = str(getattr(scene, "mood", "")).strip()
            scene_key = f"{day_type}:{block}:{location}".lower()
            activity_key = f"{day_type}:{mood}".lower()
            location_key = f"{city}:{location.lower().replace(' ', '_')}".lower()

            if not self.scene_allowed(scene_key, scene_memory):
                continue
            if not self.activity_allowed(activity_key, activity_memory):
                continue
            if not self.location_allowed(location_key, location_memory):
                continue
            out.append(scene)
        return out


@dataclass
class LifeNarrativeEngine:
    state_store: Any
    lookback_days: int = 14

    def __post_init__(self) -> None:
        self.variation_controller = LifeVariationController()

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except Exception:
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except Exception:
            return default

    def _load_rows(self, method_name: str) -> List[Dict[str, Any]]:
        if not hasattr(self.state_store, method_name):
            return []
        try:
            rows = getattr(self.state_store, method_name)() or []
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    def _recent_window(self, rows: Sequence[Dict[str, Any]], target_date: date) -> List[Dict[str, Any]]:
        cutoff = target_date - timedelta(days=self.lookback_days)
        out: List[Dict[str, Any]] = []
        for row in rows:
            raw = row.get("date") or row.get("last_used")
            if not raw:
                continue
            try:
                d = date.fromisoformat(str(raw)[:10])
            except Exception:
                continue
            if d <= target_date and d >= cutoff:
                out.append({**row, "_d": d})
        out.sort(key=lambda r: r.get("_d"), reverse=True)
        return out

    def _derive_energy_state(self, fatigue_level: int, day_rows: Sequence[Dict[str, Any]]) -> str:
        activity_count = len(day_rows)
        if fatigue_level >= 7 or activity_count >= 30:
            return "low"
        if fatigue_level <= 3 and activity_count < 18:
            return "high"
        return "medium"

    def _derive_rhythm(self, day_rows: Sequence[Dict[str, Any]], activity_rows: Sequence[Dict[str, Any]]) -> str:
        active_days = 0
        for row in day_rows[:7]:
            if str(row.get("day_type") or "") in {"work_day", "travel_day", "airport_transfer"}:
                active_days += 1
        if active_days >= 4:
            return "overloaded"
        if active_days <= 1 and len(activity_rows) <= 6:
            return "slow"

        dates = [row.get("_d") for row in day_rows[:7] if row.get("_d")]
        if len(dates) >= 3:
            gaps = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
            if any(g > 2 for g in gaps):
                return "irregular"
        return "stable"

    def _novelty_pressure(
        self,
        day_rows: Sequence[Dict[str, Any]],
        scene_rows: Sequence[Dict[str, Any]],
        activity_rows: Sequence[Dict[str, Any]],
        location_rows: Sequence[Dict[str, Any]],
    ) -> float:
        if not day_rows:
            return 0.2
        cities = [str(r.get("city") or "").strip().lower() for r in day_rows[:10] if r.get("city")]
        unique_city_ratio = len(set(cities)) / max(1, len(cities))

        scene_usage = [self._safe_int(r.get("usage_count"), 0) for r in scene_rows[:20]]
        activity_usage = [self._safe_int(r.get("usage_count"), 0) for r in activity_rows[:20]]
        location_usage = [self._safe_int(r.get("usage_count"), 0) for r in location_rows[:20]]

        repetitive_pressure = (
            (sum(scene_usage) / max(1, len(scene_usage)) if scene_usage else 0)
            + (sum(activity_usage) / max(1, len(activity_usage)) if activity_usage else 0)
            + (sum(location_usage) / max(1, len(location_usage)) if location_usage else 0)
        ) / 30.0
        pressure = min(1.0, max(0.0, repetitive_pressure + (1.0 - unique_city_ratio) * 0.4))
        return round(pressure, 2)

    def _phase(
        self,
        rhythm_state: str,
        energy_state: str,
        novelty_pressure: float,
        day_rows: Sequence[Dict[str, Any]],
        life_state_rows: Sequence[Dict[str, Any]],
    ) -> tuple[str, str]:
        work_streak = 0
        for row in day_rows:
            day_type = str(row.get("day_type") or "")
            if day_type in {"work_day", "travel_day", "airport_transfer"}:
                work_streak += 1
            else:
                break

        fatigue = 0
        if life_state_rows:
            fatigue = self._safe_int(life_state_rows[0].get("fatigue_level"), 0)

        if rhythm_state == "overloaded" or fatigue >= 8:
            return "recovery_phase", "overload_detected"
        if novelty_pressure >= 0.72:
            return "exploration_phase", "high_novelty_pressure"
        if work_streak >= 3:
            return "work_focus_phase", "work_streak"

        social_hits = sum(1 for row in day_rows[:6] if str(row.get("day_type") or "") in {"layover_day", "day_off"})
        if social_hits >= 4:
            return "social_phase", "social_density"
        if energy_state == "low":
            return "quiet_reset_phase", "low_energy"
        return "routine_stability", "default_stable"

    def build_context(self, target_date: date, base_context: Dict[str, Any]) -> NarrativeContext:
        life_state_rows = self._recent_window(self._load_rows("load_life_state"), target_date)
        calendar_rows = self._recent_window(self._load_rows("load_calendar"), target_date)
        history_rows = self._recent_window(self._load_rows("load_content_history"), target_date)
        scene_rows = self._recent_window(self._load_rows("load_scene_memory"), target_date)
        activity_rows = self._recent_window(self._load_rows("load_activity_memory"), target_date)
        location_rows = self._recent_window(self._load_rows("load_location_memory"), target_date)

        fatigue = self._safe_int(getattr(base_context.get("life_state"), "fatigue_level", 0), 0)
        energy = self._derive_energy_state(fatigue, history_rows)
        rhythm = self._derive_rhythm(calendar_rows, activity_rows)
        novelty = self._novelty_pressure(calendar_rows, scene_rows, activity_rows, location_rows)
        recovery_need = round(min(1.0, (fatigue / 10.0) + (0.35 if rhythm == "overloaded" else 0.0)), 2)

        phase, reason = self._phase(rhythm, energy, novelty, calendar_rows, life_state_rows)

        social_balance = round(min(1.0, len([r for r in calendar_rows[:10] if str(r.get("day_type") or "") == "layover_day"]) / 4.0), 2)
        activity_balance = round(min(1.0, len(activity_rows[:10]) / 10.0), 2)
        location_variation = round(min(1.0, len({str(r.get('location_id') or '') for r in location_rows[:10]}) / 6.0), 2)

        context = NarrativeContext(
            narrative_phase=phase,
            energy_state=energy,
            rhythm_state=rhythm,
            novelty_pressure=novelty,
            recovery_need=recovery_need,
            social_balance=social_balance,
            activity_balance=activity_balance,
            location_variation=location_variation,
            reason=reason,
        )
        self.persist_context(target_date, context)
        return context

    def persist_context(self, target_date: date, narrative_context: NarrativeContext) -> None:
        if hasattr(self.state_store, "append_narrative_memory"):
            self.state_store.append_narrative_memory(
                {
                    "date": target_date.isoformat(),
                    **narrative_context.to_dict(),
                }
            )

