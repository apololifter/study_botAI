import os
from typing import Any, Dict, List, Optional
from telegram import Bot, Update

class TelegramReceiver:
    """
    Lightweight receiver using getUpdates (polling) intended for short-lived runs.
    Updated to handle Text (including Links) and Documents (PDFs).
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
        Returns user messages as dicts. Handles Text and Documents.
        """
        offset = None if last_update_id is None else last_update_id + 1
        updates: List[Update] = await self.bot.get_updates(offset=offset, limit=limit, timeout=0)

        out: List[Dict[str, Any]] = []
        for u in updates:
            msg = getattr(u, "message", None)
            if not msg:
                continue
            
            chat_id = str(msg.chat_id)
            if allowed_chat_id and chat_id != str(allowed_chat_id):
                continue
            
            # Determine content type
            text = getattr(msg, "text", "") or ""
            document = getattr(msg, "document", None)
            
            # If neither text nor document, skip (unless we want captions from photos later)
            if not text and not document:
                continue

            msg_data = {
                "update_id": u.update_id,
                "date": msg.date.timestamp() if msg.date else None,
                "text": text,
                "chat_id": chat_id,
                "from_id": getattr(getattr(msg, "from_user", None), "id", None),
                "document": None
            }

            if document:
                msg_data["document"] = {
                    "file_id": document.file_id,
                    "file_name": document.file_name,
                    "mime_type": document.mime_type,
                    "file_size": document.file_size
                }
                # Check for caption if text was empty
                if not text and msg.caption:
                    msg_data["text"] = msg.caption

            out.append(msg_data)
            
        return out

    async def download_file_content(self, file_id: str) -> bytes:
        """Downloads a file from Telegram and returns its bytes."""
        new_file = await self.bot.get_file(file_id)
        # download_as_bytearray is deprecated in v20+, use download_to_memory
        from io import BytesIO
        out_buffer = BytesIO()
        await new_file.download_to_memory(out_buffer)
        return out_buffer.getvalue()
