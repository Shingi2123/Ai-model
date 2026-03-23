import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import gspread
from requests import Response

from virtual_persona.delivery.publishing_plan_normalizer import PUBLISHING_PLAN_HEADERS


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_google_sheet.py"
SPEC = spec_from_file_location("bootstrap_google_sheet", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
BOOTSTRAP = module_from_spec(SPEC)
SPEC.loader.exec_module(BOOTSTRAP)

BEHAVIOR_MEMORY_HEADERS = BOOTSTRAP.BEHAVIOR_MEMORY_HEADERS
CONTENT_HISTORY_HEADERS = BOOTSTRAP.CONTENT_HISTORY_HEADERS
CONTENT_MOMENT_MEMORY_HEADERS = BOOTSTRAP.CONTENT_MOMENT_MEMORY_HEADERS
DAILY_CALENDAR_HEADERS = BOOTSTRAP.DAILY_CALENDAR_HEADERS
HABIT_MEMORY_HEADERS = BOOTSTRAP.HABIT_MEMORY_HEADERS
LIFE_STATE_HEADERS = BOOTSTRAP.LIFE_STATE_HEADERS
OBJECT_USAGE_HEADERS = BOOTSTRAP.OBJECT_USAGE_HEADERS
OUTFIT_CONTROL_HEADERS = BOOTSTRAP.OUTFIT_CONTROL_HEADERS
PLACE_MEMORY_HEADERS = BOOTSTRAP.PLACE_MEMORY_HEADERS
RUN_LOG_HEADERS = BOOTSTRAP.RUN_LOG_HEADERS
SCENE_CANDIDATE_HEADERS = BOOTSTRAP.SCENE_CANDIDATE_HEADERS
SCENE_LIBRARY_HEADERS = BOOTSTRAP.SCENE_LIBRARY_HEADERS
SHEETS = BOOTSTRAP.SHEETS


class FakeWorksheet:
    def __init__(self, title: str, headers: list[str] | None = None) -> None:
        self.title = title
        self.headers = list(headers or [])
        self.update_calls = 0

    def update(self, *, values, range_name):
        assert range_name == "1:1"
        self.update_calls += 1
        self.headers = list(values[0])
        return {"updatedRange": f"{self.title}!1:1"}


class FakeSpreadsheet:
    def __init__(self, initial_headers: dict[str, list[str]] | None = None) -> None:
        self.sheet_map = {
            title: FakeWorksheet(title, headers)
            for title, headers in (initial_headers or {}).items()
        }
        self.worksheets_calls = 0
        self.values_batch_get_calls = 0
        self.add_worksheet_calls = 0
        self.worksheet_calls = 0

    def worksheets(self):
        self.worksheets_calls += 1
        return list(self.sheet_map.values())

    def values_batch_get(self, ranges):
        self.values_batch_get_calls += 1
        value_ranges = []
        for range_name in ranges:
            title = range_name.split("!")[0].strip("'").replace("''", "'")
            worksheet = self.sheet_map[title]
            values = [worksheet.headers] if worksheet.headers else []
            value_ranges.append({"range": range_name, "values": values})
        return {"valueRanges": value_ranges}

    def add_worksheet(self, *, title, rows, cols):
        del rows, cols
        self.add_worksheet_calls += 1
        worksheet = FakeWorksheet(title)
        self.sheet_map[title] = worksheet
        return worksheet

    def worksheet(self, title):
        self.worksheet_calls += 1
        raise AssertionError(f"worksheet({title}) should not be used when cache is active")


def _api_error(code: int, message: str) -> gspread.exceptions.APIError:
    response = Response()
    response.status_code = code
    response._content = json.dumps(
        {"error": {"code": code, "message": message, "status": "RESOURCE_EXHAUSTED"}}
    ).encode("utf-8")
    return gspread.exceptions.APIError(response)


def test_bootstrap_google_sheet_uses_runtime_publishing_plan_headers():
    assert SHEETS["publishing_plan"] == list(PUBLISHING_PLAN_HEADERS)


def test_bootstrap_google_sheet_behavior_memory_tabs_are_present_and_current():
    assert SHEETS["behavior_memory"] == BEHAVIOR_MEMORY_HEADERS
    assert SHEETS["habit_memory"] == HABIT_MEMORY_HEADERS
    assert SHEETS["place_memory"] == PLACE_MEMORY_HEADERS
    assert SHEETS["object_usage"] == OBJECT_USAGE_HEADERS


def test_bootstrap_google_sheet_core_runtime_tabs_match_current_headers():
    assert SHEETS["content_history"] == CONTENT_HISTORY_HEADERS
    assert SHEETS["content_moment_memory"] == CONTENT_MOMENT_MEMORY_HEADERS
    assert SHEETS["life_state"] == LIFE_STATE_HEADERS
    assert SHEETS["run_log"] == RUN_LOG_HEADERS


def test_bootstrap_google_sheet_outfit_control_tabs_are_present_and_current():
    assert SHEETS["scene_library"] == SCENE_LIBRARY_HEADERS
    assert SHEETS["scene_candidates"] == SCENE_CANDIDATE_HEADERS
    assert SHEETS["daily_calendar"] == DAILY_CALENDAR_HEADERS
    assert SHEETS["outfit_controls"] == OUTFIT_CONTROL_HEADERS


def test_bootstrap_google_sheet_content_history_tracks_generated_outfit_controls():
    for header in ["outfit_summary", "style_intensity", "outfit_style", "outfit_override_used"]:
        assert header in CONTENT_HISTORY_HEADERS


def test_with_gspread_retry_retries_429_with_exponential_backoff():
    sleeps = []
    logs = []
    attempts = {"count": 0}

    def flaky_operation():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise _api_error(429, "Quota exceeded for quota metric 'Read requests'")
        return "ok"

    result = BOOTSTRAP.with_gspread_retry(
        flaky_operation,
        "batch read worksheet headers",
        sleep_fn=sleeps.append,
        print_fn=logs.append,
    )

    assert result == "ok"
    assert sleeps == [5, 10]
    assert any("Retry after 429" in line for line in logs)


def test_bootstrap_spreadsheet_is_idempotent_and_avoids_worksheet_reads():
    initial_headers = {
        "character_profile": ["field"],
        "content_history": list(CONTENT_HISTORY_HEADERS),
    }
    spreadsheet = FakeSpreadsheet(initial_headers)
    sleeps = []
    logs = []

    first = BOOTSTRAP.bootstrap_spreadsheet(
        spreadsheet,
        sleep_fn=sleeps.append,
        print_fn=logs.append,
    )
    update_count_after_first = sum(ws.update_calls for ws in spreadsheet.sheet_map.values())

    second = BOOTSTRAP.bootstrap_spreadsheet(
        spreadsheet,
        sleep_fn=sleeps.append,
        print_fn=logs.append,
    )
    update_count_after_second = sum(ws.update_calls for ws in spreadsheet.sheet_map.values())

    assert spreadsheet.worksheet_calls == 0
    assert spreadsheet.worksheets_calls == 2
    assert spreadsheet.values_batch_get_calls == 2
    assert first["created"]
    assert "character_profile" in first["updated"]
    assert second["created"] == []
    assert second["initialized"] == []
    assert second["updated"] == []
    assert len(second["skipped"]) == len(SHEETS)
    assert update_count_after_second == update_count_after_first
    assert spreadsheet.sheet_map["character_profile"].headers == SHEETS["character_profile"]
    assert any("Exists: character_profile" in line for line in logs)
    assert any("Bootstrap completed successfully." in line for line in logs)
