from pathlib import Path


def test_orchestrator_has_day_freeze_and_force_regenerate_flag():
    source = Path("src/virtual_persona/pipeline/orchestrator.py").read_text(encoding="utf-8")
    assert "def _load_frozen_day" in source
    assert "if not force_regenerate" in source
    assert "mode=reuse" in source
    assert 'mode = "regenerate" if force_regenerate else "create"' in source


def test_orchestrator_quality_trace_contains_new_compact_fields():
    source = Path("src/virtual_persona/pipeline/orchestrator.py").read_text(encoding="utf-8")
    assert "device_profile=" in source
    assert "camera_behavior_used=" in source
    assert "framing_style_used=" in source
    assert "favorite_location_used=" in source
    assert "social_behavior_mode=" in source
    assert "anti_synthetic_cleaner_applied=" in source
