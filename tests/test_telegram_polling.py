from pathlib import Path
import asyncio
import importlib.util
import sys
import types
from datetime import date
from unittest.mock import Mock


class _FakeBadRequest(Exception):
    pass


def _install_telegram_stubs() -> None:
    telegram_module = types.ModuleType("telegram")

    class InlineKeyboardButton:
        def __init__(self, label: str, callback_data: str):
            self.label = label
            self.callback_data = callback_data

    class InlineKeyboardMarkup:
        def __init__(self, keyboard):
            self.keyboard = keyboard

    class ReplyKeyboardMarkup:
        def __init__(self, keyboard, resize_keyboard: bool = False):
            self.keyboard = keyboard
            self.resize_keyboard = resize_keyboard

    class Update:
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

    class Application:
        @staticmethod
        def builder():
            return _ApplicationBuilder()

    class CallbackQueryHandler:
        def __init__(self, *_args, **_kwargs):
            pass

    class CommandHandler:
        def __init__(self, *_args, **_kwargs):
            pass

    class MessageHandler:
        def __init__(self, *_args, **_kwargs):
            pass

    class ContextTypes:
        DEFAULT_TYPE = object

    class _Filters:
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

    from virtual_persona.storage.state_store import TelegramStateView

    class PipelineOrchestrator:
        def __init__(self, _settings, mode="full"):
            self.mode = mode
            base = types.SimpleNamespace(
                available=lambda: True,
                load_publishing_plan=lambda _d=None: [],
                load_cities=lambda: [],
                load_life_state=lambda: [],
            )
            self.state = TelegramStateView(base)
            self.telegram_delivery_service = types.SimpleNamespace(_resolve_persona_timezone=lambda _city: "Europe/Prague")

        def _load_frozen_day(self, _target_date):
            return None

    orchestrator_module.PipelineOrchestrator = PipelineOrchestrator
    sys.modules["virtual_persona.pipeline.orchestrator"] = orchestrator_module


def _load_module():
    _install_telegram_stubs()
    _install_orchestrator_stub()

    module_name = "telegram_polling_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, Path("scripts/telegram_polling.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    assert module.orchestrator.mode == "telegram"
    return module


def _context_and_items(module):
    plan_context = module.PlanScreenContext(
        target_date=date(2026, 3, 12),
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )
    return plan_context, []


def test_callback_refresh_ignores_message_not_modified(monkeypatch):
    module = _load_module()
    plan_context, plan_items = _context_and_items(module)

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

    assert query.answer_calls == [((), {})]
    assert query.edit_calls == 1
    assert module.logger.exception.call_count == 0


def test_callback_refresh_recovers_from_stale_session(monkeypatch):
    module = _load_module()
    plan_context, plan_items = _context_and_items(module)

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("План публикаций", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached")
    module.logger.exception = Mock()

    class Query:
        def __init__(self):
            self.data = "plan:2026-03-12"
            self.answer_calls = []
            self.edit_payload = None

        async def answer(self, *args, **kwargs):
            self.answer_calls.append((args, kwargs))

        async def edit_message_text(self, **kwargs):
            self.edit_payload = kwargs

    query = Query()
    update = types.SimpleNamespace(callback_query=query)
    context = types.SimpleNamespace(user_data={"plan_screen": {"broken": "state"}})

    asyncio.run(module.callback_nav(update, context))

    assert query.edit_payload["text"] == "План публикаций"
    assert query.answer_calls == [((), {})]
    assert module.logger.exception.call_count == 0


def test_callback_back_to_plan_after_prompt(monkeypatch):
    module = _load_module()
    plan_context, plan_items = _context_and_items(module)

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("План публикаций", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached")

    class Query:
        def __init__(self):
            self.data = "back:plan:2026-03-12"
            self.answer_calls = []

        async def answer(self, *args, **kwargs):
            self.answer_calls.append((args, kwargs))

        async def edit_message_text(self, **_kwargs):
            return None

    query = Query()
    update = types.SimpleNamespace(callback_query=query)
    context = types.SimpleNamespace(user_data={"plan_screen": "cached"})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert context.user_data["plan_screen"] == "cached"


def test_select_screen_items_prefers_persisted_plan_for_detail_views():
    module = _load_module()
    target_date = date(2026, 3, 12)
    cached_context = module.PlanScreenContext(
        target_date=target_date,
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )

    items, source = module._select_screen_items(
        parsed=types.SimpleNamespace(view="prompt"),
        target_date=target_date,
        cached_context=cached_context,
        cached_items=["stale-cached-item"],
        plan_items=["canonical-plan-item"],
    )

    assert items == ["canonical-plan-item"]
    assert source == "publishing_plan"


def test_select_screen_items_falls_back_to_cached_context_only_when_plan_missing():
    module = _load_module()
    target_date = date(2026, 3, 12)
    cached_context = module.PlanScreenContext(
        target_date=target_date,
        city="Paris",
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )

    items, source = module._select_screen_items(
        parsed=types.SimpleNamespace(view="caption"),
        target_date=target_date,
        cached_context=cached_context,
        cached_items=["cached-item"],
        plan_items=[],
    )

    assert items == ["cached-item"]
    assert source == "serialized_callback_context"


def test_start_button_and_safe_wrappers_use_utf8_runtime(monkeypatch):
    module = _load_module()
    plan_context, plan_items = _context_and_items(module)

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("План публикаций", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached")

    wrapper_calls = {"answer": 0, "edit": 0}

    async def fake_safe_answer(_query, text=None, *, show_alert=False):
        wrapper_calls["answer"] += 1
        return True

    async def fake_safe_edit(_query, *, text, markup, parse_mode=None):
        wrapper_calls["edit"] += 1
        assert text == "План публикаций"
        return True

    monkeypatch.setattr(module, "safe_answer_callback", fake_safe_answer)
    monkeypatch.setattr(module, "safe_edit_message", fake_safe_edit)

    class Query:
        def __init__(self):
            self.data = "plan:2026-03-12"

    query = Query()
    update = types.SimpleNamespace(callback_query=query)
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert wrapper_calls == {"answer": 1, "edit": 1}
    assert module.GET_PLAN_BUTTON == "📅 Получить план на сегодня"
