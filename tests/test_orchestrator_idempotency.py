from pathlib import Path


def test_orchestrator_has_day_freeze_and_force_regenerate_flag():
    source = Path("src/virtual_persona/pipeline/orchestrator.py").read_text(encoding="utf-8")
    assert "def _load_frozen_day" in source
    assert "if not force_regenerate" in source
    assert "mode=reuse" in source
    assert 'mode = "regenerate" if force_regenerate else "create"' in source
