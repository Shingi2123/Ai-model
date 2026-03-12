from pathlib import Path


def test_orchestrator_generate_day_resets_day_records_before_persist():
    source = Path("src/virtual_persona/pipeline/orchestrator.py").read_text(encoding="utf-8")
    assert 'if hasattr(self.state, "reset_day_records")' in source
    assert 'self.state.reset_day_records(context["date"].isoformat())' in source
