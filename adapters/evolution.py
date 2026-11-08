"""Evolution API adapter stub. Does not call HTTP or read credentials in Phase 1.

Later phases, if enabled, must:
- read SALESPILOT_EVOLUTION_BASE_URL / SALESPILOT_EVOLUTION_API_KEY /
  SALESPILOT_EVOLUTION_INSTANCE only through agent.secret_scope.get_secret
- confirm the instance status is open before sendText
- send one instance to one target; do not fan out
- verify delivery by message id; a pending ack is not sent
- store the provider message id on the draft
"""

from __future__ import annotations

from typing import Any

from .base import BLOCK_REASON, PHASE, SENDING_ENABLED, ChannelAdapter

CREDENTIAL_ENV = (
    "SALESPILOT_EVOLUTION_BASE_URL",
    "SALESPILOT_EVOLUTION_API_KEY",
    "SALESPILOT_EVOLUTION_INSTANCE",
)


class EvolutionAdapter(ChannelAdapter):
    name = "evolution"
    channel = "whatsapp"

    def status(self) -> dict[str, Any]:
        body = super().status()
        body["credential_env"] = list(CREDENTIAL_ENV)
        body["credentials_read"] = False
        body["reason"] = BLOCK_REASON if not SENDING_ENABLED else "ready"
        body["phase"] = PHASE
        return body
