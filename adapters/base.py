"""Channel adapter contract. Sending is a later phase and stays hard-off."""

from __future__ import annotations

from typing import Any

PHASE = 1
SENDING_ENABLED = False
BLOCK_REASON = "sending_disabled_phase_1"


class SendBlocked(Exception):
    def __init__(self, channel: str, reason: str = BLOCK_REASON) -> None:
        super().__init__(reason)
        self.channel = channel
        self.reason = reason


class ChannelAdapter:
    name = "base"
    channel = "none"

    def status(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "channel": self.channel,
            "phase": PHASE,
            "sending_enabled": SENDING_ENABLED,
            "network": False,
            "credentials_read": False,
        }

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        return {
            "ok": False,
            "sent": False,
            "channel": self.channel,
            "adapter": self.name,
            "reason": BLOCK_REASON,
            "phase": PHASE,
        }
