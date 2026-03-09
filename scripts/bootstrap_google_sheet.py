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
    "cities": ["city", "country", "timezone", "lat", "lng"],
    "scene_library": ["scene_id", "day_type", "time_block", "location", "description", "mood", "tags"],
    "daily_calendar": ["date", "city", "day_type", "notes"],
    "content_history": ["date", "city", "day_type", "outfit_ids", "scenes", "post_caption"],
    "continuity_flags": ["date", "level", "code", "message"],
    "prompt_templates": ["key", "template"],
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
            print(f"Exists: {title}")


if __name__ == "__main__":
    main()
