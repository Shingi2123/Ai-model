from virtual_persona.storage.state_store import GoogleSheetsStateStore, LocalStateStore, TelegramStateView, build_state_store


class FakeWS:
    def __init__(self):
        self.cleared = False
        self.updated = None

    def clear(self):
        self.cleared = True

    def update(self, values):
        self.updated = values


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
            "scene_memory": FakeWS(),
            "activity_memory": FakeWS(),
            "location_memory": FakeWS(),
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
        if title in self._ws_map:
            ws = self._ws_map[title]
            ws.clear()
            ws.update([headers] + [[row.get(h, "") for h in headers] for row in rows])
            return
        self.replaced[title] = {"headers": headers, "rows": rows}
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


def test_telegram_state_view_exposes_only_needed_methods():
    base = build_state_store(SettingsStub(), mode="telegram")
    assert isinstance(base, TelegramStateView)
    assert hasattr(base, "load_publishing_plan")
    assert hasattr(base, "load_cities")
    assert hasattr(base, "load_life_state")
    assert not hasattr(base, "load_wardrobe")


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
