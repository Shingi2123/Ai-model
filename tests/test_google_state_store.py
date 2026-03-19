from virtual_persona.storage.state_store import GoogleSheetsStateStore, LocalStateStore, TelegramStateView, build_state_store
from virtual_persona.models.domain import DailyPackage, GeneratedContent, OutfitSelection, PublishingPlanItem, SunSnapshot, WeatherSnapshot
from datetime import date, datetime


class FakeWS:
    def __init__(self):
        self.cleared = False
        self.updated = None
        self.rows = []
        self.header = []

    def clear(self):
        self.cleared = True

    def update(self, values):
        self.updated = values

    def append_row(self, row):
        self.rows.append(row)

    def row_values(self, idx):
        if idx == 1:
            return list(self.header)
        return []


class HelperGoogleStore(GoogleSheetsStateStore):
    def __init__(self):
        # do not call parent initializer (network/auth)
        self.json_path = ""
        self.sheet_id = ""
        self.client = object()
        self.sheet = object()
        self.last_error = ""
        self._sheet_cache = {}
        self._ws_cache = {}
        self._headers_ensured = set()
        self._worksheet_fetch_count = 0
        self._ws_map = {
            "publishing_plan": FakeWS(),
            "life_state": FakeWS(),
            "daily_calendar": FakeWS(),
            "content_history": FakeWS(),
            "scene_memory": FakeWS(),
            "activity_memory": FakeWS(),
            "location_memory": FakeWS(),
            "content_moment_memory": FakeWS(),
            "run_log": FakeWS(),
        }
        self.records = {}
        self.replaced = {}

    def available(self) -> bool:
        return True

    def _get_ws(self, title: str):
        return self._ws_map[title]



    def _safe_records(self, title: str):
        return list(self.records.get(title, []))

    def _replace_records(self, title, headers, rows):
        self.replaced[title] = {"headers": headers, "rows": rows}
        if title in self._ws_map:
            ws = self._ws_map[title]
            ws.clear()
            ws.update([headers] + [[row.get(h, "") for h in headers] for row in rows])
            return
class CacheWS:
    def __init__(self):
        self.rows = []

    def get_all_records(self):
        return []

    def append_row(self, row):
        self.rows.append(row)


class CacheSheet:
    def __init__(self):
        self.calls = 0
        self.ws = CacheWS()

    def worksheet(self, _title: str):
        self.calls += 1
        return self.ws


class SettingsStub:
    state_backend = "local"
    google_service_account_json_path = ""
    google_sheet_id = ""


def test_google_store_scene_memory_saved_to_worksheet():
    store = HelperGoogleStore()

    store.save_scene_memory([{"scene_id": "s1", "last_used": "2026-03-12"}])

    ws = store._ws_map["scene_memory"]
    assert ws.cleared is True
    assert ws.updated is not None
    assert ws.updated[0][0] == "scene_id"
    assert ws.updated[1][0] == "s1"


def test_google_store_activity_and_location_saved_to_worksheet():
    store = HelperGoogleStore()

    store.save_activity_memory([{"activity_id": "a1", "activity_type": "walk"}])
    store.save_location_memory([{"location_id": "l1", "city": "Paris", "name": "CDG"}])

    aws = store._ws_map["activity_memory"]
    lws = store._ws_map["location_memory"]
    assert aws.cleared is True and aws.updated[1][0] == "a1"
    assert lws.cleared is True and lws.updated[1][0] == "l1"


def test_google_store_reuses_cached_worksheet_handle():
    store = GoogleSheetsStateStore.__new__(GoogleSheetsStateStore)
    store.json_path = ""
    store.sheet_id = ""
    store.client = object()
    store.sheet = CacheSheet()
    store.last_error = ""
    store._sheet_cache = {}
    store._ws_cache = {}
    store._headers_ensured = set()
    store._worksheet_fetch_count = 0

    ws_1 = store.get_worksheet("daily_calendar")
    ws_2 = store.get_worksheet("daily_calendar")

    assert ws_1 is ws_2
    assert store.sheet.calls == 1
    assert store._worksheet_fetch_count == 1


def test_telegram_state_view_proxies_base_store_methods_needed_for_generation():
    base = build_state_store(SettingsStub(), mode="telegram")
    assert isinstance(base, TelegramStateView)
    assert hasattr(base, "load_publishing_plan")
    assert hasattr(base, "load_cities")
    assert hasattr(base, "load_life_state")
    assert hasattr(base, "load_character_profile")
    assert hasattr(base, "load_calendar")


def test_google_store_reset_day_records_removes_target_date_rows():
    store = HelperGoogleStore()
    store.records = {
        "publishing_plan": [
            {"date": "2026-03-12", "publication_id": "p1"},
            {"date": "2026-03-13", "publication_id": "p2"},
        ],
        "life_state": [{"date": "2026-03-12"}],
        "daily_calendar": [{"date": "2026-03-12"}],
        "content_history": [{"date": "2026-03-12"}, {"date": "2026-03-11"}],
        "content_moment_memory": [{"date": "2026-03-12"}, {"date": "2026-03-12"}],
    }

    store.reset_day_records("2026-03-12")

    assert [r["date"] for r in store.replaced["publishing_plan"]["rows"]] == ["2026-03-13"]
    assert store.replaced["life_state"]["rows"] == []
    assert [r["date"] for r in store.replaced["content_history"]["rows"]] == ["2026-03-11"]
    assert store.replaced["content_moment_memory"]["rows"] == []


def test_local_store_reset_day_records_keeps_single_day_slice(tmp_path):
    store = LocalStateStore(base_dir=str(tmp_path / "state"))
    target = "2026-03-12"

    for name in ["publishing_plan", "life_state", "daily_calendar", "content_history", "content_moment_memory"]:
        path = store.base_dir / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('[{"date":"2026-03-12"},{"date":"2026-03-13"}]', encoding='utf-8')

    store.reset_day_records(target)

    for name in ["publishing_plan", "life_state", "daily_calendar", "content_history", "content_moment_memory"]:
        rows = __import__('json').loads((store.base_dir / f"{name}.json").read_text(encoding='utf-8'))
        assert rows == [{"date": "2026-03-13"}]


def test_local_store_bootstraps_default_posting_rules(tmp_path):
    store = LocalStateStore(base_dir=str(tmp_path / "state"))
    rules = store.load_posting_rules()
    assert rules
    assert any(str(r.get("rule_id", "")).startswith("default-") for r in rules)


def test_google_store_content_moment_memory_uses_actual_sheet_header_order():
    store = HelperGoogleStore()
    ws = store._ws_map["content_moment_memory"]
    ws.header = [
        "date", "city", "day_type", "scene_moment", "scene_moment_type", "moment_signature", "visual_focus", "scene_source",
        "shot_archetype", "platform_intent", "publish_score", "publish_decision", "decision_reason",
        "camera_behavior_used", "framing_style_used", "favorite_location_used", "social_behavior_mode",
    ]

    row = {
        "date": "2026-03-14",
        "city": "Paris",
        "day_type": "work_day",
        "scene_moment": "coffee line",
        "scene_moment_type": "micro",
        "moment_signature": "sig",
        "visual_focus": "hands",
        "scene_source": "planner",
        "shot_archetype": "close",
        "platform_intent": "reach",
        "camera_behavior_used": "handheld",
        "framing_style_used": "off-center",
        "favorite_location_used": "corner cafe",
        "social_behavior_mode": "observing",
        "publish_score": 0.88,
        "publish_decision": "publish",
        "decision_reason": "high novelty",
    }
    store.append_content_moment_memory(row)

    assert ws.rows
    values = ws.rows[0]
    assert values[10] == 0.88
    assert values[11] == "publish"
    assert values[12] == "high novelty"
    assert values[13] == "handheld"


def test_google_store_publishing_plan_uses_actual_sheet_header_order():
    store = HelperGoogleStore()
    ws = store._ws_map["publishing_plan"]
    ws.header = [
        "publication_id", "date", "platform", "post_time", "content_type", "city", "day_type", "narrative_phase",
        "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus", "activity_type",
        "outfit_ids", "prompt_type", "prompt_text", "negative_prompt", "prompt_package_json", "caption_text",
        "short_caption", "shot_archetype", "framing_mode", "generation_mode", "reference_type", "publish_score",
        "selection_reason", "notes", "identity_mode", "reference_pack_type",
    ]

    row = {
        "publication_id": "pub-1",
        "date": "2026-03-14",
        "platform": "Instagram",
        "post_time": "09:30",
        "content_type": "photo",
        "city": "Paris",
        "day_type": "work_day",
        "narrative_phase": "routine_stability",
        "scene_moment": "Coffee line before boarding",
        "scene_source": "planner",
        "scene_moment_type": "transition",
        "moment_signature": "sig-1",
        "visual_focus": "coffee cup",
        "activity_type": "coffee_pause",
        "outfit_ids": "look-1",
        "prompt_type": "photo",
        "prompt_text": "Prompt body",
        "negative_prompt": "bad anatomy",
        "prompt_package_json": "{\"generation_mode\":\"friend_shot_mode\"}",
        "caption_text": "Canonical caption",
        "short_caption": "Canonical short caption",
        "shot_archetype": "friend-shot",
        "framing_mode": "friend-shot, 3/4 body",
        "generation_mode": "friend_shot_mode",
        "reference_type": "lifestyle",
        "publish_score": 3.6,
        "selection_reason": "selected_by_primary_decision_and_diversity",
        "notes": "score=3.60; reasons=visual_focus",
        "identity_mode": "reference_manifest",
        "reference_pack_type": "identity_lock",
    }

    store.append_publishing_plan(row)

    values = ws.rows[0]
    assert values[19] == "Canonical caption"
    assert values[20] == "Canonical short caption"
    assert values[21] == "friend-shot"
    assert values[22] == "friend-shot, 3/4 body"
    assert values[23] == "friend_shot_mode"
    assert values[24] == "lifestyle"
    assert values[25] == 3.6
    assert values[26] == "selected_by_primary_decision_and_diversity"
    assert values[27] == "score=3.60; reasons=visual_focus"
    assert values[28] == "reference_manifest"


def test_google_store_publishing_plan_populates_legacy_prompt_column():
    store = HelperGoogleStore()
    ws = store._ws_map["publishing_plan"]
    ws.header = ["publication_id", "prompt", "prompt_text"]

    row = {
        "publication_id": "pub-1",
        "prompt_text": "Canonical final prompt",
    }

    store.append_publishing_plan(row)

    values = ws.rows[0]
    assert values[1] == "Canonical final prompt"
    assert values[2] == "Canonical final prompt"


def test_google_store_run_log_persists_structured_trace_fields():
    store = HelperGoogleStore()
    ws = store._ws_map["run_log"]
    ws.header = ["timestamp", "status", "message", "device_profile", "camera_behavior_used", "framing_style_used", "favorite_location_used", "social_behavior_mode", "anti_synthetic_cleaner_applied"]

    store.save_run_log(
        "debug",
        "quality_trace ...",
        device_profile="pixel_7",
        camera_behavior_used="handheld",
        framing_style_used="off-center",
        favorite_location_used="corner cafe",
        social_behavior_mode="observing",
        anti_synthetic_cleaner_applied=True,
    )

    assert ws.rows
    values = ws.rows[0]
    assert values[3] == "pixel_7"
    assert values[4] == "handheld"
    assert values[5] == "off-center"
    assert values[6] == "corner cafe"
    assert values[7] == "observing"
    assert values[8] is True


def test_google_store_run_log_uses_actual_sheet_header_order():
    store = HelperGoogleStore()
    ws = store._ws_map["run_log"]
    ws.header = [
        "timestamp",
        "status",
        "message",
        "camera_behavior_used",
        "framing_style_used",
        "favorite_location_used",
        "social_behavior_mode",
        "anti_synthetic_cleaner_applied",
        "device_profile",
    ]

    store.save_run_log(
        "debug",
        "quality_trace ...",
        device_profile="pixel_7",
        camera_behavior_used="handheld",
        framing_style_used="off-center",
        favorite_location_used="corner cafe",
        social_behavior_mode="observing",
        anti_synthetic_cleaner_applied=True,
    )

    values = ws.rows[0]
    assert values[3] == "handheld"
    assert values[8] == "pixel_7"


def test_google_store_history_uses_selected_publication_moment():
    store = HelperGoogleStore()
    ws = store._ws_map["content_history"]
    ws.header = [
        "date", "city", "day_type", "outfit_ids", "scenes", "post_caption",
        "scene_moment", "scene_source", "scene_moment_type", "moment_signature", "visual_focus",
    ]

    package = DailyPackage(
        generated_at=datetime.utcnow(),
        date=date(2026, 3, 14),
        city="Paris",
        day_type="work_day",
        summary="",
        weather=WeatherSnapshot(city="Paris", temp_c=20.0, condition="Clear", humidity=40, wind_speed=2.0, cloudiness=10),
        sun=SunSnapshot(sunrise_local=datetime.utcnow(), sunset_local=datetime.utcnow()),
        outfit=OutfitSelection(item_ids=["jacket"], summary="Look"),
        scenes=[],
        content=GeneratedContent(post_caption="Selected caption", story_lines=[], photo_prompts=[], video_prompts=[], publish_windows=[], creative_notes=[]),
        publishing_plan=[
            PublishingPlanItem(
                publication_id="2026-03-14-01",
                date=date(2026, 3, 14),
                platform="Instagram",
                post_time="10:00",
                content_type="photo",
                city="Paris",
                day_type="work_day",
                narrative_phase="routine_stability",
                scene_moment="selected moment",
                scene_source="selected source",
                scene_moment_type="selected type",
                moment_signature="selected-signature",
                visual_focus="selected focus",
                activity_type="walk",
                outfit_ids=["jacket"],
                prompt_type="photo",
                prompt_text="prompt",
            )
        ],
    )

    store.append_history(package)

    values = ws.rows[0]
    assert values[5] == "Selected caption"
    assert values[6] == "selected moment"
    assert values[7] == "selected source"
    assert values[8] == "selected type"
    assert values[9] == "selected-signature"
    assert values[10] == "selected focus"
