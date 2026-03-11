from datetime import date

from virtual_persona.services.daily_scheduler import DailySchedulerService


class DummyOrchestrator:
    class Settings:
        timezone = "Europe/Prague"
        default_city = "Prague"

    def __init__(self):
        self.settings = self.Settings()
        self.state = self
        self.context_builder = self
        self.generated = False
        self.sent = False
        self.telegram_delivery_service = self

    def load_cities(self):
        return [{"city": "Paris", "timezone": "Europe/Paris"}]

    def build(self, target_date=None):
        return {"city": "Paris"}

    def generate_day(self, target_date=None, override_city=None):
        self.generated = True
        class P:
            publishing_plan = []
            date = date.today()
            city = "Paris"
        return P()

    def send_daily_plan(self, package, plan_items):
        self.sent = True
        return True


def test_scheduler_skips_when_time_not_matched():
    orchestrator = DummyOrchestrator()
    scheduler = DailySchedulerService(orchestrator, "25:61")

    assert scheduler.run_once() is False
    assert orchestrator.generated is False


def test_resolve_persona_timezone_from_city_table():
    orchestrator = DummyOrchestrator()
    scheduler = DailySchedulerService(orchestrator, "00:00")

    assert scheduler._resolve_persona_timezone("Paris") == "Europe/Paris"
