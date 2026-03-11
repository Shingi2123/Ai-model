from __future__ import annotations

from typing import Dict, List, Any

from virtual_persona.models.domain import DayScene


class DailyPlanner:
    DAYTYPE_TEMPLATES = {
        "hotel_rest": [
            ("morning", "hotel room", "Slow coffee by the window and planning the day", "calm"),
            ("afternoon", "hotel lounge", "Reading and journaling with soft ambient music", "cozy"),
            ("evening", "nearby cafe", "Quiet dinner and reflective walk back", "soft"),
        ],
        "airport_transfer": [
            ("morning", "hotel checkout", "Packing essentials and short espresso", "focused"),
            ("afternoon", "airport terminal", "Check-in, lounge time, and runway view", "transit"),
            ("evening", "arrival hotel", "Late check-in and room settling ritual", "tired-cozy"),
        ],
        "day_off": [
            ("morning", "home", "Slow morning at home with coffee and light planning", "calm"),
            ("afternoon", "city cafe", "Quiet time in a cafe with reading or notes", "soft"),
            ("evening", "home", "Calm evening indoors after the day", "reflective"),
        ],
        "work_day": [
            ("morning", "airport", "Early airport routine before the flight", "focused"),
            ("afternoon", "aircraft", "Working flight hours with calm professional rhythm", "composed"),
            ("evening", "hotel room", "Quiet rest after the flight and a short reset", "tired"),
        ],
        "layover_day": [
            ("morning", "hotel room", "Slow hotel morning and getting ready for a short city break", "calm"),
            ("afternoon", "city center", "A few quiet hours walking through the city during layover", "curious"),
            ("evening", "cafe", "Light dinner or coffee before returning to the hotel", "soft"),
        ],
        "travel_day": [
            ("morning", "airport", "Transit through the terminal with coffee and carry-on", "focused"),
            ("afternoon", "airplane", "Travel hours between cities with a calm reflective mood", "quiet"),
            ("evening", "hotel room", "Arrival, check-in and short rest after the trip", "tired"),
        ],
    }

    def __init__(self, state_store=None) -> None:
        self.state_store = state_store

    def _scene_allowed_by_memory(self, day_type: str, row: Dict[str, Any]) -> bool:
        if not self.state_store or not hasattr(self.state_store, "load_scene_memory"):
            return True
        try:
            memory_rows = self.state_store.load_scene_memory() or []
        except Exception:
            return True

        scene_key = f"{day_type}:{str(row.get('time_block', '')).strip()}:{str(row.get('location', '')).strip()}"
        memory_row = next((m for m in memory_rows if str(m.get("scene_id") or "") == scene_key), None)
        if not memory_row:
            return True

        status = str(memory_row.get("status") or "active").strip().lower()
        return status not in {"overused", "temporary_pause", "inactive"}

    def _load_scenes_from_sheet(self, day_type: str) -> List[DayScene]:
        if not self.state_store or not hasattr(self.state_store, "load_scene_library"):
            return []

        try:
            rows = self.state_store.load_scene_library() or []
        except Exception:
            return []

        matched_rows: List[Dict[str, Any]] = []
        for row in rows:
            row_day_type = str(row.get("day_type", "")).strip()
            if row_day_type == day_type:
                if not self._scene_allowed_by_memory(day_type, row):
                    continue
                matched_rows.append(row)

        if not matched_rows:
            return []

        time_order = {
            "early_morning": 1,
            "morning": 2,
            "late_morning": 3,
            "noon": 4,
            "afternoon": 5,
            "golden_hour": 6,
            "evening": 7,
            "night": 8,
        }

        matched_rows.sort(key=lambda r: time_order.get(str(r.get("time_block", "")).strip(), 99))

        scenes: List[DayScene] = []
        for row in matched_rows[:3]:
            time_block = str(row.get("time_block", "")).strip() or "day"
            location = str(row.get("location", "")).strip() or "unknown"
            description = str(row.get("description", "")).strip() or "Lifestyle moment"
            mood = str(row.get("mood", "")).strip() or "calm"

            scenes.append(
                DayScene(
                    block=time_block,
                    location=location,
                    description=description,
                    mood=mood,
                    time_of_day=time_block,
                )
            )

        return scenes

    def build_day(self, context: Dict) -> List[DayScene]:
        sheet_scenes = self._load_scenes_from_sheet(context["day_type"])
        if sheet_scenes:
            return sheet_scenes

        template = self.DAYTYPE_TEMPLATES.get(context["day_type"])

        if not template:
            template = [
                ("morning", "home", "Slow morning at home with coffee and light planning", "calm"),
                ("afternoon", "city cafe", "Quiet time in a cafe with reading or notes", "soft"),
                ("evening", "home", "Calm evening indoors after the day", "reflective"),
            ]

        return [
            DayScene(block=b, location=l, description=d, mood=m, time_of_day=b)
            for b, l, d, m in template
        ]
