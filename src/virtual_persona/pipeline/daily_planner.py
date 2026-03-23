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

    def _candidate_rows(self, day_type: str) -> List[Dict[str, Any]]:
        if not self.state_store or not hasattr(self.state_store, "load_scene_candidates"):
            return []
        try:
            rows = self.state_store.load_scene_candidates() or []
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for row in rows:
            if str(row.get("day_type", "")).strip() != day_type:
                continue
            status = str(row.get("status") or "candidate").strip().lower()
            if status not in {"candidate", "active", "approved"}:
                continue
            out.append(row)
        return out

    def _load_scenes_from_sheet(self, day_type: str) -> List[DayScene]:
        if not self.state_store or not hasattr(self.state_store, "load_scene_library"):
            return []

        try:
            rows = self.state_store.load_scene_library() or []
        except Exception:
            rows = []

        rows = rows + self._candidate_rows(day_type)

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
                    activity=str(row.get("activity_hint") or ""),
                    source="generated" if row.get("generated_by_ai") else "library",
                )
            )

        return scenes

    def build_day(self, context: Dict) -> List[DayScene]:
        narrative = context.get("narrative_context")
        narrative_phase = getattr(narrative, "narrative_phase", "") if narrative else ""
        energy_state = getattr(narrative, "energy_state", "") if narrative else ""
        behavior = context.get("behavioral_context")
        daily_behavior = getattr(behavior, "daily_state", None)

        day_type = context["day_type"]
        if narrative_phase in {"recovery_phase", "quiet_reset_phase"}:
            day_type = "day_off"
        elif narrative_phase in {"exploration_phase", "travel_phase"} and context.get("day_type") == "day_off":
            day_type = "layover_day"

        story_arc = context.get("story_arc") or {}
        arc_type = str(story_arc.get("arc_type") or "").strip().lower()
        if arc_type == "travel_phase":
            day_type = "travel_day"
        elif arc_type == "fitness_journey" and day_type == "day_off":
            day_type = "layover_day"

        sheet_scenes = self._load_scenes_from_sheet(day_type)
        if sheet_scenes:
            sheet_scenes = self._apply_behavioral_bias(sheet_scenes, context, daily_behavior)
            if energy_state == "low":
                return sheet_scenes[:2]
            return sheet_scenes

        template = self.DAYTYPE_TEMPLATES.get(day_type)

        if not template:
            template = [
                ("morning", "home", "Slow morning at home with coffee and light planning", "calm"),
                ("afternoon", "city cafe", "Quiet time in a cafe with reading or notes", "soft"),
                ("evening", "home", "Calm evening indoors after the day", "reflective"),
            ]

        scenes = [
            DayScene(block=b, location=l, description=d, mood=m, time_of_day=b, activity="", source="template")
            for b, l, d, m in template
        ]
        scenes = self.apply_behavioral_bias(scenes, context)
        if energy_state == "low":
            return scenes[:2]
        return scenes

    def apply_behavioral_bias(self, scenes: List[DayScene], context: Dict[str, Any]) -> List[DayScene]:
        behavior = context.get("behavioral_context")
        return self._apply_behavioral_bias(scenes, context, getattr(behavior, "daily_state", None))

    def _apply_behavioral_bias(self, scenes: List[DayScene], context: Dict[str, Any], daily_behavior: Any) -> List[DayScene]:
        behavior = context.get("behavioral_context")
        if not behavior:
            return scenes

        energy = str(getattr(behavior, "energy_level", "medium") or "medium")
        social_mode = str(getattr(behavior, "social_mode", "alone") or "alone")
        habit = str(getattr(behavior, "habit", "") or "")
        place_anchor = str(getattr(behavior, "place_anchor", "") or "")
        objects = list(getattr(behavior, "objects", []) or [])
        emotional_arc = str(getattr(behavior, "emotional_arc", "routine") or "routine")
        self_presentation = str(getattr(behavior, "self_presentation", "relaxed") or "relaxed")

        anchor_locations = {
            "hotel_window": "hotel room",
            "kitchen_corner": "home kitchen",
            "terminal_gate": "airport terminal",
            "cafe_corner": "cafe",
        }
        movement_hint = {
            "low": "still posture",
            "medium": "natural pause moment",
            "high": "slow relaxed movement",
        }[energy]
        social_hint = {
            "alone": "no other people in frame",
            "light_public": "soft background people",
            "social": "shared public atmosphere",
        }[social_mode]
        interaction_hint = {
            "window_pause": "touching the window lightly",
            "coffee_moment": "holding a coffee cup",
            "packing": "handling luggage",
            "slow_walk": "walking with a bag",
            "none": "resting hands naturally",
        }[habit or "none"]

        adjusted: List[DayScene] = []
        for idx, scene in enumerate(scenes):
            location = scene.location.lower()
            target_location = anchor_locations.get(place_anchor, scene.location)
            desc = scene.description
            mood = scene.mood
            activity = scene.activity
            scene_family = ""
            location_family = "private" if any(token in target_location.lower() for token in ["hotel", "home", "room", "kitchen"]) else "public"

            if idx == 0:
                scene.location = target_location
                desc = f"{desc} at the familiar {place_anchor.replace('_', ' ')}"

            if energy == "low":
                if idx == 0 and place_anchor in {"kitchen_corner", "hotel_window"}:
                    scene.location = anchor_locations.get(place_anchor, scene.location)
                mood = "calm" if emotional_arc != "transition" else "reflective"
                activity = activity or "still_pause"
                desc = f"{desc}, {movement_hint}, {interaction_hint}"
                scene_family = "static"
            elif energy == "high":
                if idx == 1:
                    scene.location = "city street" if place_anchor != "terminal_gate" else "airport terminal"
                activity = activity or "walking"
                desc = f"{desc}, {movement_hint}, {interaction_hint}"
                mood = "curious" if emotional_arc == "arrival" else "focused"
                scene_family = "movement"
            else:
                activity = activity or "daily_pause"
                desc = f"{desc}, {movement_hint}, {interaction_hint}"
                scene_family = "anchored"

            if social_mode == "alone":
                desc = f"{desc}, {social_hint}"
            elif social_mode == "light_public":
                desc = f"{desc}, {social_hint}"
            else:
                desc = f"{desc}, {social_hint}"

            if objects:
                desc = f"{desc}, with {' and '.join(objects[:2])} nearby"
            if emotional_arc == "arrival":
                desc = f"{desc}, with the feeling of a new place"
            elif emotional_arc == "transition":
                desc = f"{desc}, before moving on again"
            elif emotional_arc == "reflection":
                desc = f"{desc}, in a more reflective rhythm"

            if self_presentation == "focused":
                mood = "focused"
            elif self_presentation == "soft":
                mood = "soft"
            elif self_presentation == "transitional":
                mood = "reflective"

            adjusted.append(
                DayScene(
                    block=scene.block,
                    location=scene.location,
                    description=desc,
                    mood=mood,
                    time_of_day=scene.time_of_day,
                    activity=activity,
                    source=scene.source,
                    scene_family=scene_family or ("private" if location_family == "private" else "quiet_public"),
                    action_family=behavior.action_family or activity or "daily_life",
                    location_family=location_family,
                )
            )
        return adjusted
