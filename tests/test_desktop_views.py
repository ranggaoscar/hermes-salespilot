"""Desktop read API uses persisted rows and never exposes secrets."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import mission
import storage
import tools
import views

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


def _call(fn, args):
    return json.loads(fn(args))


class DesktopViewTests(unittest.TestCase):
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
        _call(mission.mission, {
            "action": "save_dna",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/dna",
            "text": DNA,
            "permitted": True,
        })
        _call(mission.mission, {
            "action": "scan",
            "name": "Lobby radar",
            "business_id": self.business_id,
            "url": "https://example.invalid/page",
            "text": PAGE,
            "permitted": True,
        })

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_views_are_persisted_and_have_no_send_route(self):
        first = views.overview(self.business_id)
        again = views.overview(self.business_id)
        self.assertEqual(first["counts"]["missions"], 1)
        self.assertEqual(again["missions"][0]["id"], first["missions"][0]["id"])
        cards = views.radar(self.business_id)["cards"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["company"], "Harborline Studio")
        self.assertIn("No public contact", cards[0]["unknowns"][0])
        self.assertFalse(views.outreach(self.business_id)["send_via_rest"])
        dna = views.dna(self.business_id)
        self.assertEqual(dna["claims"][0]["confidence"], "sourced")
        self.assertIs(dna["mail"]["password_present"], False)
        self.assertNotIn("smtp_password", json.dumps(dna))
        source = Path("dashboard/plugin_api.py").read_text(encoding="utf-8")
        self.assertNotIn("send", source.lower().split("no send")[0])
        plugin = Path("desktop/plugin.js").read_text(encoding="utf-8")
        self.assertIn("SIDEBAR_NAV_AREA", plugin)
        self.assertIn("ROUTES_AREA", plugin)
        self.assertIn("method: 'POST'", plugin)
        self.assertIn("'/pipeline'", plugin)
        self.assertNotIn("'/send'", plugin)
        self.assertIn("codicon: 'compass'", plugin)
        self.assertIn("Created by ROCK", plugin)
        self.assertNotIn("Nous Research ownership", plugin)
        manifest = Path("plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("name: ROCK", manifest)
        self.assertIn("https://github.com/ranggaoscar", manifest)
