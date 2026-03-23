from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

"""Initialize Google Sheets tabs for the project.
Requires optional deps: gspread google-auth
"""

import os
import time
from typing import Any, Callable, Dict, Iterable, List, Tuple

import gspread
from google.oauth2.service_account import Credentials
from virtual_persona.delivery.publishing_plan_normalizer import PUBLISHING_PLAN_HEADERS


CHARACTER_PROFILE_V3_FIELDS = [
    "identity_mode",
    "identity_pack_status",

    "display_name",
    "age",
    "device_profile",
    "recurring_phone_device",
    "face_signature",
    "face_shape",
    "nose_bridge",
    "cheekbone_softness",
    "lip_fullness",
    "brow_style",
    "favorite_locations",
    "recurring_spaces",
    "favorite_locations_memory",
    "primary_device_profile",
    "camera_behavior_memory",
    "social_behavior_profile",
    "default_style_intensity",
    "default_outfit_style",
    "outfit_realism_notes",
    "identity_manifest_version",
    "face_similarity_threshold",
]

CONTENT_HISTORY_HEADERS = [
    "date",
    "city",
    "day_type",
    "outfit_ids",
    "outfit_summary",
    "style_intensity",
    "outfit_style",
    "outfit_override_used",
    "scenes",
    "post_caption",
    "scene_moment",
    "scene_source",
    "scene_moment_type",
    "moment_signature",
    "visual_focus",
    "reference_pack_type",
    "prompt_mode",
    "face_similarity",
    "scene_logic_score",
    "artifact_flags",
]

OUTFIT_MEMORY_HEADERS = [
    "date",
    "outfit_id",
    "item_ids",
    "city",
    "day_type",
    "weather",
    "occasion",
    "used_in_content",
    "repeat_score",
    "outfit_summary",
    "top",
    "bottom",
    "outerwear",
    "shoes",
    "accessories",
    "fit",
    "fabric",
    "condition",
    "styling",
    "place",
    "activity",
    "time_of_day",
    "social_presence",
    "energy",
    "habit",
    "style_intensity",
    "outfit_style",
    "enhance_attractiveness",
    "outfit_override_used",
    "style_profile",
    "notes",
]

SCENE_LIBRARY_HEADERS = [
    "scene_id",
    "day_type",
    "time_block",
    "location",
    "description",
    "mood",
    "activity_hint",
    "social_presence",
    "style_intensity",
    "outfit_style",
    "outfit_override",
    "enhance_attractiveness",
    "weather_hint",
    "tags",
]

SCENE_CANDIDATE_HEADERS = [
    "candidate_id",
    "day_type",
    "time_block",
    "location",
    "description",
    "mood",
    "activity_hint",
    "social_presence",
    "style_intensity",
    "outfit_style",
    "outfit_override",
    "enhance_attractiveness",
    "city",
    "season",
    "weather_hint",
    "source_context",
    "generated_by_ai",
    "status",
    "score",
    "notes",
]

DAILY_CALENDAR_HEADERS = [
    "date",
    "city",
    "day_type",
    "outfit_override",
    "style_intensity",
    "outfit_style",
    "enhance_attractiveness",
    "notes",
]

OUTFIT_CONTROL_HEADERS = [
    "control_id",
    "date",
    "city",
    "day_type",
    "time_of_day",
    "place",
    "activity",
    "social_presence",
    "style_intensity",
    "outfit_style",
    "outfit_override",
    "enhance_attractiveness",
    "enabled",
    "priority",
    "notes",
]

CONTENT_MOMENT_MEMORY_HEADERS = [
    "date",
    "city",
    "day_type",
    "scene_moment",
    "scene_moment_type",
    "moment_signature",
    "visual_focus",
    "scene_source",
    "shot_archetype",
    "platform_intent",
    "camera_behavior_used",
    "framing_style_used",
    "favorite_location_used",
    "social_behavior_mode",
    "publish_score",
    "publish_decision",
    "decision_reason",
]

BEHAVIOR_MEMORY_HEADERS = [
    "date",
    "city",
    "day_type",
    "behavior_state",
    "energy_level",
    "social_mode",
    "emotional_arc",
    "habit",
    "place_anchor",
    "objects",
    "self_presentation",
    "source",
    "day_behavior_summary",
    "selected_habit",
    "familiar_place_anchor",
    "recurring_objects_in_scene",
    "self_presentation_mode",
    "social_presence_mode",
]

HABIT_MEMORY_HEADERS = ["date", "city", "day_type", "habit", "emotional_arc", "place_anchor"]
PLACE_MEMORY_HEADERS = ["date", "city", "day_type", "place_anchor", "emotional_arc", "habit"]
OBJECT_USAGE_HEADERS = ["date", "city", "day_type", "place_anchor", "objects", "habit"]

LIFE_STATE_HEADERS = [
    "date",
    "current_city",
    "day_type",
    "season",
    "fatigue_level",
    "mood_base",
    "reason",
    "continuity_note",
    "narrative_phase",
    "energy_state",
    "rhythm_state",
    "novelty_pressure",
    "recovery_need",
]

RUN_LOG_HEADERS = [
    "timestamp",
    "status",
    "message",
    "device_profile",
    "camera_behavior_used",
    "framing_style_used",
    "favorite_location_used",
    "social_behavior_mode",
    "anti_synthetic_cleaner_applied",
    "face_similarity",
    "scene_logic_score",
    "hand_integrity_flag",
    "body_consistency_flag",
    "artifact_flags",
    "prompt_mode",
    "reference_pack_used",
]

SHEETS = {
    "character_profile": ["field", "value"],
    "wardrobe": ["id", "category", "name", "styles", "colors", "season", "temp_min_c", "temp_max_c", "weather_tags", "cooldown_days", "last_used"],
    "wardrobe_items": ["item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags", "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used", "wear_count", "times_in_content", "capsule_role", "style_vector", "priority_score", "notes"],
    "outfit_memory": OUTFIT_MEMORY_HEADERS,
    "wardrobe_actions": ["date", "action_type", "target_item_id", "reason", "status", "context_day_type", "context_season", "context_city", "notes"],
    "shopping_candidates": ["candidate_id", "category", "subcategory", "suggested_name", "reason", "priority", "season", "style_match", "gap_score", "status", "notes"],
    "cities": ["city", "country", "timezone", "lat", "lng"],
    "scene_library": SCENE_LIBRARY_HEADERS,
    "scene_memory": ["scene_id", "last_used", "usage_count", "last_city", "last_day_type", "repeat_cooldown", "status", "notes"],
    "scene_candidates": SCENE_CANDIDATE_HEADERS,
    "activity_candidates": ["candidate_id", "activity_code", "activity_label", "day_type", "time_block", "city", "season", "mood_fit", "fatigue_min", "fatigue_max", "weather_fit", "source_context", "generated_by_ai", "status", "score", "notes"],
    "style_rules": ["rule_id", "rule_type", "target", "rule_value", "priority", "status", "notes"],
    "activity_memory": ["activity_id", "activity_type", "last_used", "usage_count", "context_tags", "status", "notes"],
    "location_memory": ["location_id", "city", "location_type", "name", "usage_count", "visit_frequency", "last_used", "last_scene", "cooldown_days", "season_tags", "status", "notes"],
    "world_candidates": ["candidate_id", "candidate_type", "name", "city", "description", "source_reason", "priority", "status"],
    "story_arcs": ["arc_id", "arc_type", "title", "status", "start_date", "progress", "description"],
    "activity_evolution": ["activity_id", "origin_activity", "generated_variant", "reason", "status"],
    "daily_calendar": DAILY_CALENDAR_HEADERS,
    "outfit_controls": OUTFIT_CONTROL_HEADERS,
    "content_history": CONTENT_HISTORY_HEADERS,
    "content_moment_memory": CONTENT_MOMENT_MEMORY_HEADERS,
    "publishing_plan": list(PUBLISHING_PLAN_HEADERS),
    "behavior_memory": BEHAVIOR_MEMORY_HEADERS,
    "habit_memory": HABIT_MEMORY_HEADERS,
    "place_memory": PLACE_MEMORY_HEADERS,
    "object_usage": OBJECT_USAGE_HEADERS,
    "posting_rules": ["rule_id", "platform", "content_type", "preferred_time", "enabled", "priority", "min_per_day", "max_per_day", "day_type_filter", "narrative_phase_filter", "city_filter", "weekday_filter", "notes"],
    "delivery_log": ["date", "delivery_type", "status", "message_id", "error", "details"],
    "continuity_flags": ["date", "level", "code", "message"],
    "prompt_templates": ["key", "template"],
    "prompt_blocks": ["key", "content", "priority", "enabled"],
    "route_pool": ["route_id", "origin_city", "destination_city", "flight_type", "weight", "active"],
    "life_state": LIFE_STATE_HEADERS,
    "narrative_memory": ["date", "narrative_phase", "energy_state", "rhythm_state", "novelty_pressure", "recovery_need", "reason"],
    "run_log": RUN_LOG_HEADERS,
    "character_identity": ["field", "value", "source", "updated_at"],
    "identity_references": ["reference_type", "path", "status", "notes"],
    "asset_quality": ["asset_id", "date", "face_similarity", "scene_logic_score", "hand_integrity_flag", "body_consistency_flag", "artifact_flags", "prompt_mode", "reference_pack_used", "rank"],
}


RETRY_BACKOFF_SECONDS: Tuple[int, ...] = (5, 10, 20, 40, 60)
LOOP_THROTTLE_SECONDS = 0.5
STAGE_THROTTLE_SECONDS = 0.75


def _is_quota_error(exc: Exception) -> bool:
    if not isinstance(exc, gspread.exceptions.APIError):
        return False
    if getattr(exc, "code", None) == 429:
        return True
    message = str(exc).lower()
    return "quota" in message or "read requests per minute per user" in message or "[429]" in message


def with_gspread_retry(
    operation: Callable[[], Any],
    operation_name: str,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    print_fn: Callable[[str], None] = print,
    max_attempts: int = 5,
    backoff_seconds: Iterable[int] = RETRY_BACKOFF_SECONDS,
) -> Any:
    waits = list(backoff_seconds) or list(RETRY_BACKOFF_SECONDS)
    last_quota_error: gspread.exceptions.APIError | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except gspread.exceptions.APIError as exc:
            if not _is_quota_error(exc):
                raise
            last_quota_error = exc
            if attempt >= max_attempts:
                break
            wait_seconds = waits[min(attempt - 1, len(waits) - 1)]
            print_fn(
                f"Retry after 429: {operation_name} "
                f"(attempt {attempt}/{max_attempts}, waiting {wait_seconds}s)"
            )
            sleep_fn(wait_seconds)

    raise RuntimeError(
        f"Google Sheets API quota limit persisted during '{operation_name}' after {max_attempts} attempts. "
        "Bootstrap stopped because of Google Sheets API limits, not because of project logic."
    ) from last_quota_error


def _throttle(sleep_fn: Callable[[float], None], seconds: float) -> None:
    if seconds > 0:
        sleep_fn(seconds)


def _quote_sheet_title(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _fetch_header_cache(
    spreadsheet: Any,
    worksheets_by_title: Dict[str, Any],
    *,
    sleep_fn: Callable[[float], None],
    print_fn: Callable[[str], None],
) -> Dict[str, List[str]]:
    if not worksheets_by_title:
        return {}

    titles = list(worksheets_by_title.keys())
    ranges = [f"{_quote_sheet_title(title)}!1:1" for title in titles]
    response = with_gspread_retry(
        lambda: spreadsheet.values_batch_get(ranges),
        "batch read worksheet headers",
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )

    value_ranges = response.get("valueRanges", []) if isinstance(response, dict) else []
    header_cache: Dict[str, List[str]] = {}
    for index, title in enumerate(titles):
        values = []
        if index < len(value_ranges):
            values = value_ranges[index].get("values", []) or []
        header_cache[title] = list(values[0]) if values else []
    return header_cache


def _load_worksheet_cache(
    spreadsheet: Any,
    *,
    sleep_fn: Callable[[float], None],
    print_fn: Callable[[str], None],
) -> tuple[Dict[str, Any], Dict[str, List[str]]]:
    worksheets = with_gspread_retry(
        lambda: spreadsheet.worksheets(),
        "load worksheet metadata",
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )
    worksheets_by_title = {ws.title: ws for ws in worksheets}
    header_cache = _fetch_header_cache(
        spreadsheet,
        worksheets_by_title,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )
    return worksheets_by_title, header_cache


def _create_missing_sheets(
    spreadsheet: Any,
    worksheets_by_title: Dict[str, Any],
    header_cache: Dict[str, List[str]],
    *,
    sleep_fn: Callable[[float], None],
    print_fn: Callable[[str], None],
) -> List[str]:
    created: List[str] = []
    for title, headers in SHEETS.items():
        if title in worksheets_by_title:
            print_fn(f"Exists: {title}")
            continue
        worksheet = with_gspread_retry(
            lambda title=title, headers=headers: spreadsheet.add_worksheet(
                title=title,
                rows=1000,
                cols=max(20, len(headers) + 3),
            ),
            f"create worksheet '{title}'",
            sleep_fn=sleep_fn,
            print_fn=print_fn,
        )
        worksheets_by_title[title] = worksheet
        with_gspread_retry(
            lambda worksheet=worksheet, headers=headers: worksheet.update(
                values=[headers],
                range_name="1:1",
            ),
            f"initialize headers for '{title}'",
            sleep_fn=sleep_fn,
            print_fn=print_fn,
        )
        header_cache[title] = list(headers)
        created.append(title)
        print_fn(f"Created: {title}")
        _throttle(sleep_fn, LOOP_THROTTLE_SECONDS)
    return created


def _update_headers(
    worksheets_by_title: Dict[str, Any],
    header_cache: Dict[str, List[str]],
    *,
    sleep_fn: Callable[[float], None],
    print_fn: Callable[[str], None],
) -> tuple[List[str], List[str], List[str]]:
    initialized: List[str] = []
    updated: List[str] = []
    skipped: List[str] = []

    for title, expected_headers in SHEETS.items():
        worksheet = worksheets_by_title[title]
        current_headers = list(header_cache.get(title, []))
        if not current_headers:
            with_gspread_retry(
                lambda worksheet=worksheet, headers=expected_headers: worksheet.update(
                    values=[headers],
                    range_name="1:1",
                ),
                f"initialize missing headers for '{title}'",
                sleep_fn=sleep_fn,
                print_fn=print_fn,
            )
            header_cache[title] = list(expected_headers)
            initialized.append(title)
            print_fn(f"Updated headers: {title} (initialized empty row)")
            _throttle(sleep_fn, LOOP_THROTTLE_SECONDS)
            continue

        missing = [header for header in expected_headers if header not in current_headers]
        if missing:
            next_headers = current_headers + missing
            with_gspread_retry(
                lambda worksheet=worksheet, values=next_headers: worksheet.update(
                    values=[values],
                    range_name="1:1",
                ),
                f"update headers for '{title}'",
                sleep_fn=sleep_fn,
                print_fn=print_fn,
            )
            header_cache[title] = next_headers
            updated.append(title)
            print_fn(f"Updated headers: {title} (+{', '.join(missing)})")
            _throttle(sleep_fn, LOOP_THROTTLE_SECONDS)
        else:
            skipped.append(title)
            print_fn(f"Skipped headers: {title}")
    return initialized, updated, skipped


def _validate_structure(
    spreadsheet: Any,
    worksheets_by_title: Dict[str, Any],
    header_cache: Dict[str, List[str]],
    *,
    sleep_fn: Callable[[float], None],
    print_fn: Callable[[str], None],
) -> None:
    missing_titles = [title for title in SHEETS if title not in worksheets_by_title]
    if missing_titles:
        raise RuntimeError(f"Bootstrap validation failed: missing worksheets {', '.join(missing_titles)}")

    invalid_titles = [
        title
        for title, expected_headers in SHEETS.items()
        if any(header not in header_cache.get(title, []) for header in expected_headers)
    ]
    if invalid_titles:
        refreshed = _fetch_header_cache(
            spreadsheet,
            {title: worksheets_by_title[title] for title in invalid_titles},
            sleep_fn=sleep_fn,
            print_fn=print_fn,
        )
        header_cache.update(refreshed)
        still_invalid = [
            title
            for title, expected_headers in SHEETS.items()
            if any(header not in header_cache.get(title, []) for header in expected_headers)
        ]
        if still_invalid:
            raise RuntimeError(
                "Bootstrap validation failed after retries: some worksheets still miss required headers: "
                + ", ".join(still_invalid)
            )


def bootstrap_spreadsheet(
    spreadsheet: Any,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
    print_fn: Callable[[str], None] = print,
) -> Dict[str, List[str]]:
    print_fn("Stage 1/4: loading worksheet metadata and caches")
    worksheets_by_title, header_cache = _load_worksheet_cache(
        spreadsheet,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )
    _throttle(sleep_fn, STAGE_THROTTLE_SECONDS)

    print_fn("Stage 2/4: creating missing worksheets")
    created = _create_missing_sheets(
        spreadsheet,
        worksheets_by_title,
        header_cache,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )
    _throttle(sleep_fn, STAGE_THROTTLE_SECONDS)

    print_fn("Stage 3/4: updating worksheet headers")
    initialized, updated, skipped = _update_headers(
        worksheets_by_title,
        header_cache,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )
    _throttle(sleep_fn, STAGE_THROTTLE_SECONDS)

    print_fn("Stage 4/4: validating final worksheet structure")
    _validate_structure(
        spreadsheet,
        worksheets_by_title,
        header_cache,
        sleep_fn=sleep_fn,
        print_fn=print_fn,
    )

    print_fn("\nBootstrap summary:")
    print_fn(f"- Created sheets: {len(created)}")
    print_fn(f"- Initialized headers: {len(initialized)}")
    print_fn(f"- Updated headers: {len(updated)}")
    print_fn(f"- Skipped headers: {len(skipped)}")
    if created:
        print_fn(f"  Created -> {', '.join(created)}")
    if initialized:
        print_fn(f"  Initialized -> {', '.join(initialized)}")
    if updated:
        print_fn(f"  Updated -> {', '.join(updated)}")
    print_fn("Bootstrap completed successfully.")
    return {
        "created": created,
        "initialized": initialized,
        "updated": updated,
        "skipped": skipped,
    }


def main() -> None:
    creds_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = with_gspread_retry(
        lambda: gc.open_by_key(sheet_id),
        "open spreadsheet by key",
    )
    bootstrap_spreadsheet(sh)

    print("\nCharacter profile Prompt System v3 recommended keys:")
    print("- " + ", ".join(CHARACTER_PROFILE_V3_FIELDS))


if __name__ == "__main__":
    main()
