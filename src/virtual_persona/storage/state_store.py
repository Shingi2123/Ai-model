from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from google.oauth2.service_account import Credentials
import gspread

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


class GoogleSheetsStateStore:
    def __init__(self, json_path: str, sheet_id: str) -> None:
        self.json_path = json_path
        self.sheet_id = sheet_id
        self.client = None
        self.sheet = None

        try:
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

    def load_calendar(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("daily_calendar").get_all_records() or []

    def load_content_history(self) -> List[Dict[str, Any]]:
        if not self.available():
            return []
        return self._ws("content_history").get_all_records() or []

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