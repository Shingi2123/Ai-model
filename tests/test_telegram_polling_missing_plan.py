from datetime import date
import asyncio
import types
from unittest.mock import Mock

from test_telegram_polling import _load_module, _make_context


def test_callback_back_to_plan_does_not_trigger_generation_when_plan_missing(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = _make_context(module, target_date, city="")

    generate_day = Mock(side_effect=AssertionError("generate_day must not run on back-to-plan"))
    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (empty_context, []))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)
    module.logger.exception = Mock()

    class Query:
        def __init__(self):
            self.data = "back:plan:2026-03-20"
            self.answer_calls = []
            self.edit_payload = None
            self.from_user = types.SimpleNamespace(id=600)

        async def answer(self, *args, **kwargs):
            self.answer_calls.append((args, kwargs))

        async def edit_message_text(self, **kwargs):
            self.edit_payload = kwargs

    query = Query()
    update = types.SimpleNamespace(
        callback_query=query,
        effective_chat=types.SimpleNamespace(id=500),
        effective_user=types.SimpleNamespace(id=600),
    )
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert query.edit_payload["text"] == module.MISSING_PLAN_MESSAGE
    assert generate_day.call_count == 0
    assert module.logger.exception.call_count == 0


def test_plan_command_without_plan_returns_missing_plan_message(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = _make_context(module, target_date, city="")

    generate_day = Mock(side_effect=AssertionError("generate_day must not run in command flow"))
    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (empty_context, []))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)

    replies = []

    class Message:
        text = "/today"

        async def reply_text(self, text):
            replies.append(text)

    update = types.SimpleNamespace(message=Message())
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.plan_cmd(update, context))

    assert replies == [module.MISSING_PLAN_MESSAGE]
    assert generate_day.call_count == 0
