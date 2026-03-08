from datetime import date

from virtual_persona.services.wardrobe import WardrobeManager


def test_select_outfit_required_categories_present():
    manager = WardrobeManager("config/wardrobe.example.json")
    outfit = manager.select_outfit(temp_c=12, condition="cloudy", preferred_style="soft minimal", today=date(2026, 1, 15))
    joined = " ".join(outfit.item_ids)
    assert "sneakers" in joined
    assert "trousers" in joined or "bottom" not in joined
