"""Phase 2 workflow: authorized site text, CSV, grounded research, no send."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import storage
import tools

ROOT = Path(__file__).resolve().parents[1]
SITE = (ROOT / "data" / "phase2" / "site.md").read_text(encoding="utf-8")
CSV = (ROOT / "data" / "phase2" / "customers.csv").read_text(encoding="utf-8")
PROSPECTS = json.loads((ROOT / "data" / "phase2" / "prospects.json").read_text(encoding="utf-8"))
MAPPING = {
    "Company": "company",
    "Contact": "contact_name",
    "Email": "email",
    "Phone": "phone",
    "Segment": "segment",
    "Notes": "notes",
}


def _call(fn, args):
    return json.loads(fn(args))


class Phase2WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "profile-a"
        storage.set_data_dir(self.data)

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def _onboard(self):
        return _call(tools.onboard_business, {
            "authorized": True,
            "authorization_note": "operator supplied fictional page text",
            "default_cta": "Reply if a one-page fixture shortlist would help.",
            "default_country": "ID",
            "followup_days": 3,
            "sources": [{
                "url": "https://example.invalid/cedarline",
                "text": SITE,
                "permitted": True,
            }],
        })

    def test_untrusted_page_cannot_enable_sending_or_invent_offer(self):
        refused = _call(tools.onboard_business, {
            "sources": [{"url": "https://example.invalid/cedarline", "text": SITE, "permitted": True}],
        })
        self.assertEqual(refused["code"], "not_authorized")
        onboarded = self._onboard()
        self.assertTrue(onboarded["ok"])
        self.assertFalse(onboarded["fetched"])
        self.assertFalse(onboarded["sending_enabled"])
        self.assertTrue(onboarded["ignored_instructions"])
        profile = onboarded["business"]["profile"]
        blob = json.dumps(profile)
        self.assertNotIn("enable sending", blob.lower())
        self.assertIn("Walnut sample board", json.dumps(profile["products"]))
        self.assertEqual(onboarded["business"]["name"], "Cedarline Fixture Studio")
        self.assertTrue(onboarded["business"]["citations"])

    def test_csv_authorization_dedupe_and_invalid_rows(self):
        self._onboard()
        blocked = _call(tools.import_customers, {"csv_text": CSV, "mapping": MAPPING})
        self.assertEqual(blocked["code"], "not_authorized")
        first = _call(tools.import_customers, {
            "csv_text": CSV,
            "mapping": MAPPING,
            "authorized": True,
            "authorization_note": "fictional batch",
            "source": "phase2-fixture-csv",
            "synthetic": True,
        })
        self.assertTrue(first["ok"])
        self.assertEqual(first["inserted_count"], 11)
        self.assertEqual({item["code"] for item in first["row_errors"]}, {"duplicate_in_file", "spreadsheet_formula"})
        self.assertTrue(any(item.get("email_reason") == "invalid_format" for item in first["warnings"]))
        second = _call(tools.import_customers, {
            "csv_text": CSV,
            "mapping": MAPPING,
            "authorized": True,
            "authorization_note": "fictional batch",
            "source": "phase2-fixture-csv",
            "synthetic": True,
        })
        self.assertEqual(second["inserted_count"], 0)
        self.assertEqual(second["skipped_count"], 11)
        self.assertEqual(first["skipped"], [])

    def test_full_pipeline_persists_and_stays_isolated(self):
        onboarded = self._onboard()
        business_id = onboarded["business"]["id"]
        imported = _call(tools.import_customers, {
            "csv_text": CSV,
            "mapping": MAPPING,
            "authorized": True,
            "authorization_note": "fictional batch",
            "source": "phase2-fixture-csv",
            "synthetic": True,
            "business_id": business_id,
        })
        self.assertGreaterEqual(imported["inserted_count"], 10)
        qualified = []
        for prospect in PROSPECTS:
            researched = _call(tools.research_opportunity, {
                "business_id": business_id,
                "title": prospect["url"].rsplit("/", 1)[-1],
                "sources": [{
                    "url": prospect["url"],
                    "text": prospect["text"],
                    "permitted": True,
                }],
            })
            self.assertTrue(researched["ok"], researched)
            self.assertTrue(researched["grounded"])
            self.assertFalse(researched["fetched"])
            self.assertIn("breakdown", researched["confidence"])
            scored = _call(tools.qualify_lead, {"lead_id": researched["lead"]["id"], "business_id": business_id})
            self.assertTrue(scored["ok"])
            qualified.append(scored["lead"])
        decisions = {item["company"]: item["decision"] for item in qualified}
        self.assertEqual(decisions["Northlamp Demo Studio"], "qualified")
        self.assertEqual(decisions["Harbor Desk Demo Co"], "qualified")
        self.assertEqual(decisions["Lumen Room Demo Build"], "qualified")
        self.assertEqual(decisions["Masked Pier Demo Co"], "hold")
        self.assertGreaterEqual(sum(item["decision"] == "qualified" for item in qualified), 3)
        invented = _call(tools.qualify_lead, {
            "lead_id": next(item["id"] for item in qualified if item["decision"] == "qualified"),
            "evidence": "They promised a signed contract yesterday.",
        })
        self.assertEqual(invented["code"], "evidence_not_in_source")
        drafts = []
        for lead in qualified:
            if lead["decision"] != "qualified":
                continue
            draft = _call(tools.draft_outreach, {"lead_id": lead["id"], "channel": "email"})
            self.assertTrue(draft["ok"])
            self.assertIn(lead["evidence"][:40], draft["draft"]["body"])
            self.assertFalse(draft["sent"])
            self.assertEqual(draft["delivery"]["reason"], "sending_disabled_phase_1")
            drafts.append(draft["draft"])
        self.assertGreaterEqual(len(drafts), 3)
        wrong = _call(tools.request_approval, {
            "draft_id": drafts[0]["id"],
            "decision": "approve",
            "business_id": "biz_other",
            "actor": "tester",
        })
        self.assertEqual(wrong["code"], "scope_mismatch")
        approval = _call(tools.request_approval, {
            "draft_id": drafts[0]["id"],
            "decision": "approve",
            "lead_id": drafts[0]["lead_id"],
            "actor": "tester",
            "note": "ledger only",
            "human_confirmed": True,
        })
        self.assertEqual(approval["code"], "host_approval_unavailable")
        self.assertFalse(approval["sent"])
        planned = _call(tools.plan_followups, {"business_id": business_id})
        self.assertTrue(planned["ok"])
        self.assertTrue(all(item.get("scheduled_for") for item in planned["followups"]))
        self.assertTrue(all(item["send"] is False for item in planned["followups"]))
        report = _call(tools.report, {"business_id": business_id, "section": "summary"})
        self.assertGreaterEqual(report["summary"]["customers"], 10)
        self.assertGreaterEqual(report["summary"]["by_decision"].get("qualified", 0), 3)
        self.assertTrue(report["next_actions"])
        self.assertTrue(any(item.get("evidence") for item in report["leads"]))
        self.assertFalse(report["sending_enabled"])
        with storage.unit_of_work() as conn:
            customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertGreaterEqual(customers, 10)
        self.assertGreater(events, 0)
        other = Path(self.tmp.name) / "profile-b"
        storage.set_data_dir(other)
        leaked = _call(tools.report, {})
        self.assertEqual(leaked["code"], "missing_business")
        storage.set_data_dir(self.data)
        again = _call(tools.report, {"business_id": business_id})
        self.assertEqual(again["summary"]["customers"], report["summary"]["customers"])
