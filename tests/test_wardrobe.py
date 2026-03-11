from datetime import date

from virtual_persona.services.wardrobe import WardrobeManager


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
