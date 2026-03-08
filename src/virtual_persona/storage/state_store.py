from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

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
        return self._read_json(Path("data/samples/daily_calendar.sample.json"), [])

    def load_content_history(self) -> List[Dict[str, Any]]:
        return self._read_json(Path("data/state/content_history.json"), self._read_json(Path("data/samples/content_history.sample.json"), []))

    def save_content_package(self, package: DailyPackage) -> Path:
        output_path = Path("data/outputs") / f"{package.date.isoformat()}_package.json"
        self._write_json(output_path, package.to_dict())
        return output_path

    def append_history(self, package: DailyPackage) -> None:
        history_path = self.base_dir / "content_history.json"
        history = self._read_json(history_path, [])
        history.append(
            {
                "date": package.date.isoformat(),
                "city": package.city,
                "day_type": package.day_type,
                "scenes": [s.description for s in package.scenes],
                "outfit_ids": package.outfit.item_ids,
            }
        )
        self._write_json(history_path, history)

    def save_run_log(self, status: str, message: str) -> None:
        run_log_path = self.base_dir / "run_log.json"
        logs = self._read_json(run_log_path, [])
        logs.append({"date": date.today().isoformat(), "status": status, "message": message})
        self._write_json(run_log_path, logs)


class GoogleSheetsStateStore:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.enabled = False
        try:
            import gspread  # noqa: F401

            self.enabled = True
        except Exception:
            logger.warning("gspread not installed; GoogleSheetsStateStore disabled.")

    def available(self) -> bool:
        return self.enabled
