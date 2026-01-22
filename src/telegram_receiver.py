import os
from typing import Any, Dict, List, Optional
from telegram import Bot, Update

class TelegramReceiver:
    """
    Lightweight receiver using getUpdates (polling) intended for short-lived runs
    (e.g., GitHub Actions cron).
    """

    def __init__(self):
        self.token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM credentials not found")
        self.bot = Bot(token=self.token)

    async def get_new_messages(
        self,
        last_update_id: Optional[int],
        allowed_chat_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Returns user text messages as dicts:
          { "update_id": int, "date": int, "text": str, "chat_id": str, "from_id": int }
        """
        offset = None if last_update_id is None else last_update_id + 1
        # get_updates is an async method in python-telegram-bot v20+
        updates: List[Update] = await self.bot.get_updates(offset=offset, limit=limit, timeout=0)

        out: List[Dict[str, Any]] = []
        for u in updates:
            msg = getattr(u, "message", None)
            if not msg:
                continue
            if not getattr(msg, "text", None):
                continue
            chat_id = str(msg.chat_id)
            if allowed_chat_id and chat_id != str(allowed_chat_id):
                continue
            out.append(
                {
                    "update_id": u.update_id,
                    "date": msg.date.timestamp() if msg.date else None,
                    "text": msg.text,
                    "chat_id": chat_id,
                    "from_id": getattr(getattr(msg, "from_user", None), "id", None),
                }
            )
        return out
