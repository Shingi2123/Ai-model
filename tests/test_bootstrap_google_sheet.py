from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

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
