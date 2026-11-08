"""SMTP adapter stub. Does not open a socket or read credentials in Phase 1.

Later phases, if enabled, must:
- read SALESPILOT_SMTP_HOST / SALESPILOT_SMTP_USERNAME / SALESPILOT_SMTP_PASSWORD
  only through agent.secret_scope.get_secret
- never log secret values
- set a stable Message-ID from the draft idempotency key
- treat SMTP accept as handoff, not proof the person read it
"""

from __future__ import annotations

from typing import Any

from .base import BLOCK_REASON, PHASE, SENDING_ENABLED, ChannelAdapter

CREDENTIAL_ENV = (
    "SALESPILOT_SMTP_HOST",
    "SALESPILOT_SMTP_USERNAME",
    "SALESPILOT_SMTP_PASSWORD",
)


def smtp_readiness() -> dict[str, Any]:
    """Report whether Hermes secret scope has SMTP names set. Never returns values."""
    present = {name: False for name in CREDENTIAL_ENV}
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return {
            "checked": True,
            "credentials_read": False,
            "configured": False,
            "present": present,
            "sending_enabled": False,
            "reason": BLOCK_REASON,
        }
    for name in CREDENTIAL_ENV:
        try:
            present[name] = bool(get_secret(name, default=None))
        except Exception:
            present[name] = False
    return {
        "checked": True,
        "credentials_read": True,
        "configured": all(present.values()),
        "present": present,
        "sending_enabled": False,
        "reason": BLOCK_REASON,
    }


class SmtpAdapter(ChannelAdapter):
    name = "smtp"
    channel = "email"

    def status(self) -> dict[str, Any]:
        body = super().status()
        body["credential_env"] = list(CREDENTIAL_ENV)
        body["credentials_read"] = False
        body["reason"] = BLOCK_REASON if not SENDING_ENABLED else "ready"
        body["phase"] = PHASE
        return body
