from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.request import Request, urlopen

from virtual_persona.config.settings import AppSettings

logger = logging.getLogger(__name__)


class TelegramDelivery:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def send_message(self, text: str) -> bool:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            logger.warning("Telegram credentials missing; skip sending.")
            return False
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        body = json.dumps({"chat_id": self.settings.telegram_chat_id, "text": text[:4096]}).encode("utf-8")
        req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=self.settings.request_timeout_seconds):
                return True
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return False

    def save_fallback(self, text: str, path: str = "data/outputs/telegram_fallback.md") -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        return output
