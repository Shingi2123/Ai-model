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

import gspread
from google.oauth2.service_account import Credentials

SHEETS = {
    "character_profile": ["field", "value"],
    "wardrobe": ["id", "category", "name", "styles", "colors", "season", "temp_min_c", "temp_max_c", "weather_tags", "cooldown_days", "last_used"],
    "wardrobe_items": ["item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags", "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used", "wear_count", "times_in_content", "notes"],
    "outfit_memory": ["date", "outfit_id", "item_ids", "city", "day_type", "weather", "occasion", "used_in_content", "repeat_score", "notes"],
    "wardrobe_actions": ["date", "action_type", "target_item_id", "reason", "status", "notes"],
    "shopping_candidates": ["candidate_id", "category", "subcategory", "suggested_name", "reason", "priority", "season", "style_match", "status", "notes"],
    "cities": ["city", "country", "timezone", "lat", "lng"],
    "scene_library": ["scene_id", "day_type", "time_block", "location", "description", "mood", "tags"],
    "scene_memory": ["scene_id", "last_used", "usage_count", "last_city", "last_day_type", "repeat_cooldown", "status", "notes"],
    "activity_memory": ["activity_id", "activity_type", "last_used", "usage_count", "context_tags", "status", "notes"],
    "location_memory": ["location_id", "city", "location_type", "name", "usage_count", "last_used", "season_tags", "status", "notes"],
    "daily_calendar": ["date", "city", "day_type", "notes"],
    "content_history": ["date", "city", "day_type", "outfit_ids", "scenes", "post_caption"],
    "continuity_flags": ["date", "level", "code", "message"],
    "prompt_templates": ["key", "template"],
    "prompt_blocks": ["key", "content", "priority", "enabled"],
    "route_pool": ["route_id", "origin_city", "destination_city", "flight_type", "weight", "active"],
    "life_state": ["date", "current_city", "day_type", "season", "fatigue_level", "mood_base", "reason", "continuity_note"],
    "run_log": ["timestamp", "status", "message"],
}


def main() -> None:
    creds_path = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON_PATH"]
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    existing = {ws.title for ws in sh.worksheets()}
    for title, headers in SHEETS.items():
        if title not in existing:
            ws = sh.add_worksheet(title=title, rows=1000, cols=max(20, len(headers) + 3))
            ws.append_row(headers)
            print(f"Created: {title}")
        else:
            ws = sh.worksheet(title)
            current_headers = ws.row_values(1)
            if current_headers != headers:
                ws.update("1:1", [headers])
                print(f"Updated headers: {title}")
            else:
                print(f"Exists: {title}")


if __name__ == "__main__":
    main()
