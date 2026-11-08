"""Mission graph tests. Synthetic companies only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import mission
import storage
import tools

DNA = """
Differentiator: schedules stone before the architect locks the lobby
Offer: fixture schedules
Segment: interior studio
"""

PAGE = """
Company: Harborline Studio
Date: 2026-03-12
Signal: published a lobby renovation brief
Offer: fixture schedules
"""

INVENTED = """
Company: Quiet Harbor
Signal: they will probably buy stone soon
"""


def _call(fn, args):
    return json.loads(fn(args))


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        onboard = _call(tools.onboard_business, {
            "authorized": True,
            "authorization_note": "fixture",
            "name": "Cedarline Fixture Studio",
            "offer": "Fixture schedules.",
            "offer_short": "Fixture schedules",
            "default_cta": "Reply if useful.",
            "default_country": "ID",
        })
        self.business_id = onboard["business"]["id"]

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_quoted_mission_resumes_and_does_not_invent(self):
        saved = _call(mission.mission, {
            "action": "save_dna",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/dna",
            "text": DNA,
            "permitted": True,
        })
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["dna"][0]["offer"], "fixture schedules")
        self.assertFalse(saved["sent"])
        scanned = _call(mission.mission, {
            "action": "scan",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/page",
            "text": PAGE,
            "permitted": True,
        })
        self.assertEqual(len(scanned["cards"]), 1)
        card = scanned["cards"][0]
        self.assertEqual(card["company"], "Harborline Studio")
        self.assertEqual(card["offer_fit"], "mapped")
        self.assertEqual(card["intent"], "not_inferred")
        self.assertIsNone(card["contact"])
        self.assertFalse(card["send"])
        again = _call(mission.mission, {
            "action": "scan",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/page",
            "text": PAGE,
            "permitted": True,
        })
        self.assertTrue(again["signals"][0]["reused"])
        self.assertEqual(len(again["signals"]), 1)
        empty = _call(mission.mission, {
            "action": "scan",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/empty",
            "text": INVENTED,
            "permitted": True,
        })
        self.assertEqual(empty["cards"][0]["company"], "Harborline Studio")
        self.assertFalse(any(card["company"] == "Quiet Harbor" for card in empty["cards"]))
        self.assertEqual(empty["new_signals"], 0)
        resumed = _call(mission.mission, {
            "action": "resume",
            "name": "Lobby radar",
            "business_id": self.business_id,
        })
        self.assertEqual(resumed["mission_id"], saved["mission_id"])
        self.assertEqual(resumed["cards"][0]["why"], "published a lobby renovation brief")
        self.assertFalse(resumed["auto_send"])
