"""Setup wizard rejects secrets and does not invent prospects."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import setup
import storage
import tools


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)

    def test_password_is_refused_and_not_stored(self):
        result = setup.save({"action": "business", "name": "Stone Co", "products": "Slabs", "target_market": "Villa builders", "password": "secret"})
        self.assertEqual(result["code"], "secret_refused")
        self.assertFalse(result["sent"])
        text = Path(self.tmp.name, "salespilot.db").read_bytes() if Path(self.tmp.name, "salespilot.db").exists() else b""
        self.assertNotIn(b"secret", text)

    def test_wizard_resumes_after_business_and_skip(self):
        saved = setup.save({"action": "business", "name": "Stone Co", "website": "https://example.com", "products": "Stone slabs", "target_market": "Bali villa builders"})
        self.assertTrue(saved["ok"])
        self.assertEqual(saved["step"], 2)
        self.assertFalse(saved["gmail_oauth"]["available"])
        skipped = setup.save({"action": "skip_mail", "business_id": saved["business_id"]})
        self.assertEqual(skipped["step"], 3)
        self.assertTrue(skipped["mail"]["research_only"])
        again = setup.status()
        self.assertEqual(again["business"]["name"], "Stone Co")
        self.assertEqual(again["suggestions"][0]["source"], "operator_target_market")

    def test_empty_search_creates_no_prospect(self):
        saved = setup.save({"action": "business", "name": "Stone Co", "products": "Stone slabs", "target_market": "Villa builders"})
        setup.save({"action": "skip_mail", "business_id": saved["business_id"]})
        setup.save({"action": "segments", "business_id": saved["business_id"], "segments": ["Villa builders"]})
        original = tools._hermes_search
        tools._hermes_search = lambda query: {"ok": False, "code": "search_unavailable", "results": [], "urls": [], "fabricated": False}
        self.addCleanup(setattr, tools, "_hermes_search", original)
        result = setup.discover({"business_id": saved["business_id"]})
        self.assertEqual(result["discovery"]["prospects"], [])
        self.assertFalse(result["fabricated"])
        with storage.read_only() as conn:
            count = conn.execute("select count(*) from leads").fetchone()[0]
        self.assertEqual(count, 0)

    def test_plugin_api_has_no_send_route(self):
        from dashboard.plugin_api import router
        paths = {route.path for route in router.routes}
        self.assertIn("/setup", paths)
        self.assertNotIn("/send", paths)
        self.assertNotIn("/salespilot-send", paths)
