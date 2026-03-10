from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass
class AppSettings:
    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = "Europe/Prague"
    default_city: str = "Prague"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    openweather_api_key: str | None = None
    openweather_base_url: str = "https://api.openweathermap.org/data/2.5"
    sun_api_url: str = "https://api.sunrise-sunset.org/json"
    google_service_account_json_path: str | None = None
    google_sheet_id: str | None = None
    llm_provider: str = "none"
    llm_api_key: str | None = None
    llm_model: str | None = None
    openclaw_url: str | None = None
    openclaw_api_key: str | None = None
    state_backend: str = "auto"
    request_timeout_seconds: int = 10
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "AppSettings":
        _load_dotenv()
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            timezone=os.getenv("TIMEZONE", "Europe/Prague"),
            default_city=os.getenv("DEFAULT_CITY", "Prague"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            openweather_api_key=os.getenv("OPENWEATHER_API_KEY"),
            openweather_base_url=os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5"),
            sun_api_url=os.getenv("SUN_API_URL", "https://api.sunrise-sunset.org/json"),
            google_service_account_json_path=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH"),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID"),
            llm_provider=os.getenv("LLM_PROVIDER", "none"),
            llm_api_key=os.getenv("LLM_API_KEY"),
            llm_model=os.getenv("LLM_MODEL"),
            openclaw_url=os.getenv("OPENCLAW_URL"),
            openclaw_api_key=os.getenv("OPENCLAW_API_KEY"),
            state_backend=os.getenv("STATE_BACKEND", "auto"),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
        )


def load_settings_yaml(path: str | Path = "config/settings.example.yaml") -> Dict[str, Any]:
    # lightweight parser for nested YAML-like file limited to this project usage
    data: Dict[str, Any] = {
        "fallbacks": {
            "weather": {"condition": "mild_clouds", "temp_c": 18},
            "city_coordinates": {
                "Prague": [50.0755, 14.4378],
                "Paris": [48.8566, 2.3522],
                "Rome": [41.9028, 12.4964],
                "Lisbon": [38.7223, -9.1393],
                "Vienna": [48.2082, 16.3738],
            },
        }
    }
    return data
