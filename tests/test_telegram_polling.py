from pathlib import Path
import asyncio
import importlib
import importlib.util
import sys
import types
from datetime import date
from unittest.mock import Mock


class _FakeBadRequest(Exception):
    pass


def _install_telegram_stubs() -> None:
    telegram_module = types.ModuleType("telegram")

    class InlineKeyboardButton:  # pragma: no cover - helper for import wiring
        def __init__(self, label: str, callback_data: str):
            self.label = label
            self.callback_data = callback_data

    class InlineKeyboardMarkup:  # pragma: no cover - helper for import wiring
        def __init__(self, keyboard):
            self.keyboard = keyboard

    class ReplyKeyboardMarkup:  # pragma: no cover - helper for import wiring
        def __init__(self, keyboard, resize_keyboard: bool = False):
            self.keyboard = keyboard
            self.resize_keyboard = resize_keyboard

    class Update:  # pragma: no cover - helper for import wiring
        pass

    telegram_module.InlineKeyboardButton = InlineKeyboardButton
    telegram_module.InlineKeyboardMarkup = InlineKeyboardMarkup
    telegram_module.ReplyKeyboardMarkup = ReplyKeyboardMarkup
    telegram_module.Update = Update

    telegram_error_module = types.ModuleType("telegram.error")
    telegram_error_module.BadRequest = _FakeBadRequest

    telegram_ext_module = types.ModuleType("telegram.ext")

    class _ApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return object()

    class Application:  # pragma: no cover - helper for import wiring
        @staticmethod
        def builder():
            return _ApplicationBuilder()

    class CallbackQueryHandler:  # pragma: no cover
        def __init__(self, *_args, **_kwargs):
            pass

    class CommandHandler:  # pragma: no cover
        def __init__(self, *_args, **_kwargs):
            pass

    class MessageHandler:  # pragma: no cover
        def __init__(self, *_args, **_kwargs):
            pass

    class ContextTypes:  # pragma: no cover
        DEFAULT_TYPE = object

    class _Filters:  # pragma: no cover
        @staticmethod
        def Regex(_pattern: str):
            return object()

    telegram_ext_module.Application = Application
    telegram_ext_module.CallbackQueryHandler = CallbackQueryHandler
    telegram_ext_module.CommandHandler = CommandHandler
    telegram_ext_module.ContextTypes = ContextTypes
    telegram_ext_module.MessageHandler = MessageHandler
    telegram_ext_module.filters = _Filters

    sys.modules["telegram"] = telegram_module
    sys.modules["telegram.error"] = telegram_error_module
    sys.modules["telegram.ext"] = telegram_ext_module


def _install_orchestrator_stub() -> None:
    orchestrator_module = types.ModuleType("virtual_persona.pipeline.orchestrator")

    class PipelineOrchestrator:
        def __init__(self, _settings):
            self.state = types.SimpleNamespace(load_publishing_plan=lambda _d: [])
            self.telegram_delivery_service = types.SimpleNamespace(_resolve_persona_timezone=lambda _city: "Europe/Prague")

    orchestrator_module.PipelineOrchestrator = PipelineOrchestrator
    sys.modules["virtual_persona.pipeline.orchestrator"] = orchestrator_module


def test_callback_refresh_ignores_message_not_modified(monkeypatch):
    _install_telegram_stubs()
    _install_orchestrator_stub()

    module_name = "telegram_polling_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, Path("scripts/telegram_polling.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    plan_context = module.PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )
    plan_items = []

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("План публикаций", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached")

    module.logger.info = Mock()
    module.logger.exception = Mock()

    class Query:
        def __init__(self):
            self.data = "plan:2026-03-12"
            self.answer_calls = []
            self.edit_calls = 0

        async def answer(self, *_args, **_kwargs):
            self.answer_calls.append((_args, _kwargs))

        async def edit_message_text(self, **_kwargs):
            self.edit_calls += 1
            raise module.BadRequest("Message is not modified")

    query = Query()
    update = types.SimpleNamespace(callback_query=query)
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert len(query.answer_calls) == 1
    assert query.answer_calls[0][0] == ("План уже актуален",)
    assert query.edit_calls == 1
    assert module.logger.exception.call_count == 0
    module.logger.info.assert_any_call("telegram_plan_view unchanged action=callback data=%s", query.data)
