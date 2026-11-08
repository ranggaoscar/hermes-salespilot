"""Adapters must refuse delivery in Phase 1."""

from __future__ import annotations

import unittest

from adapters import adapter_for
from adapters.base import SENDING_ENABLED


class AdapterTests(unittest.TestCase):
    def test_both_channels_block_without_network_or_secrets(self):
        self.assertFalse(SENDING_ENABLED)
        for channel in ("email", "whatsapp"):
            adapter = adapter_for(channel)
            status = adapter.status()
            result = adapter.send({"to": "nobody@example.invalid", "body": "nope"})
            self.assertFalse(status["network"])
            self.assertFalse(status["credentials_read"])
            self.assertFalse(result["ok"])
            self.assertFalse(result["sent"])
            self.assertEqual(result["reason"], "sending_disabled_phase_1")

    def test_unknown_channel_is_rejected(self):
        with self.assertRaises(ValueError):
            adapter_for("sms")
