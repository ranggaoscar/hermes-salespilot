"""Handler and storage tests. Uses a temp data dir, never the operator profile."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import storage
import tools
from schemas import TOOL_NAMES


def _call(fn, args):
    return json.loads(fn(args))


class ToolFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_manifest_names_match_schemas(self):
        text = Path("plugin.yaml").read_text(encoding="utf-8")
        for name in TOOL_NAMES:
            self.assertIn(f"- {name}", text)

    def test_seed_is_idempotent_and_synthetic(self):
        first = _call(tools.import_customers, {"seed_demo": True})
        self.assertTrue(first["ok"])
        self.assertTrue(first["synthetic"])
        self.assertFalse(first["sending_enabled"])
        self.assertEqual(first["customers"]["inserted_count"], 3)
        decisions = {item["company"]: item["decision"] for item in first["prospects"]}
        self.assertEqual(decisions["Northwind Demo Studio"], "qualified")
        self.assertEqual(decisions["Masked Pier Demo Co"], "hold")
        self.assertEqual(decisions["Rival Stone Demo Supply"], "reject")
        second = _call(tools.import_customers, {"seed_demo": True})
        self.assertEqual(second["customers"]["inserted_count"], 0)
        self.assertEqual(second["customers"]["skipped_count"], 3)

    def test_manual_import_rejects_real_records(self):
        _call(tools.import_customers, {"seed_demo": True})
        blocked = _call(tools.import_customers, {
            "source": "unit-test",
            "records": [{"company": "Real Co", "synthetic": False, "email": "a@example.invalid"}],
        })
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["code"], "not_authorized")

    def test_draft_approval_and_report_never_send(self):
        seeded = _call(tools.import_customers, {"seed_demo": True})
        lead_id = next(item["id"] for item in seeded["prospects"] if item["decision"] == "qualified")
        draft = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        self.assertTrue(draft["ok"])
        self.assertFalse(draft["sent"])
        self.assertEqual(draft["delivery"]["reason"], "sending_disabled_phase_1")
        again = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        self.assertTrue(again["reused"])
        self.assertEqual(again["draft"]["id"], draft["draft"]["id"])
        approval = _call(tools.request_approval, {
            "draft_id": draft["draft"]["id"],
            "decision": "approve",
            "actor": "tester",
            "note": "ledger only",
            "human_confirmed": True,
        })
        self.assertEqual(approval["code"], "host_approval_unavailable")
        self.assertFalse(approval["sent"])
        followups = _call(tools.plan_followups, {})
        self.assertTrue(all(item["send"] is False for item in followups["followups"]))
        self.assertNotIn("send", {item["action"] for item in followups["followups"]})
        report = _call(tools.report, {"section": "summary"})
        self.assertGreaterEqual(report["summary"]["customers"], 3)
        self.assertGreaterEqual(report["summary"]["drafts"], 1)
        self.assertFalse(report["sending_enabled"])
        self.assertEqual(report["summary"]["phase"], 2)

    def test_research_keeps_claim_classes_separate(self):
        _call(tools.import_customers, {"seed_demo": True})
        saved = _call(tools.research_opportunity, {
            "title": "Lobby package",
            "verified": [{"claim": "Public page lists a lobby fit-out.", "source": "https://example.invalid/lumen"}],
            "assumptions": ["They may need samples this quarter."],
            "unknowns": ["Decision maker"],
            "fit": "unknown",
            "next_question": "Who specifies the lobby stone?",
        })
        self.assertTrue(saved["ok"])
        self.assertFalse(saved["fetched"])
        self.assertEqual(saved["opportunity"]["verified"][0]["source"], "https://example.invalid/lumen")
        empty = _call(tools.research_opportunity, {"title": "Empty"})
        self.assertFalse(empty["ok"])

    def test_hold_cannot_be_drafted(self):
        seeded = _call(tools.import_customers, {"seed_demo": True})
        lead_id = next(item["id"] for item in seeded["prospects"] if item["decision"] == "hold")
        draft = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        self.assertFalse(draft["ok"])
        self.assertEqual(draft["code"], "not_qualified")
