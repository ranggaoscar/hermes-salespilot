"""Optional channel adapters. Phase 1 keeps every adapter unable to send."""

from .base import ChannelAdapter, SendBlocked
from .evolution import EvolutionAdapter
from .smtp import SmtpAdapter

__all__ = ["ChannelAdapter", "EvolutionAdapter", "SendBlocked", "SmtpAdapter", "adapter_for"]


def adapter_for(channel: str) -> ChannelAdapter:
    key = (channel or "").strip().lower()
    if key == "email":
        return SmtpAdapter()
    if key == "whatsapp":
        return EvolutionAdapter()
    raise ValueError(f"unsupported channel: {channel}")
