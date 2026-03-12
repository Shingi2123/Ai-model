from datetime import date

from virtual_persona.services.wardrobe import WardrobeManager


class DummyWardrobeState:
    def __init__(self, rows):
        self.rows = rows
        self.logs = []

    def load_wardrobe_items(self):
        return self.rows

    def load_outfit_memory(self):
        return []

    def save_run_log(self, status, message):
        self.logs.append((status, message))


def test_select_outfit_required_categories_present():
    manager = WardrobeManager("config/wardrobe.example.json")
    outfit = manager.select_outfit(
        temp_c=12,
        condition="cloudy",
        preferred_style="soft minimal",
        today=date(2026, 1, 15),
        day_type="work_day",
        city="Prague",
    )

    ids = outfit.item_ids
    assert any("top" in item or "shirt" in item or "turtleneck" in item for item in ids)
    assert any("bottom" in item or "trousers" in item for item in ids)
    assert any("shoes" in item or "sneakers" in item or "loafers" in item for item in ids)


def test_select_outfit_adds_outerwear_when_cold_if_available():
    manager = WardrobeManager("config/wardrobe.example.json")
    manager.catalog.items.append(
        manager.catalog.items[0].__class__(
            id="outerwear_trench_1",
            category="outerwear",
            name="Trench",
            styles=["all"],
            colors=["beige"],
            season=["all"],
            temp_min_c=-10,
            temp_max_c=20,
            weather_tags=["all"],
            cooldown_days=0,
            last_used=None,
        )
    )

    outfit = manager.select_outfit(
        temp_c=5,
        condition="cloudy",
        preferred_style="soft minimal",
        today=date(2026, 1, 15),
        day_type="work_day",
        city="Prague",
    )

    assert any("outerwear" in item or "trench" in item for item in outfit.item_ids)


def test_sheet_mapping_avoids_fallback_when_wardrobe_has_compatible_items():
    rows = [
        {"item_id": "shirt_1", "name": "Shirt", "category": "shirt", "style_tags": "soft minimal", "season_tags": "spring", "weather_tags": "clear", "temp_min_c": 8, "temp_max_c": 28, "status": "active"},
        {"item_id": "jeans_1", "name": "Jeans", "category": "jeans", "style_tags": "soft minimal", "season_tags": "spring", "weather_tags": "clear", "temp_min_c": 8, "temp_max_c": 28, "status": "active"},
        {"item_id": "sneakers_1", "name": "Sneakers", "category": "sneakers", "style_tags": "soft minimal", "season_tags": "spring", "weather_tags": "clear", "temp_min_c": 8, "temp_max_c": 30, "status": "active"},
    ]
    state = DummyWardrobeState(rows)
    manager = WardrobeManager(state)

    outfit = manager.select_outfit(
        temp_c=16,
        condition="sunny",
        preferred_style="soft minimal",
        today=date(2026, 4, 15),
        day_type="work_day",
        city="Paris",
    )

    assert not any(item.startswith("fallback_") for item in outfit.item_ids)


def test_soft_degradation_works_before_fallback():
    rows = [
        {"item_id": "top_1", "name": "Top", "category": "top", "style_tags": "all", "season_tags": "all", "weather_tags": "all", "temp_min_c": 0, "temp_max_c": 12, "status": "active"},
        {"item_id": "bottom_1", "name": "Bottom", "category": "bottom", "style_tags": "all", "season_tags": "all", "weather_tags": "all", "temp_min_c": 0, "temp_max_c": 12, "status": "active"},
        {"item_id": "shoes_1", "name": "Shoes", "category": "shoes", "style_tags": "all", "season_tags": "all", "weather_tags": "all", "temp_min_c": 0, "temp_max_c": 12, "status": "active"},
    ]
    state = DummyWardrobeState(rows)
    manager = WardrobeManager(state)

    # temp is slightly out of strict range, should still pass via soft/tolerant path
    outfit = manager.select_outfit(
        temp_c=15,
        condition="cloudy",
        preferred_style="soft minimal",
        today=date(2026, 4, 15),
        day_type="work_day",
        city="Paris",
    )

    assert set(outfit.item_ids) == {"top_1", "bottom_1", "shoes_1"}
