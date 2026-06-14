"""Cron webhook callback: receives run completions from LangGraph and routes to channels."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from src.channels.base import parse_thread_id
from src.channels.manager import ChannelManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cron-callback"])

_channel_manager = ChannelManager()


def _get_last_ai_message(payload: dict[str, Any]) -> str:
    """Extract the last AI message from cron callback payload outputs."""
    outputs = payload.get("outputs", {})
    messages = outputs.get("messages", [])
    for msg in reversed(messages):
        if msg.get("type") == "ai" and msg.get("content"):
            return msg["content"]
    return "Cron job completed."


@router.post("/webhooks/internal/cron-callback")
async def cron_callback(request: Request):
    """Receive LangGraph cron run completion callbacks.

    Parses the thread_id to extract routing info, extracts the agent's
    final response, and routes it to the correct channel via ChannelManager.
    """
    payload = await request.json()

    thread_id = payload.get("thread_id")
    if not thread_id:
        raise HTTPException(400, "Missing thread_id")

    # Parse routing info from thread_id
    try:
        tenant_id, user_id, channel, session_id = parse_thread_id(thread_id)
    except ValueError:
        logger.warning("Invalid thread_id in cron callback: %s", thread_id)
        raise HTTPException(400, "Invalid thread_id format")

    # Extract agent's response
    response_text = _get_last_ai_message(payload)

    # Route to channel
    try:
        await _channel_manager.send(
            channel_type=channel,
            to_handle=user_id,
            text=response_text,
            meta={"source": "cron", "run_id": payload.get("run_id")},
        )
    except ValueError:
        logger.warning("Unknown channel '%s' in cron callback", channel)

    logger.info(
        "Cron callback processed: tenant=%s user=%s channel=%s run=%s",
        tenant_id, user_id, channel, payload.get("run_id"),
    )
    return {"success": True}
