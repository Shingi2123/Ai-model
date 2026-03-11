from virtual_persona.storage.state_store import GoogleSheetsStateStore


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
        self._sheet_cache = {}
        self._ws_map = {
            "scene_memory": FakeWS(),
            "activity_memory": FakeWS(),
            "location_memory": FakeWS(),
        }

    def available(self) -> bool:
        return True

    def _get_ws(self, title: str):
        return self._ws_map[title]


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
