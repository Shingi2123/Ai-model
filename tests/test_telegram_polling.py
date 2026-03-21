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

        def generate_day(self, **_kwargs):
            return types.SimpleNamespace(date=date(2026, 3, 20), city="Prague", publishing_plan=[])

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


def _make_context(module, target_date: date, city: str = "Paris"):
    return module.PlanScreenContext(
        target_date=target_date,
        city=city,
        day_type="work_day",
        narrative_phase="recovery_phase",
        persona_timezone="Europe/Paris",
        user_timezone="Asia/Pavlodar",
    )


def _make_item(target_date: date, publication_id: str = "pub-1", city: str = "Paris"):
    return types.SimpleNamespace(
        publication_id=publication_id,
        date=target_date,
        platform="Instagram",
        post_time="09:30",
        content_type="photo",
        city=city,
        day_type="work_day",
        narrative_phase="recovery_phase",
        scene_moment="Morning coffee before leaving home",
        caption_text="Caption",
        short_caption="Short caption",
        post_timezone="Europe/Paris",
    )


def _message_update():
    class LoadingMessage:
        def __init__(self):
            self.edit_calls = []

        async def edit_text(self, text, reply_markup=None):
            self.edit_calls.append({"text": text, "reply_markup": reply_markup})

    class Message:
        def __init__(self):
            self.loading = LoadingMessage()
            self.replies = []
            self.chat = types.SimpleNamespace(id=500)
            self.from_user = types.SimpleNamespace(id=600)

        async def reply_text(self, text, reply_markup=None):
            self.replies.append({"text": text, "reply_markup": reply_markup})
            return self.loading

    message = Message()
    update = types.SimpleNamespace(
        message=message,
        effective_chat=types.SimpleNamespace(id=500),
        effective_user=types.SimpleNamespace(id=600),
    )
    return update, message.loading


def _callback_update(data: str):
    class Query:
        def __init__(self):
            self.data = data
            self.answer_calls = []
            self.edit_calls = []
            self.from_user = types.SimpleNamespace(id=600)

        async def answer(self, *args, **kwargs):
            self.answer_calls.append((args, kwargs))

        async def edit_message_text(self, **kwargs):
            self.edit_calls.append(kwargs)

    query = Query()
    update = types.SimpleNamespace(
        callback_query=query,
        effective_chat=types.SimpleNamespace(id=500),
        effective_user=types.SimpleNamespace(id=600),
    )
    return update, query


def test_show_today_plan_uses_existing_plan_without_generation(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    plan_context = _make_context(module, target_date)
    plan_items = [_make_item(target_date)]

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("PLAN", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached-plan")
    generate_day = Mock(side_effect=AssertionError("generate_day must not run when plan already exists"))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)

    update, loading = _message_update()
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.show_today_plan(update, context))

    assert loading.edit_calls[-1]["text"] == "PLAN"
    assert len(loading.edit_calls) == 1
    assert loading.edit_calls[-1]["reply_markup"] is not None
    assert generate_day.call_count == 0
    assert context.user_data["plan_screen"] == "cached-plan"


def test_show_today_plan_generates_if_missing_and_reloads_persisted_plan(monkeypatch):
    module = _load_module()
    target_date = date.today()
    empty_context = _make_context(module, target_date, city="")
    persisted_context = _make_context(module, target_date, city="Prague")
    generated_item = _make_item(target_date, city="Prague")

    load_calls = {"count": 0}

    def fake_load(_target_date):
        load_calls["count"] += 1
        if load_calls["count"] <= 2:
            return empty_context, []
        return persisted_context, [generated_item]

    generate_day = Mock(return_value=types.SimpleNamespace(date=target_date, city="Prague", publishing_plan=[]))

    async def fake_to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(module, "_load_persisted_plan", fake_load)
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("PLAN", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached-plan")
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)
    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)

    update, loading = _message_update()
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.show_today_plan(update, context))

    assert loading.edit_calls[0]["text"] == module.GENERATING_PLAN_MESSAGE
    assert loading.edit_calls[-1]["text"] == "PLAN"
    assert generate_day.call_args.kwargs == {"target_date": target_date}
    assert context.user_data["plan_screen"] == "cached-plan"


def test_show_today_plan_reports_generation_failure_without_crashing(monkeypatch):
    module = _load_module()
    target_date = date.today()
    empty_context = _make_context(module, target_date, city="")

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (empty_context, []))
    monkeypatch.setattr(module.logger, "exception", Mock())

    async def fake_to_thread(_func, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)

    update, loading = _message_update()
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.show_today_plan(update, context))

    assert loading.edit_calls[0]["text"] == module.GENERATING_PLAN_MESSAGE
    assert loading.edit_calls[-1]["text"] == module.GENERATION_FAILED_MESSAGE
    assert module.logger.exception.call_count >= 1
    assert "plan_screen" not in context.user_data


def test_callback_refresh_uses_same_generate_if_missing_flow(monkeypatch):
    module = _load_module()
    target_date = date.today()
    empty_context = _make_context(module, target_date, city="")
    persisted_context = _make_context(module, target_date, city="Prague")
    generated_item = _make_item(target_date, city="Prague")

    load_calls = {"count": 0}

    def fake_load(_target_date):
        load_calls["count"] += 1
        if load_calls["count"] <= 2:
            return empty_context, []
        return persisted_context, [generated_item]

    async def fake_to_thread(func, **kwargs):
        return func(**kwargs)

    monkeypatch.setattr(module, "_load_persisted_plan", fake_load)
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("PLAN", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached-plan")
    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(module.orchestrator, "generate_day", Mock(return_value=types.SimpleNamespace()), raising=False)

    update, query = _callback_update(f"plan:{target_date.isoformat()}")
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert query.edit_calls[0]["text"] == module.GENERATING_PLAN_MESSAGE
    assert query.edit_calls[-1]["text"] == "PLAN"
    assert context.user_data["plan_screen"] == "cached-plan"


def test_callback_refresh_with_existing_plan_does_not_regenerate(monkeypatch):
    module = _load_module()
    target_date = date.today()
    plan_context = _make_context(module, target_date)
    plan_items = [_make_item(target_date)]

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("PLAN", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached-plan")
    generate_day = Mock(side_effect=AssertionError("refresh must not regenerate when plan already exists"))
    monkeypatch.setattr(module.orchestrator, "generate_day", generate_day, raising=False)

    update, query = _callback_update(f"plan:{target_date.isoformat()}")
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert query.edit_calls[-1]["text"] == "PLAN"
    assert generate_day.call_count == 0
    assert context.user_data["plan_screen"] == "cached-plan"


def test_concurrent_generate_if_missing_starts_only_one_generation(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    empty_context = _make_context(module, target_date, city="")
    persisted_context = _make_context(module, target_date, city="Prague")
    generated_item = _make_item(target_date, city="Prague")

    started = asyncio.Event()
    release = asyncio.Event()
    generation_done = {"value": False}
    generate_calls = []

    def fake_load(_target_date):
        if generation_done["value"]:
            return persisted_context, [generated_item]
        return empty_context, []

    def fake_generate_day(**kwargs):
        generate_calls.append(kwargs)
        return types.SimpleNamespace(date=target_date, city="Prague", publishing_plan=[])

    async def fake_to_thread(func, **kwargs):
        started.set()
        await release.wait()
        generation_done["value"] = True
        return func(**kwargs)

    monkeypatch.setattr(module, "_load_persisted_plan", fake_load)
    monkeypatch.setattr(module.orchestrator, "generate_day", fake_generate_day, raising=False)
    monkeypatch.setattr(module.asyncio, "to_thread", fake_to_thread)

    update, _loading = _message_update()
    status_messages_1 = []
    status_messages_2 = []

    async def first_status(text: str):
        status_messages_1.append(text)

    async def second_status(text: str):
        status_messages_2.append(text)

    async def run_test():
        first = asyncio.create_task(
            module._load_plan_with_generate_if_missing(update, target_date=target_date, status_message=first_status)
        )
        await started.wait()
        second = asyncio.create_task(
            module._load_plan_with_generate_if_missing(update, target_date=target_date, status_message=second_status)
        )
        await asyncio.sleep(0)
        release.set()
        first_result = await first
        second_result = await second
        return first_result, second_result

    first_result, second_result = asyncio.run(run_test())

    assert generate_calls == [{"target_date": target_date}]
    assert first_result[1][0].publication_id == "pub-1"
    assert second_result[1][0].publication_id == "pub-1"
    assert status_messages_1 == [module.GENERATING_PLAN_MESSAGE]
    assert status_messages_2 == [module.WAITING_FOR_GENERATION_MESSAGE]


def test_callback_refresh_ignores_message_not_modified(monkeypatch):
    module = _load_module()
    target_date = date(2026, 3, 20)
    plan_context = _make_context(module, target_date)
    plan_items = [_make_item(target_date)]

    monkeypatch.setattr(module, "_load_persisted_plan", lambda _target_date: (plan_context, plan_items))
    monkeypatch.setattr(module, "_render_plan", lambda _context, _items: ("PLAN", object()))
    monkeypatch.setattr(module, "serialize_context", lambda _context, _items: "cached-plan")
    module.logger.exception = Mock()

    class Query:
        def __init__(self):
            self.data = "plan:2026-03-20"
            self.answer_calls = []
            self.edit_calls = 0
            self.from_user = types.SimpleNamespace(id=600)

        async def answer(self, *_args, **_kwargs):
            self.answer_calls.append((_args, _kwargs))

        async def edit_message_text(self, **_kwargs):
            self.edit_calls += 1
            raise module.BadRequest("Message is not modified")

    query = Query()
    update = types.SimpleNamespace(
        callback_query=query,
        effective_chat=types.SimpleNamespace(id=500),
        effective_user=types.SimpleNamespace(id=600),
    )
    context = types.SimpleNamespace(user_data={})

    asyncio.run(module.callback_nav(update, context))

    assert query.answer_calls == [((), {})]
    assert query.edit_calls == 1
    assert module.logger.exception.call_count == 0


def test_start_button_uses_utf8_runtime():
    module = _load_module()
    assert module.GET_PLAN_BUTTON == "📅 Получить план на сегодня"
