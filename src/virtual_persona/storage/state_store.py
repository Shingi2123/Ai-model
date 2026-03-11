from __future__ import annotations

import json
import logging
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

    def append_outfit_memory(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "outfit_memory.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def append_wardrobe_action(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "wardrobe_actions.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def append_shopping_candidate(self, row: Dict[str, Any]) -> None:
        path = self.base_dir / "shopping_candidates.json"
        rows = self._read_json(path, [])
        rows.append(row)
        self._write_json(path, rows)

    def save_scene_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "scene_memory.json", rows)

    def save_activity_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "activity_memory.json", rows)

    def save_location_memory(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "location_memory.json", rows)

    def save_wardrobe_items(self, rows: List[Dict[str, Any]]) -> None:
        self._write_json(self.base_dir / "wardrobe_items.json", rows)

    def load_scene_library(self) -> List[Dict[str, Any]]:
        return []

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

        history.append(
            {
                "date": package.date.isoformat(),
                "city": package.city,
                "day_type": package.day_type,
                "scenes": " | ".join(s.description for s in package.scenes),
                "outfit_ids": ", ".join(package.outfit.item_ids),
                "post_caption": caption,
            }
        )
        self._write_json(history_path, history)

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
            }
        )
        self._write_json(life_state_path, rows)


class GoogleSheetsStateStore:
    def __init__(self, json_path: str, sheet_id: str) -> None:
        self.json_path = json_path
        self.sheet_id = sheet_id
        self.client = None
        self.sheet = None

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
            logger.warning("GoogleSheetsStateStore disabled: %s", exc)
            self.client = None
            self.sheet = None

    def available(self) -> bool:
        return self.sheet is not None

    def _ws(self, title: str):
        return self.sheet.worksheet(title)

    def _safe_records(self, title: str) -> List[Dict[str, Any]]:
        try:
            return self._ws(title).get_all_records() or []
        except Exception:
            return []

    def _append_dict_row(self, title: str, headers: List[str], row: Dict[str, Any]) -> None:
        if not self.available():
            return
        try:
            self._ws(title).append_row([row.get(h, "") for h in headers])
        except Exception:
            return

    def _replace_records(self, title: str, headers: List[str], rows: List[Dict[str, Any]]) -> None:
        if not self.available():
            return
        try:
            ws = self._ws(title)
            values = [headers] + [[row.get(h, "") for h in headers] for row in rows]
            ws.clear()
            ws.update(values)
        except Exception:
            return

    def load_calendar(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("daily_calendar").get_all_records() or []

    def load_content_history(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("content_history").get_all_records() or []

    def load_character_profile(self) -> Dict[str, Any]:
        if not self.available():
            return {}

        rows = self._ws("character_profile").get_all_records() or []
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
        return self._ws("cities").get_all_records() or []

    def load_wardrobe(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("wardrobe").get_all_records() or []

    def load_wardrobe_items(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        rows = self._safe_records("wardrobe_items")
        return rows or self.load_wardrobe()

    def save_wardrobe_items(self, rows: List[Dict[str, Any]]) -> None:
        headers = [
            "item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags",
            "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used",
            "wear_count", "times_in_content", "notes",
        ]
        self._replace_records("wardrobe_items", headers, rows)

    def load_scene_library(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("scene_library").get_all_records() or []

    def load_outfit_memory(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._safe_records("outfit_memory")

    def append_outfit_memory(self, row: Dict[str, Any]) -> None:
        headers = ["date", "outfit_id", "item_ids", "city", "day_type", "weather", "occasion", "used_in_content", "repeat_score", "notes"]
        self._append_dict_row("outfit_memory", headers, row)

    def append_wardrobe_action(self, row: Dict[str, Any]) -> None:
        headers = ["date", "action_type", "target_item_id", "reason", "status", "notes"]
        self._append_dict_row("wardrobe_actions", headers, row)

    def append_shopping_candidate(self, row: Dict[str, Any]) -> None:
        headers = ["candidate_id", "category", "subcategory", "suggested_name", "reason", "priority", "season", "style_match", "status", "notes"]
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
        headers = ["location_id", "city", "location_type", "name", "usage_count", "last_used", "season_tags", "status", "notes"]
        self._replace_records("location_memory", headers, rows)

    def load_prompt_templates(self) -> Dict[str, str]:
        if not self.available():
            return {}

        rows = self._ws("prompt_templates").get_all_records() or []
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
            rows = self._ws("prompt_blocks").get_all_records() or []
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
            return self._ws("route_pool").get_all_records() or []
        except Exception:
            return []

    def save_content_package(self, package: DailyPackage) -> Path:
        output_path = Path("data/outputs") / f"{package.date.isoformat()}_package.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(package.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        return output_path

    def append_history(self, package: DailyPackage) -> None:
        if not self.available():
            return

        caption = getattr(package.content, "post_caption", "") if hasattr(package, "content") else ""

        self._ws("content_history").append_row(
            [
                package.date.isoformat(),
                package.city,
                package.day_type,
                ", ".join(package.outfit.item_ids),
                " | ".join(s.description for s in package.scenes),
                caption,
            ]
        )

    def append_daily_calendar(self, package: DailyPackage) -> None:
        if not self.available():
            return

        self._ws("daily_calendar").append_row(
            [
                package.date.isoformat(),
                package.city,
                package.day_type,
                package.summary,
            ]
        )

    def ensure_city_exists(self, package: DailyPackage) -> None:
        if not self.available():
            return

        ws = self._ws("cities")
        records = ws.get_all_records()
        known = {row.get("city") for row in records}

        if package.city not in known:
            ws.append_row([package.city, "", "", "", ""])

    def save_run_log(self, status: str, message: str) -> None:
        if not self.available():
            return

        self._ws("run_log").append_row(
            [
                datetime.now().isoformat(timespec="seconds"),
                status,
                message,
            ]
        )

    def append_life_state(self, package: DailyPackage) -> None:
        if not self.available() or not package.life_state:
            return
        try:
            self._ws("life_state").append_row(
                [
                    package.date.isoformat(),
                    package.life_state.current_city,
                    package.life_state.day_type,
                    package.life_state.season,
                    package.life_state.fatigue_level,
                    package.life_state.mood_base,
                    package.life_state.day_type_reason,
                    package.life_state.continuity_note,
                ]
            )
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

    return LocalStateStore()
