"""BaseChannel ABC and message routing utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IncomingMessage:
    """Parsed incoming message from any channel."""

    user_id: str
    tenant_id: str
    content: str
    session_id: str = ""
    channel: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def build_thread_id(
    tenant_id: str, user_id: str, channel: str, session_id: str
) -> str:
    """Build a globally unique thread ID encoding routing info."""
    return f"{tenant_id}:{user_id}:{channel}:{session_id}"


def parse_thread_id(thread_id: str) -> tuple[str, str, str, str]:
    """Parse a thread ID into (tenant_id, user_id, channel, session_id).

    Raises:
        ValueError: If the thread_id format is invalid.
    """
    parts = thread_id.split(":", 3)
    if len(parts) != 4:
        raise ValueError(
            f"Invalid thread_id format: expected 4 colon-separated parts, "
            f"got {len(parts)}"
        )
    return parts[0], parts[1], parts[2], parts[3]


class BaseChannel(ABC):
    """Abstract base class for all channels.

    Subclasses must implement: start, stop, send, parse_incoming.
    """

    channel: str

    @abstractmethod
    async def start(self) -> None:
        """Initialize the channel (connect, register handlers)."""

    @abstractmethod
    async def stop(self) -> None:
        """Shut down the channel."""

    @abstractmethod
    async def send(
        self,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message to a user/conversation.

        Args:
            to_handle: Routing handle (e.g., session webhook URL).
            text: Message text to send.
            meta: Optional metadata (source, run_id, etc.).
        """

    @abstractmethod
    def parse_incoming(self, payload: dict[str, Any]) -> IncomingMessage:
        """Parse a raw channel payload into an IncomingMessage.

        Args:
            payload: Raw dict from the channel's webhook/callback.

        Returns:
            Parsed IncomingMessage.
        """
