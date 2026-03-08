from __future__ import annotations

from typing import Dict, List

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
    }

    def build_day(self, context: Dict) -> List[DayScene]:
        template = self.DAYTYPE_TEMPLATES.get(context["day_type"], [
            ("morning", "cozy cafe", "Breakfast coffee and notes for the route", "calm"),
            ("afternoon", "old town street", "Unhurried city walk with architecture details", "curious"),
            ("evening", "riverside", "Golden hour stroll and warm drink", "reflective"),
        ])
        return [
            DayScene(block=b, location=l, description=d, mood=m, time_of_day=b)
            for b, l, d, m in template
        ]
