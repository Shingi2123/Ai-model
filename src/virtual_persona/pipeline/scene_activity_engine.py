from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from virtual_persona.models.domain import DayScene


@dataclass
class SceneActivityExpansionEngine:
    state_store: Any

    def _split_csv(self, value: Any) -> List[str]:
        if value is None:
            return []
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    def _scene_signatures(self, scenes: List[Dict[str, Any]]) -> set[str]:
        out = set()
        for row in scenes:
            out.add(
                "|".join(
                    [
                        str(row.get("day_type") or "").strip().lower(),
                        str(row.get("time_block") or "").strip().lower(),
                        str(row.get("location") or "").strip().lower(),
                        str(row.get("description") or "").strip().lower(),
                    ]
                )
            )
        return out

    def _activity_signatures(self, activities: List[Dict[str, Any]]) -> set[str]:
        out = set()
        for row in activities:
            out.add(
                "|".join(
                    [
                        str(row.get("day_type") or "").strip().lower(),
                        str(row.get("time_block") or "").strip().lower(),
                        str(row.get("activity_code") or "").strip().lower(),
                    ]
                )
            )
        return out

    def _scene_seed_pool(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        day_type = context.get("day_type", "day_off")
        city = context.get("city", "")
        life_state = context.get("life_state")
        narrative = context.get("narrative_context")
        season = getattr(life_state, "season", "all")
        fatigue = getattr(life_state, "fatigue_level", 4)
        phase = getattr(narrative, "narrative_phase", "") if narrative else ""

        base = [
            {"time_block": "morning", "location": "home", "description": "Slow breakfast near the window", "mood": "calm", "activity_hint": "slow_breakfast"},
            {"time_block": "afternoon", "location": "city cafe", "description": "Quiet coffee and notes review", "mood": "soft", "activity_hint": "coffee_pause"},
            {"time_block": "evening", "location": "home", "description": "Evening reset with tea and reading", "mood": "reflective", "activity_hint": "reading_evening"},
        ]

        by_day = {
            "work_day": [
                {"time_block": "morning", "location": "airport", "description": "Pre-flight routine with checklists", "mood": "focused", "activity_hint": "preflight_routine"},
                {"time_block": "afternoon", "location": "crew lounge", "description": "Short quiet break between duties", "mood": "composed", "activity_hint": "crew_break"},
                {"time_block": "evening", "location": "hotel room", "description": "Post-flight skincare and wind-down", "mood": "tired-cozy", "activity_hint": "postflight_reset"},
            ],
            "layover_day": [
                {"time_block": "morning", "location": "hotel room", "description": "Slow wake-up and stretch before city walk", "mood": "calm", "activity_hint": "stretching"},
                {"time_block": "afternoon", "location": "city center", "description": "Gentle walk through nearby streets", "mood": "curious", "activity_hint": "city_walk"},
                {"time_block": "evening", "location": "nearby cafe", "description": "Light dinner near the hotel", "mood": "soft", "activity_hint": "light_dinner"},
            ],
            "travel_day": [
                {"time_block": "morning", "location": "airport terminal", "description": "Transit coffee before boarding", "mood": "focused", "activity_hint": "airport_transfer"},
                {"time_block": "afternoon", "location": "aircraft", "description": "Quiet in-between travel hours", "mood": "quiet", "activity_hint": "in_transit"},
                {"time_block": "evening", "location": "arrival hotel", "description": "Check-in and luggage reset", "mood": "tired", "activity_hint": "hotel_checkin"},
            ],
        }
        scenes = by_day.get(day_type, base)

        if phase in {"recovery_phase", "quiet_reset_phase"}:
            scenes = [
                {"time_block": "morning", "location": "home", "description": "Slow morning with no rush and warm drink", "mood": "calm", "activity_hint": "slow_morning"},
                {"time_block": "afternoon", "location": "nearby park", "description": "Short restorative walk and mindful pause", "mood": "soft", "activity_hint": "recovery_walk"},
                {"time_block": "evening", "location": "home", "description": "Quiet evening reset and early wind-down", "mood": "low-energy", "activity_hint": "quiet_day"},
            ]
        elif phase in {"exploration_phase", "creative_phase"}:
            scenes.append(
                {"time_block": "golden_hour", "location": "new district", "description": "Exploring a new corner of the city", "mood": "curious", "activity_hint": "exploration_walk"}
            )

        if fatigue >= 7:
            scenes[-1] = {
                "time_block": "evening",
                "location": "home",
                "description": "Early recovery evening with calm music",
                "mood": "low-energy",
                "activity_hint": "early_sleep",
            }

        story_arc = context.get("story_arc") or {}
        arc_type = str(story_arc.get("arc_type") or "").strip().lower()
        if arc_type == "fitness_journey":
            scenes.append({"time_block": "afternoon", "location": "studio gym", "description": "Structured movement session with gradual progression", "mood": "energized", "activity_hint": "fitness_session"})
        elif arc_type == "social_expansion":
            scenes.append({"time_block": "evening", "location": "community space", "description": "Low-key social meetup in a cozy local spot", "mood": "open", "activity_hint": "social_meetup"})

        diversity = context.get("diversity_metrics") or {}
        if float(diversity.get("novelty_boost", 0.0) or 0.0) >= 0.2:
            scenes.append(
                {
                    "time_block": "golden_hour",
                    "location": "experimental district",
                    "description": "Discovered a new route and spontaneous visual moments",
                    "mood": "curious",
                    "activity_hint": "new_scene_walk",
                }
            )

        for row in scenes:
            row["day_type"] = day_type
            row["city"] = city
            row["season"] = season
        return scenes

    def _activity_seed_pool(self, context: Dict[str, Any], scenes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        life_state = context.get("life_state")
        narrative = context.get("narrative_context")
        day_type = context.get("day_type", "day_off")
        fatigue = int(getattr(life_state, "fatigue_level", 4))
        season = getattr(life_state, "season", "all")
        city = context.get("city", "")
        novelty = float(getattr(narrative, "novelty_pressure", 0.0)) if narrative else 0.0
        activity_balance = float(getattr(narrative, "activity_balance", 0.5)) if narrative else 0.5

        out: List[Dict[str, Any]] = []
        for scene in scenes:
            hint = scene.get("activity_hint", "daily_routine")
            out.append(
                {
                    "activity_code": hint,
                    "activity_label": hint.replace("_", " "),
                    "day_type": day_type,
                    "time_block": scene.get("time_block", "day"),
                    "city": city,
                    "season": season,
                    "mood_fit": scene.get("mood", "calm"),
                    "fatigue_min": max(0, fatigue - 2),
                    "fatigue_max": min(10, fatigue + 2),
                    "weather_fit": "all",
                    "source_context": scene.get("description", ""),
                    "generated_by_ai": True,
                    "status": "candidate",
                    "score": 0.78,
                    "notes": "Generated from continuity-aware scene seed",
                }
            )

        if novelty >= 0.7 or activity_balance <= 0.35:
            out.append(
                {
                    "activity_code": "new_activity_trial",
                    "activity_label": "new activity trial",
                    "day_type": day_type,
                    "time_block": "afternoon",
                    "city": city,
                    "season": season,
                    "mood_fit": "curious",
                    "fatigue_min": 0,
                    "fatigue_max": 7,
                    "weather_fit": "all",
                    "source_context": "narrative_novelty_pressure",
                    "generated_by_ai": True,
                    "status": "candidate",
                    "score": 0.86,
                    "notes": "Injected by narrative engine for life variation",
                }
            )
        return out

    def ensure_candidates(self, context: Dict[str, Any]) -> Tuple[List[DayScene], List[str]]:
        notes: List[str] = []
        existing_scene_candidates = []
        if hasattr(self.state_store, "load_scene_candidates"):
            existing_scene_candidates = self.state_store.load_scene_candidates() or []

        scene_seed = self._scene_seed_pool(context)
        existing_scene_signatures = self._scene_signatures(existing_scene_candidates)

        selected_scene_rows: List[Dict[str, Any]] = []
        for i, row in enumerate(scene_seed, start=1):
            signature = "|".join(
                [
                    str(row.get("day_type") or "").lower(),
                    str(row.get("time_block") or "").lower(),
                    str(row.get("location") or "").lower(),
                    str(row.get("description") or "").lower(),
                ]
            )
            if signature not in existing_scene_signatures and hasattr(self.state_store, "append_scene_candidate"):
                self.state_store.append_scene_candidate(
                    {
                        "candidate_id": f"scene_cand_{context['date'].isoformat()}_{i}",
                        "day_type": row.get("day_type", ""),
                        "time_block": row.get("time_block", ""),
                        "location": row.get("location", ""),
                        "description": row.get("description", ""),
                        "mood": row.get("mood", ""),
                        "activity_hint": row.get("activity_hint", ""),
                        "city": row.get("city", ""),
                        "season": row.get("season", "all"),
                        "source_context": f"life_state:{context.get('day_type')}|{context.get('city')}",
                        "generated_by_ai": True,
                        "status": "candidate",
                        "score": 0.82,
                        "notes": "Auto-generated for continuity expansion",
                    }
                )
            selected_scene_rows.append(row)

        existing_activity_candidates = []
        if hasattr(self.state_store, "load_activity_candidates"):
            existing_activity_candidates = self.state_store.load_activity_candidates() or []

        activity_seed = self._activity_seed_pool(context, selected_scene_rows)
        existing_activity_signatures = self._activity_signatures(existing_activity_candidates)
        for i, row in enumerate(activity_seed, start=1):
            signature = "|".join(
                [
                    str(row.get("day_type") or "").lower(),
                    str(row.get("time_block") or "").lower(),
                    str(row.get("activity_code") or "").lower(),
                ]
            )
            if signature not in existing_activity_signatures and hasattr(self.state_store, "append_activity_candidate"):
                payload = {"candidate_id": f"activity_cand_{context['date'].isoformat()}_{i}", **row}
                self.state_store.append_activity_candidate(payload)

        scenes = [
            DayScene(
                block=row.get("time_block", "day"),
                location=row.get("location", "city"),
                description=row.get("description", "Lifestyle moment"),
                mood=row.get("mood", "calm"),
                time_of_day=row.get("time_block", "day"),
                activity=row.get("activity_hint", ""),
                source="generated",
            )
            for row in selected_scene_rows
        ]

        notes.append("scene_activity_expansion_applied")
        return scenes, notes
