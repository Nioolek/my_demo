"""Webhook endpoints for channel callbacks."""

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from src.channels.dingtalk import DingTalkChannel
from src.db.client import execute, fetch_one

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

_dingtalk_channel = DingTalkChannel()


async def _ensure_dingtalk_user(payload: dict[str, Any]) -> str:
    """Look up or create a DingTalk user, return tenant_id.

    Uses senderStaffId as user_id with channel_source='dingtalk'.
    If the user doesn't exist, returns empty string (message will be rejected).
    """
    user_id = payload.get("senderStaffId", "")
    if not user_id:
        return ""

    user = await fetch_one(
        "SELECT tenant_id::text, name FROM users "
        "WHERE id = %s AND channel_source = 'dingtalk'",
        user_id,
    )
    if user:
        return user["tenant_id"]

    return ""


async def _create_agent_run(
    tenant_id: str,
    user_id: str,
    content: str,
    session_id: str,
) -> str:
    """Create a LangGraph run and return the agent's response text.

    Uses the LangGraph SDK to create a wait-mode run.
    """
    from langgraph_sdk import get_client

    client = get_client(url="http://127.0.0.1:2024")

    thread_id = f"{tenant_id}:{user_id}:dingtalk:{session_id}"

    # Ensure thread exists
    try:
        await client.threads.get(thread_id)
    except Exception:
        await client.threads.create(thread_id=thread_id)

    # Create run (wait mode — blocks until complete)
    result = await client.runs.wait(
        thread_id=thread_id,
        assistant_id="store-agent",
        input={
            "messages": [{"role": "user", "content": content}],
        },
        config={
            "configurable": {"tenant_id": tenant_id},
        },
        timeout=120,
    )

    # Extract last AI message from result
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if msg.get("type") == "ai" and msg.get("content"):
            return msg["content"]

    return "I'm sorry, I couldn't generate a response."


async def _send_dingtalk_reply(
    session_webhook: str, text: str
) -> None:
    """Send a reply via DingTalk session webhook."""
    await _dingtalk_channel.send(session_webhook, text)


async def _process_dingtalk_message(payload: dict[str, Any]) -> None:
    """Full pipeline: parse → lookup user → run agent → send reply."""
    msg = _dingtalk_channel.parse_incoming(payload)

    if not msg.user_id:
        logger.warning("DingTalk message with no senderStaffId, ignoring")
        return

    # Look up user's tenant
    tenant_id = await _ensure_dingtalk_user(payload)
    if not tenant_id:
        logger.warning(
            "DingTalk user %s not found in DB, ignoring", msg.user_id
        )
        session_webhook = msg.meta.get("session_webhook", "")
        if session_webhook:
            await _send_dingtalk_reply(
                session_webhook,
                "Sorry, your account is not configured. Please contact your administrator.",
            )
        return

    msg.tenant_id = tenant_id

    # Run agent
    try:
        response_text = await _create_agent_run(
            tenant_id=tenant_id,
            user_id=msg.user_id,
            content=msg.content,
            session_id=msg.session_id,
        )
    except Exception:
        logger.exception("Agent run failed for user %s", msg.user_id)
        response_text = "Sorry, an error occurred while processing your request."

    # Send reply
    session_webhook = msg.meta.get("session_webhook", "")
    if session_webhook:
        await _send_dingtalk_reply(session_webhook, response_text)
    else:
        logger.warning("No session webhook for user %s", msg.user_id)


@router.post("/webhooks/dingtalk")
async def dingtalk_webhook(request: Request):
    """Receive DingTalk robot callback messages.

    ACKs immediately (200), processes asynchronously.
    """
    payload = await request.json()

    # Basic validation
    sender = payload.get("senderStaffId")
    if not sender:
        raise HTTPException(400, "Missing senderStaffId")

    # Process asynchronously — don't block the ACK
    asyncio.create_task(_process_dingtalk_message(payload))

    return {"success": True}
