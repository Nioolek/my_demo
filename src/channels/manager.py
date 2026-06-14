"""ChannelManager: centralized outbound message routing."""

from __future__ import annotations

import logging
from typing import Any

from src.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class ChannelManager:
    """Registry of channels with outbound send routing."""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        """Register a channel instance."""
        self._channels[channel.channel] = channel
        logger.info("Registered channel: %s", channel.channel)

    def get(self, channel_type: str) -> BaseChannel | None:
        """Get a registered channel by type, or None."""
        return self._channels.get(channel_type)

    async def send(
        self,
        channel_type: str,
        to_handle: str,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Route an outbound message to the specified channel.

        Args:
            channel_type: Channel identifier (e.g., "dingtalk").
            to_handle: Routing handle for the channel.
            text: Message text.
            meta: Optional metadata.

        Raises:
            ValueError: If the channel type is not registered.
        """
        channel = self._channels.get(channel_type)
        if not channel:
            raise ValueError(f"Unknown channel: {channel_type}")
        await channel.send(to_handle, text, meta)
