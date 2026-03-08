from datetime import date

from virtual_persona.models.domain import DayScene, OutfitSelection
from virtual_persona.pipeline.continuity_checker import ContinuityChecker


def test_continuity_detects_city_jump():
    checker = ContinuityChecker()
    issues = checker.run(
        {
            "date": date(2026, 1, 12),
            "city": "Rome",
            "day_type": "coffee_morning",
            "weather": type("W", (), {"condition": "clear"})(),
            "recent_history": [{"date": "2026-01-11", "city": "Paris", "outfit_ids": ["x"]}],
        },
        [DayScene(block="morning", location="cafe", description="Sun", mood="calm", time_of_day="morning")],
        OutfitSelection(item_ids=["a"], summary="a"),
    )
    assert any(i.code == "CITY_JUMP" for i in issues)
