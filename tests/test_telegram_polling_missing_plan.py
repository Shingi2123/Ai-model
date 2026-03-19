from datetime import date
import asyncio
import types
from unittest.mock import Mock

from test_telegram_polling import _load_module


def test_show_today_plan_returns_missing_plan_message_without_generation(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = module.PlanScreenContext(
        target_date=target_date,
        city="",
        day_type="work_day",
        narrative_phase="routine_stability",
        persona_timezone="Europe/Prague",
        user_timezone="Asia/Pavlodar",
    )

    generate_day = Mock(side_effect=AssertionError("generate_day must not run in polling UI"))
    provider_generate = Mock(side_effect=AssertionError("provider.generate must not run in polling UI"))
    content_generate = Mock(side_effect=AssertionError("content_generator.generate must not run in polling UI"))

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (empty_context, []))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)
    module.orchestrator.provider = types.SimpleNamespace(generate=provider_generate)
    module.orchestrator.content_generator = types.SimpleNamespace(generate=content_generate)

    class LoadingMessage:
        def __init__(self):
            self.edit_payload = None

        async def edit_text(self, text, reply_markup=None):
            self.edit_payload = {"text": text, "reply_markup": reply_markup}

    class Message:
        def __init__(self):
            self.loading = LoadingMessage()

        async def reply_text(self, _text):
            return self.loading

    update = types.SimpleNamespace(message=Message())
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.show_today_plan(update, context))

    assert update.message.loading.edit_payload["text"] == module.MISSING_PLAN_MESSAGE
    assert generate_day.call_count == 0
    assert provider_generate.call_count == 0
    assert content_generate.call_count == 0
    assert "plan_screen" not in context.user_data


def test_callback_refresh_without_plan_returns_missing_plan_message(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = module.PlanScreenContext(
        target_date=target_date,
        city="",
        day_type="work_day",
        narrative_phase="routine_stability",
        persona_timezone="Europe/Prague",
        user_timezone="Asia/Pavlodar",
    )

    generate_day = Mock(side_effect=AssertionError("generate_day must not run in callback refresh"))
    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (empty_context, []))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)
    module.logger.exception = Mock()

    class Query:
        def __init__(self):
            self.data = "plan:2026-03-20"
            self.answer_calls = []
            self.edit_payload = None

        async def answer(self, *args, **kwargs):
            self.answer_calls.append((args, kwargs))

        async def edit_message_text(self, **kwargs):
            self.edit_payload = kwargs

    query = Query()
    update = types.SimpleNamespace(callback_query=query)
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert query.edit_payload["text"] == module.MISSING_PLAN_MESSAGE
    assert generate_day.call_count == 0
    assert module.logger.exception.call_count == 0


def test_plan_command_without_plan_returns_missing_plan_message(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = module.PlanScreenContext(
        target_date=target_date,
        city="",
        day_type="work_day",
        narrative_phase="routine_stability",
        persona_timezone="Europe/Prague",
        user_timezone="Asia/Pavlodar",
    )

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
