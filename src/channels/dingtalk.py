"""DingTalk channel implementation.

Receives messages via HTTP webhook callback, sends responses via
DingTalk session webhook URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from src.channels.base import BaseChannel, IncomingMessage

logger = logging.getLogger(__name__)

# Pattern to strip @bot mention prefix from message text
_AT_BOT_PATTERN = re.compile(r"^@\S+\s*")


class DingTalkChannel(BaseChannel):
    """DingTalk channel: HTTP webhook -> LangGraph run -> session webhook reply."""

    channel = "dingtalk"

    async def start(self) -> None:
        """No persistent connection needed for HTTP webhook mode."""

    async def stop(self) -> None:
        """No cleanup needed for HTTP webhook mode."""

    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """Parse DingTalk robot callback payload into IncomingMessage.

        DingTalk robot callback payload structure:
        {
            "senderStaffId": "...",     # user's staff ID
            "senderNick": "...",         # display name
            "conversationType": "1|2",  # 1=private, 2=group
            "conversationId": "...",
            "sessionWebhook": "https://...",
            "msgtype": "text",
            "text": {"content": "..."},
        }
        """
        user_id = payload.get("senderStaffId", "")
        sender_name = payload.get("senderNick", "")
        conversation_type = payload.get("conversationType", "1")
        conversation_id = payload.get("conversationId", "")
        session_webhook = payload.get("sessionWebhook", "")

        # Extract text content
        text_data = payload.get("text", {})
        content = (text_data.get("content", "") if isinstance(text_data, dict) else "").strip()

        # Strip @bot mention prefix
        content = _AT_BOT_PATTERN.sub("", content).strip()

        return IncomingMessage(
            user_id=user_id,
            tenant_id="",  # Resolved later via DB lookup
            content=content,
            session_id=conversation_id,
            channel=self.channel,
            meta={
                "sender_name": sender_name,
                "conversation_type": conversation_type,
                "conversation_id": conversation_id,
                "session_webhook": session_webhook,
            },
        )

    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message via DingTalk session webhook.

        Args:
            to_handle: The sessionWebhook URL from the incoming message.
            text: Message text to send.
            meta: Optional metadata (unused for basic send).
        """
        if not to_handle:
            logger.warning("DingTalk send skipped: no session webhook URL")
            return

        body = {
            "msgtype": "text",
            "text": {"content": text},
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(to_handle, json=body)
            if resp.status_code != 200:
                logger.error(
                    "DingTalk send failed: %s %s",
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.info("DingTalk send success: %d chars", len(text))
