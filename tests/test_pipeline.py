"""Pipeline lifecycle stays inside one business and never invents a reply."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import storage
import tools
import views

SOURCE = {
    "url": "https://example.com/harbor",
    "permitted": True,
    "text": "\n".join([
        "Company: Harborline Studio",
        "Contact: Mina Hart",
        "Email: mina@harborline.example",
        "Segment: interior studio",
        "Country: ID",
        "Fact: published a lobby renovation brief",
    ]),
}


def _call(fn, args):
    return json.loads(fn(args))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        self.business = _call(tools.onboard_business, {
            "name": "Cedarline",
            "offer": "Fixture schedules for lobby stone.",
            "offer_short": "Fixture schedules",
            "default_cta": "Reply if the brief is still open.",
            "research_only": True,
            "mail_mode": "gmail_oauth",
            "target_market": "interior studios",
        })["business"]

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_discovery_dedupes_and_blocks_suppressed_reentry(self):
        first = _call(tools.pipeline_action, {"action": "discover", "sources": [SOURCE]})
        second = _call(tools.pipeline_action, {"action": "discover", "sources": [SOURCE]})
        self.assertTrue(first["saved"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["prospect"]["id"], second["prospect"]["id"])
        self.assertEqual(first["intent"], "not_inferred")
        self.assertFalse(self.business["profile"]["mail"]["token_stored"])
        self.assertFalse(self.business["profile"]["mail"]["gmail_oauth_connected"])
        lead_id = first["prospect"]["id"]
        _call(tools.pipeline_action, {"action": "status", "lead_id": lead_id, "status": "do_not_contact"})
        again = _call(tools.pipeline_action, {"action": "discover", "sources": [SOURCE]})
        self.assertTrue(again["outreach_blocked"])
        draft = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        self.assertEqual(draft["code"], "outreach_blocked")

    def test_smtp_acceptance_is_not_a_reply_and_delete_is_explicit(self):
        found = _call(tools.pipeline_action, {"action": "discover", "sources": [SOURCE]})
        lead_id = found["prospect"]["id"]
        accepted = _call(tools.pipeline_action, {"action": "smtp_accepted", "lead_id": lead_id, "message_id": "<abc@example>"})
        self.assertFalse(accepted["reply_inferred"])
        self.assertEqual(accepted["inbox_delivery"], "not_observed")
        reply = _call(tools.pipeline_action, {"action": "reply", "lead_id": lead_id, "message_id": "<abc@example>"})
        self.assertEqual(reply["code"], "reply_not_observed")
        noted = _call(tools.pipeline_action, {"action": "note", "lead_id": lead_id, "note": "Asked for the brief date."})
        self.assertEqual(noted["prospect"]["note"], "Asked for the brief date.")
        refused = _call(tools.pipeline_action, {"action": "delete", "lead_id": lead_id})
        self.assertEqual(refused["code"], "delete_not_confirmed")
        deleted = _call(tools.pipeline_action, {"action": "delete", "lead_id": lead_id, "confirm_delete": True})
        self.assertTrue(deleted["deleted"])
        listed = _call(tools.pipeline_action, {"action": "list", "query": "Harborline"})
        self.assertEqual(listed["count"], 0)
        other = views.pipeline_change({"action": "send", "lead_id": lead_id})
        self.assertEqual(other["code"], "refused")
        self.assertFalse(other["sent"])

    def test_other_business_cannot_change_the_prospect(self):
        found = _call(tools.pipeline_action, {"action": "discover", "sources": [SOURCE]})
        other = _call(tools.onboard_business, {
            "name": "Other Studio",
            "offer": "Other offer for other work.",
            "offer_short": "Other offer",
            "default_cta": "Ask first.",
        })["business"]
        changed = _call(tools.pipeline_action, {
            "action": "status",
            "business_id": other["id"],
            "lead_id": found["prospect"]["id"],
            "status": "not_interested",
        })
        self.assertEqual(changed["code"], "missing_lead")
        visible = views.pipeline_view(other["id"])
        self.assertEqual(visible["count"], 0)
        home = views.pipeline_view(self.business["id"])
        self.assertEqual(home["count"], 1)
        self.assertFalse(home["send_via_rest"])
