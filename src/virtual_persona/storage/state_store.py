from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    from google.oauth2.service_account import Credentials
    import gspread
except Exception:  # optional dependency for local mode
    Credentials = None
    gspread = None

from virtual_persona.models.domain import DailyPackage

logger = logging.getLogger(__name__)


class LocalStateStore:
    def __init__(self, base_dir: str = "data/state") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _read_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    def load_calendar(self) -> List[Dict[str, Any]]:
        return self._read_json(
            self.base_dir / "daily_calendar.json",
            self._read_json(Path("data/samples/daily_calendar.sample.json"), []),
        )

    def load_content_history(self) -> List[Dict[str, Any]]:
        return self._read_json(
            self.base_dir / "content_history.json",
            self._read_json(Path("data/samples/content_history.sample.json"), []),
        )

    def load_content_moment_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "content_moment_memory.json", [])

    def load_publishing_plan(self, target_date: str | None = None) -> List[Dict[str, Any]]:
        rows = self._read_json(self.base_dir / "publishing_plan.json", [])
        if target_date:
            return [r for r in rows if str(r.get("date")) == target_date]
        return rows

    def append_publishing_plan(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "publishing_plan.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def load_posting_rules(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "posting_rules.json", [])

    def append_delivery_log(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "delivery_log.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def load_character_profile(self) -> Dict[str, Any]:
        return {}

    def load_cities(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "cities.json", [])

    def load_wardrobe(self) -> List[Dict[str, Any]]:
        return []

    def load_wardrobe_items(self) -> List[Dict[str, Any]]:
        rows = self._read_json(self.base_dir / "wardrobe_items.json", [])
        if rows:
            return rows
        return self.load_wardrobe()

    def load_outfit_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "outfit_memory.json", [])

    def load_scene_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "scene_memory.json", [])

    def load_activity_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "activity_memory.json", [])

    def load_location_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "location_memory.json", [])

    def save_scene_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "scene_memory.json", rows)

    def save_activity_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "activity_memory.json", rows)

    def save_location_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "location_memory.json", rows)

    def load_life_state(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "life_state.json", [])

    def load_narrative_memory(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "narrative_memory.json", [])

    def load_scene_candidates(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "scene_candidates.json", [])

    def load_activity_candidates(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "activity_candidates.json", [])

    def load_world_candidates(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "world_candidates.json", [])

    def append_world_candidate(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "world_candidates.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def load_story_arcs(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "story_arcs.json", [])

    def append_story_arc(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "story_arcs.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def save_story_arcs(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "story_arcs.json", rows)

    def load_activity_evolution(self) -> List[Dict[str, Any]]:
        return self._read_json(self.base_dir / "activity_evolution.json", [])

    def append_activity_evolution(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "activity_evolution.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def load_prompt_templates(self) -> Dict[str, str]:
        return {}

    def load_prompt_blocks(self) -> Dict[str, str]:
        return {}

    def load_route_pool(self) -> List[Dict[str, Any]]:
        return []

    def save_content_package(self, package: DailyPackage) -> Path:
        output_path = Path("data/outputs") / f"{package.date.isoformat()}_package.json"
        self._write_json(output_path, package.to_dict())
        return output_path

    def append_history(self, package: DailyPackage) -> None:
        history_path = self.base_dir / "content_history.json"
        history = self._read_json(history_path, [])
        caption = getattr(package.content, "post_caption", "") if hasattr(package, "content") else ""
        last_scene = package.scenes[-1] if package.scenes else None

        history.append(
            {
                "date": package.date.isoformat(),
                "city": package.city,
                "day_type": package.day_type,
                "scenes": " | ".join(s.description for s in package.scenes),
                "scene_moment": getattr(last_scene, "scene_moment", "") if last_scene else "",
                "scene_source": getattr(last_scene, "scene_source", "") if last_scene else "",
                "scene_moment_type": getattr(last_scene, "scene_moment_type", "") if last_scene else "",
                "moment_signature": getattr(last_scene, "moment_signature", "") if last_scene else "",
                "visual_focus": getattr(last_scene, "visual_focus", "") if last_scene else "",
                "outfit_ids": ", ".join(package.outfit.item_ids),
                "post_caption": caption,
            }
        )
        self._write_json(history_path, history)

    def append_content_moment_memory(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "content_moment_memory.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def append_daily_calendar(self, package: DailyPackage) -> None:
        calendar_path = self.base_dir / "daily_calendar.json"
        calendar = self._read_json(calendar_path, [])
        calendar.append(
            {
                "date": package.date.isoformat(),
                "city": package.city,
                "day_type": package.day_type,
                "notes": package.summary,
            }
        )
        self._write_json(calendar_path, calendar)

    def ensure_city_exists(self, package: DailyPackage) -> None:
        cities_path = self.base_dir / "cities.json"
        cities = self._read_json(cities_path, [])
        known = {row.get("city") for row in cities}
        if package.city not in known:
            cities.append(
                {
                    "city": package.city,
                    "country": "",
                    "timezone": "",
                    "lat": "",
                    "lng": "",
                }
            )
            self._write_json(cities_path, cities)

    def save_run_log(self, status: str, message: str) -> None:
        run_log_path = self.base_dir / "run_log.json"
        logs = self._read_json(run_log_path, [])
        logs.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "status": status,
                "message": message,
            }
        )
        self._write_json(run_log_path, logs)

    def append_life_state(self, package: DailyPackage) -> None:
        life_state_path = self.base_dir / "life_state.json"
        rows = self._read_json(life_state_path, [])
        if not package.life_state:
            return
        rows.append(
            {
                "date": package.date.isoformat(),
                "current_city": package.life_state.current_city,
                "day_type": package.life_state.day_type,
                "season": package.life_state.season,
                "fatigue_level": package.life_state.fatigue_level,
                "mood_base": package.life_state.mood_base,
                "reason": package.life_state.day_type_reason,
                "continuity_note": package.life_state.continuity_note,
                "narrative_phase": getattr(package.life_state, "narrative_phase", "routine_stability"),
                "energy_state": getattr(package.life_state, "energy_state", "medium"),
                "rhythm_state": getattr(package.life_state, "rhythm_state", "stable"),
                "novelty_pressure": getattr(package.life_state, "novelty_pressure", 0),
                "recovery_need": getattr(package.life_state, "recovery_need", 0),
            }
        )
        self._write_json(life_state_path, rows)


class GoogleSheetsStateStore:
    def __init__(self, json_path: str, sheet_id: str) -> None:
        self.json_path = json_path
        self.sheet_id = sheet_id
        self.client = None
        self.sheet = None
        self.last_error = ""
        self._sheet_cache: Dict[str, List[Dict[str, Any]]] = {}

        try:
            if Credentials is None or gspread is None:
                raise RuntimeError("google dependencies are not installed")
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(self.json_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("GoogleSheetsStateStore disabled: %s", exc)
            self.client = None
            self.sheet = None

    def available(self) -> bool:
        return self.sheet is not None

    def _ws(self, title: str):
        return self.sheet.worksheet(title)

    def _is_quota_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return "429" in text or "quota" in text or "too many requests" in text

    def _with_retry(self, operation, *, operation_name: str):
        last_exc = None
        for attempt in range(5):
            try:
                return operation()
            except Exception as exc:  # pragma: no cover - external API behavior
                last_exc = exc
                if not self._is_quota_error(exc) or attempt == 4:
                    break
                delay = 2 ** attempt
                logger.warning(
                    "Google Sheets quota issue during %s (attempt %s/5). Retry in %ss.",
                    operation_name,
                    attempt + 1,
                    delay,
                )
                time.sleep(delay)
        if last_exc is not None:
            raise last_exc
        return None

    def _get_ws(self, title: str):
        return self._with_retry(lambda: self._ws(title), operation_name=f"open worksheet {title}")

    def _read_records(self, title: str) -> List[Dict[str, Any]]:
        if title in self._sheet_cache:
            return self._sheet_cache[title]
        ws = self._get_ws(title)
        rows = self._with_retry(lambda: ws.get_all_records() or [], operation_name=f"read records {title}")
        self._sheet_cache[title] = rows
        return rows

    def _invalidate_sheet_cache(self, title: str) -> None:
        self._sheet_cache.pop(title, None)

    def _safe_records(self, title: str) -> List[Dict[str, Any]]:
        try:
            return self._read_records(title)
        except Exception as exc:
            logger.error("Google Sheets read failed for '%s': %s", title, exc)
            return []

    def _append_dict_row(self, title: str, headers: List[str], row: Dict[str, Any]) -> None:
        if not self.available():
            return
        try:
            ws = self._get_ws(title)
            self._with_retry(
                lambda: ws.append_row([row.get(h, "") for h in headers]),
                operation_name=f"append row {title}",
            )
            self._invalidate_sheet_cache(title)
        except Exception as exc:
            logger.error("Google Sheets append failed for '%s': %s", title, exc)
            return

    def _replace_records(self, title: str, headers: List[str], rows: List[Dict[str, Any]]) -> None:
        if not self.available():
            return
        try:
            ws = self._get_ws(title)
            values = [headers] + [[row.get(h, "") for h in headers] for row in rows]
            self._with_retry(ws.clear, operation_name=f"clear sheet {title}")
            self._with_retry(lambda: ws.update(values), operation_name=f"update sheet {title}")
            self._invalidate_sheet_cache(title)
        except Exception as exc:
            logger.error("Google Sheets replace failed for '%s': %s", title, exc)
            return

    def _ensure_headers(self, title: str, required_headers: List[str]) -> None:
        if not self.available():
            return
        try:
            ws = self._get_ws(title)
            existing = self._with_retry(lambda: ws.row_values(1), operation_name=f"read header {title}")
            if not existing:
                self._with_retry(lambda: ws.append_row(required_headers), operation_name=f"write header {title}")
                self._invalidate_sheet_cache(title)
                return
            missing = [h for h in required_headers if h not in existing]
            if missing:
                self._with_retry(lambda: ws.update("1:1", [existing + missing]), operation_name=f"extend header {title}")
                self._invalidate_sheet_cache(title)
        except Exception as exc:
            logger.error("Google Sheets header sync failed for '%s': %s", title, exc)
            return


    def load_calendar(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("daily_calendar")

    def load_content_history(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("content_history")

    def load_content_moment_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("content_moment_memory")

    def load_publishing_plan(self, target_date: str | None = None) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        headers = [
            "publication_id", "date", "platform", "post_time", "content_type", "city", "day_type", "narrative_phase",
            "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus", "activity_type",
            "outfit_ids", "prompt_type", "prompt_text", "caption_text", "short_caption", "delivery_status", "notes",
        ]
        self._ensure_headers("publishing_plan", headers)
        rows = self._safe_records("publishing_plan")
        if target_date:
            return [r for r in rows if str(r.get("date")) == target_date]
        return rows

    def append_publishing_plan(self, row: Dict[str, Any]) -> None:
        headers = [
            "publication_id", "date", "platform", "post_time", "content_type", "city", "day_type", "narrative_phase",
            "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus", "activity_type",
            "outfit_ids", "prompt_type", "prompt_text", "caption_text", "short_caption", "delivery_status", "notes",
        ]
        self._ensure_headers("publishing_plan", headers)
        self._append_dict_row("publishing_plan", headers, row)

    def load_posting_rules(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        headers = [
            "rule_id", "platform", "content_type", "preferred_time", "enabled", "priority", "min_per_day", "max_per_day",
            "day_type_filter", "narrative_phase_filter", "city_filter", "weekday_filter", "notes",
        ]
        self._ensure_headers("posting_rules", headers)
        return self._safe_records("posting_rules")

    def append_delivery_log(self, row: Dict[str, Any]) -> None:
        headers = ["date", "delivery_type", "status", "message_id", "error", "details"]
        self._ensure_headers("delivery_log", headers)
        self._append_dict_row("delivery_log", headers, row)

    def load_character_profile(self) -> Dict[str, Any]:
        if not self.available():
            return {}

        rows = self._safe_records("character_profile")
        profile: Dict[str, Any] = {}

        for row in rows:
            field = row.get("field")
            value = row.get("value")
            if field:
                profile[str(field).strip()] = value

        return profile

    def load_cities(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("cities")

    def load_wardrobe(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("wardrobe")

    def load_wardrobe_items(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        headers = [
            "item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags",
            "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used",
            "wear_count", "times_in_content", "capsule_role", "style_vector", "priority_score", "notes",
        ]
        self._ensure_headers("wardrobe_items", headers)
        rows = self._safe_records("wardrobe_items")
        return rows or self.load_wardrobe()

    def save_wardrobe_items(self, rows: List[Dict[str, Any]]) -> None:
        headers = [
            "item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags",
            "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used",
            "wear_count", "times_in_content", "capsule_role", "style_vector", "priority_score", "notes",
        ]
        self._ensure_headers("wardrobe_items", headers)
        self._replace_records("wardrobe_items", headers, rows)

    def load_scene_library(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("scene_library")

    def load_outfit_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("outfit_memory")

    def append_outfit_memory(self, row: Dict[str, Any]) -> None:
        headers = ["date", "outfit_id", "item_ids", "city", "day_type", "weather", "occasion", "used_in_content", "repeat_score", "notes"]
        self._ensure_headers("outfit_memory", headers)
        self._append_dict_row("outfit_memory", headers, row)

    def append_wardrobe_action(self, row: Dict[str, Any]) -> None:
        headers = ["date", "action_type", "target_item_id", "reason", "status", "context_day_type", "context_season", "context_city", "notes"]
        self._append_dict_row("wardrobe_actions", headers, row)

    def append_shopping_candidate(self, row: Dict[str, Any]) -> None:
        headers = ["candidate_id", "category", "subcategory", "suggested_name", "reason", "priority", "season", "style_match", "gap_score", "status", "notes"]
        self._append_dict_row("shopping_candidates", headers, row)

    def load_scene_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("scene_memory")

    def save_scene_memory(self, rows: List[Dict[str, Any]]) -> None:
        headers = ["scene_id", "last_used", "usage_count", "last_city", "last_day_type", "repeat_cooldown", "status", "notes"]
        self._replace_records("scene_memory", headers, rows)

    def load_activity_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("activity_memory")

    def save_activity_memory(self, rows: List[Dict[str, Any]]) -> None:
        headers = ["activity_id", "activity_type", "last_used", "usage_count", "context_tags", "status", "notes"]
        self._replace_records("activity_memory", headers, rows)

    def load_location_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("location_memory")

    def save_location_memory(self, rows: List[Dict[str, Any]]) -> None:
        headers = ["location_id", "city", "location_type", "name", "usage_count", "visit_frequency", "last_used", "last_scene", "cooldown_days", "season_tags", "status", "notes"]
        self._replace_records("location_memory", headers, rows)


    def load_life_state(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("life_state")

    def load_narrative_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("narrative_memory")

    def load_scene_candidates(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("scene_candidates")

    def append_scene_candidate(self, row: Dict[str, Any]) -> None:
        headers = [
            "candidate_id", "day_type", "time_block", "location", "description", "mood", "activity_hint",
            "city", "season", "source_context", "generated_by_ai", "status", "score", "notes",
        ]
        self._ensure_headers("scene_candidates", headers)
        self._append_dict_row("scene_candidates", headers, row)

    def load_activity_candidates(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("activity_candidates")

    def append_activity_candidate(self, row: Dict[str, Any]) -> None:
        headers = [
            "candidate_id", "activity_code", "activity_label", "day_type", "time_block", "city", "season",
            "mood_fit", "fatigue_min", "fatigue_max", "weather_fit", "source_context", "generated_by_ai",
            "status", "score", "notes",
        ]
        self._ensure_headers("activity_candidates", headers)
        self._append_dict_row("activity_candidates", headers, row)

    def append_narrative_memory(self, row: Dict[str, Any]) -> None:
        headers = ["date", "narrative_phase", "energy_state", "rhythm_state", "novelty_pressure", "recovery_need", "reason"]
        self._ensure_headers("narrative_memory", headers)
        self._append_dict_row("narrative_memory", headers, row)

    def load_style_rules(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("style_rules")

    def load_world_candidates(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("world_candidates")

    def append_world_candidate(self, row: Dict[str, Any]) -> None:
        headers = ["candidate_id", "candidate_type", "name", "city", "description", "source_reason", "priority", "status"]
        self._ensure_headers("world_candidates", headers)
        self._append_dict_row("world_candidates", headers, row)

    def load_story_arcs(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("story_arcs")

    def append_story_arc(self, row: Dict[str, Any]) -> None:
        headers = ["arc_id", "arc_type", "title", "status", "start_date", "progress", "description"]
        self._ensure_headers("story_arcs", headers)
        self._append_dict_row("story_arcs", headers, row)

    def save_story_arcs(self, rows: List[Dict[str, Any]]) -> None:
        headers = ["arc_id", "arc_type", "title", "status", "start_date", "progress", "description"]
        self._ensure_headers("story_arcs", headers)
        self._replace_records("story_arcs", headers, rows)

    def load_activity_evolution(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("activity_evolution")

    def append_activity_evolution(self, row: Dict[str, Any]) -> None:
        headers = ["activity_id", "origin_activity", "generated_variant", "reason", "status"]
        self._ensure_headers("activity_evolution", headers)
        self._append_dict_row("activity_evolution", headers, row)

    def load_prompt_templates(self) -> Dict[str, str]:
        if not self.available():
            return {}

        rows = self._safe_records("prompt_templates")
        templates: Dict[str, str] = {}

        for row in rows:
            key = row.get("key")
            template = row.get("template")
            if key:
                templates[str(key).strip()] = template or ""

        return templates

    def load_prompt_blocks(self) -> Dict[str, str]:
        if not self.available():
            return {}

        try:
            rows = self._safe_records("prompt_blocks")
        except Exception:
            return {}

        blocks: Dict[str, str] = {}
        for row in rows:
            key = row.get("key")
            value = row.get("content")
            if key:
                blocks[str(key).strip()] = str(value or "")
        return blocks

    def load_route_pool(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        try:
            return self._safe_records("route_pool")
        except Exception:
            return []

    def save_content_package(self, package: DailyPackage) -> str:
        output_path = f"data/outputs/{package.date.isoformat()}_package.json"
        os.makedirs("data/outputs", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(package.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        return output_path

    def append_history(self, package: DailyPackage) -> None:
        if not self.available():
            return

        caption = getattr(package.content, "post_caption", "") if hasattr(package, "content") else ""
        last_scene = package.scenes[-1] if package.scenes else None
        headers = [
            "date", "city", "day_type", "outfit_ids", "scenes", "post_caption",
            "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus",
        ]
        self._ensure_headers("content_history", headers)
        self._append_dict_row(
            "content_history",
            headers,
            {
                "date": package.date.isoformat(),
                "city": package.city,
                "day_type": package.day_type,
                "outfit_ids": ", ".join(package.outfit.item_ids),
                "scenes": " | ".join(s.description for s in package.scenes),
                "post_caption": caption,
                "scene_moment": getattr(last_scene, "scene_moment", "") if last_scene else "",
                "scene_source": getattr(last_scene, "scene_source", "") if last_scene else "",
                "scene_moment_type": getattr(last_scene, "scene_moment_type", "") if last_scene else "",
                "moment_signature": getattr(last_scene, "moment_signature", "") if last_scene else "",
                "visual_focus": getattr(last_scene, "visual_focus", "") if last_scene else "",
            },
        )

    def append_content_moment_memory(self, row: Dict[str, Any]) -> None:
        headers = [
            "date", "city", "day_type", "scene_moment", "scene_moment_type", "moment_signature", "visual_focus", "scene_source",
        ]
        self._ensure_headers("content_moment_memory", headers)
        self._append_dict_row("content_moment_memory", headers, row)

    def append_daily_calendar(self, package: DailyPackage) -> None:
        if not self.available():
            return

        self._with_retry(
            lambda: self._get_ws("daily_calendar").append_row(
                [
                    package.date.isoformat(),
                    package.city,
                    package.day_type,
                    package.summary,
                ]
            ),
            operation_name="append row daily_calendar",
        )
        self._invalidate_sheet_cache("daily_calendar")

    def ensure_city_exists(self, package: DailyPackage) -> None:
        if not self.available():
            return

        ws = self._get_ws("cities")
        records = self._safe_records("cities")
        known = {row.get("city") for row in records}

        if package.city not in known:
            self._with_retry(lambda: ws.append_row([package.city, "", "", "", ""]), operation_name="append row cities")
            self._invalidate_sheet_cache("cities")

    def save_run_log(self, status: str, message: str) -> None:
        if not self.available():
            return

        self._with_retry(
            lambda: self._get_ws("run_log").append_row(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    status,
                    message,
                ]
            ),
            operation_name="append row run_log",
        )
        self._invalidate_sheet_cache("run_log")

    def append_life_state(self, package: DailyPackage) -> None:
        if not self.available() or not package.life_state:
            return
        try:
            self._with_retry(lambda: self._get_ws("life_state").append_row(
                [
                    package.date.isoformat(),
                    package.life_state.current_city,
                    package.life_state.day_type,
                    package.life_state.season,
                    package.life_state.fatigue_level,
                    package.life_state.mood_base,
                    package.life_state.day_type_reason,
                    package.life_state.continuity_note,
                    getattr(package.life_state, "narrative_phase", "routine_stability"),
                    getattr(package.life_state, "energy_state", "medium"),
                    getattr(package.life_state, "rhythm_state", "stable"),
                    getattr(package.life_state, "novelty_pressure", 0),
                    getattr(package.life_state, "recovery_need", 0),
                ]
            ), operation_name="append row life_state")
            self._invalidate_sheet_cache("life_state")
        except Exception:
            return


def build_state_store(settings):
    backend = (settings.state_backend or "auto").lower()

    if backend == "local":
        return LocalStateStore()

    if backend in ("google", "gsheets", "google_sheets", "auto"):
        if settings.google_service_account_json_path and settings.google_sheet_id:
            gs = GoogleSheetsStateStore(
                json_path=settings.google_service_account_json_path,
                sheet_id=settings.google_sheet_id,
            )
            if gs.available():
                return gs
            if backend in ("google", "gsheets", "google_sheets"):
                raise RuntimeError(f"Google Sheets backend unavailable: {gs.last_error or 'unknown error'}")
            logger.error("Google Sheets backend unavailable in auto mode: %s", gs.last_error or "unknown error")
        elif backend in ("google", "gsheets", "google_sheets"):
            raise RuntimeError("Google Sheets backend requested but credentials are missing")

    return LocalStateStore()
