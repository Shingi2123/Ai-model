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
    "wardrobe_items": ["item_id", "name", "category", "subcategory", "color", "style_tags", "season_tags", "weather_tags", "occasion_tags", "work_allowed", "layer_role", "warmth", "status", "owned_since", "last_used", "wear_count", "times_in_content", "capsule_role", "style_vector", "priority_score", "notes"],
    "outfit_memory": ["date", "outfit_id", "item_ids", "city", "day_type", "weather", "occasion", "used_in_content", "repeat_score", "notes"],
    "wardrobe_actions": ["date", "action_type", "target_item_id", "reason", "status", "context_day_type", "context_season", "context_city", "notes"],
    "shopping_candidates": ["candidate_id", "category", "subcategory", "suggested_name", "reason", "priority", "season", "style_match", "gap_score", "status", "notes"],
    "cities": ["city", "country", "timezone", "lat", "lng"],
    "scene_library": ["scene_id", "day_type", "time_block", "location", "description", "mood", "tags"],
    "scene_memory": ["scene_id", "last_used", "usage_count", "last_city", "last_day_type", "repeat_cooldown", "status", "notes"],
    "scene_candidates": ["candidate_id", "day_type", "time_block", "location", "description", "mood", "activity_hint", "city", "season", "source_context", "generated_by_ai", "status", "score", "notes"],
    "activity_candidates": ["candidate_id", "activity_code", "activity_label", "day_type", "time_block", "city", "season", "mood_fit", "fatigue_min", "fatigue_max", "weather_fit", "source_context", "generated_by_ai", "status", "score", "notes"],
    "style_rules": ["rule_id", "rule_type", "target", "rule_value", "priority", "status", "notes"],
    "activity_memory": ["activity_id", "activity_type", "last_used", "usage_count", "context_tags", "status", "notes"],
    "location_memory": ["location_id", "city", "location_type", "name", "usage_count", "visit_frequency", "last_used", "last_scene", "cooldown_days", "season_tags", "status", "notes"],
    "world_candidates": ["candidate_id", "candidate_type", "name", "city", "description", "source_reason", "priority", "status"],
    "story_arcs": ["arc_id", "arc_type", "title", "status", "start_date", "progress", "description"],
    "activity_evolution": ["activity_id", "origin_activity", "generated_variant", "reason", "status"],
    "daily_calendar": ["date", "city", "day_type", "notes"],
    "content_history": ["date", "city", "day_type", "outfit_ids", "scenes", "post_caption", "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus"],
    "content_moment_memory": ["date", "city", "day_type", "scene_moment", "scene_moment_type", "moment_signature", "visual_focus", "scene_source", "publish_score", "publish_decision", "decision_reason"],
    "publishing_plan": ["publication_id", "date", "platform", "post_time", "content_type", "city", "day_type", "narrative_phase", "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus", "activity_type", "outfit_ids", "prompt_type", "prompt_text", "negative_prompt", "prompt_package_json", "shot_archetype", "platform_intent", "caption_text", "short_caption", "post_timezone", "delivery_status", "notes", "publish_score", "selection_reason"],
    "posting_rules": ["rule_id", "platform", "content_type", "preferred_time", "enabled", "priority", "min_per_day", "max_per_day", "day_type_filter", "narrative_phase_filter", "city_filter", "weekday_filter", "notes"],
    "delivery_log": ["date", "delivery_type", "status", "message_id", "error", "details"],
    "continuity_flags": ["date", "level", "code", "message"],
    "prompt_templates": ["key", "template"],
    "prompt_blocks": ["key", "content", "priority", "enabled"],
    "route_pool": ["route_id", "origin_city", "destination_city", "flight_type", "weight", "active"],
    "life_state": ["date", "current_city", "day_type", "season", "fatigue_level", "mood_base", "reason", "continuity_note", "narrative_phase", "energy_state", "rhythm_state", "novelty_pressure", "recovery_need"],
    "narrative_memory": ["date", "narrative_phase", "energy_state", "rhythm_state", "novelty_pressure", "recovery_need", "reason"],
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
    created = []
    updated = []

    for title, headers in SHEETS.items():
        if title not in existing:
            ws = sh.add_worksheet(title=title, rows=1000, cols=max(20, len(headers) + 3))
            ws.append_row(headers)
            created.append(title)
            print(f"Created: {title}")
        else:
            ws = sh.worksheet(title)
            current_headers = ws.row_values(1)
            if not current_headers:
                ws.append_row(headers)
                print(f"Initialized headers: {title}")
                continue

            missing = [h for h in headers if h not in current_headers]
            if missing:
                ws.update("1:1", [current_headers + missing])
                updated.append(title)
                print(f"Updated headers: {title} (+{', '.join(missing)})")
            else:
                print(f"Exists: {title}")

    print("\nBootstrap summary:")
    print(f"- Created sheets: {len(created)}")
    print(f"- Updated headers: {len(updated)}")
    if created:
        print(f"  Created -> {', '.join(created)}")
    if updated:
        print(f"  Updated -> {', '.join(updated)}")


if __name__ == "__main__":
    main()
