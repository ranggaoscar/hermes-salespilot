"""Desktop write actions: import, qualify, draft, inbox. None can send; each stays inside its brand."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import desk_actions
import setup
import storage
import tools
import views


def _call(fn, args):
    return json.loads(fn(args))


CSV = "Nama Perusahaan,PIC,Email\nPT Sinar Logistik,Budi,budi@sinar.test\nCV Maju,,info@maju.test\nPT Sinar Logistik,Budi,budi@sinar.test\n"
MAPPING = {"Nama Perusahaan": "company", "PIC": "contact_name", "Email": "email"}


class DeskActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        self.biz = _call(tools.onboard_business, {
            "name": "Kinetra Mobility", "offer": "Electric MPV fleets.", "offer_short": "EV fleets",
            "default_cta": "Reply if useful.", "default_country": "ID", "followup_days": 5,
        })["business"]["id"]

    def tearDown(self):
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def _lead(self, business_id, company="PT Armada Hijau"):
        result = _call(tools.qualify_lead, {
            "business_id": business_id, "company": company, "evidence": f"{company} runs a 40-van fleet.",
            "email": "fleet@armada.test", "source_url": "https://example.invalid/armada",
        })
        return result["lead"]["id"]

    def test_import_requires_permission_and_origin(self):
        base = {"csv_text": CSV, "mapping": MAPPING, "business_id": self.biz}
        self.assertEqual(desk_actions.import_csv({**base})["code"], "not_authorized")
        self.assertEqual(desk_actions.import_csv({**base, "authorized": True})["code"], "missing_authorization_note")
        refused = desk_actions.import_csv({**base, "authorized": True, "authorization_note": "crm", "smtp_password": "x"})
        self.assertEqual(refused["code"], "refused")
        self.assertIs(refused["sent"], False)

    def test_import_saves_rows_and_reports_duplicates(self):
        result = desk_actions.import_csv({"csv_text": CSV, "mapping": MAPPING, "business_id": self.biz,
                                          "authorized": True, "authorization_note": "Trade show list", "source": "expo.csv"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["inserted_count"], 2)
        self.assertEqual([e["code"] for e in result["row_errors"]], ["duplicate_in_file"])
        listed = desk_actions.customers(self.biz)
        self.assertEqual({c["company"] for c in listed["customers"]}, {"PT Sinar Logistik", "CV Maju"})
        self.assertTrue(all(c["source"] == "expo.csv" for c in listed["customers"]))

    def test_draft_and_qualify_stay_inside_the_brand(self):
        other = _call(tools.onboard_business, {"name": "Cedarline", "offer": "Fixtures.", "offer_short": "Fixtures",
                                               "default_cta": "Reply."})["business"]["id"]
        lead = self._lead(other)
        for action in (desk_actions.draft, desk_actions.qualify):
            refused = action({"lead_id": lead, "business_id": self.biz})
            self.assertEqual(refused["code"], "lead_not_found")
            self.assertIs(refused["sent"], False)

    def test_draft_subject_does_not_double_the_preposition(self):
        """An offer_short that already names its audience keeps the company out of the subject."""
        import domain

        profile = {"name": "Kinetra Mobility", "offer": "Electric MPV sales for Indonesian businesses",
                   "offer_short": "Electric MPV sales for Indonesian businesses",
                   "default_cta": "Reply if useful."}
        lead = {"company": "PT Armada Hijau", "contact_name": "", "email": "fleet@armada.test",
                "email_valid": True, "decision": "qualified", "evidence": "40-van fleet.",
                "source_url": "https://example.invalid/armada"}

        draft = domain.render_draft(profile, lead, "email")
        self.assertTrue(draft.get("ok"), draft)
        self.assertEqual(draft["subject"], "Kinetra Mobility: Electric MPV sales for Indonesian businesses")

        profile["offer_short"] = "EV fleet supply"
        draft = domain.render_draft(profile, lead, "email")
        self.assertEqual(draft["subject"], "Kinetra Mobility: EV fleet supply for PT Armada Hijau")

    def test_draft_never_sends_and_names_the_slash_command(self):
        lead = self._lead(self.biz)
        result = desk_actions.draft({"lead_id": lead, "business_id": self.biz})
        self.assertIs(result["sent"], False)
        if result.get("ok"):
            self.assertEqual(result["send_command"], f"/salespilot-send {result['draft']['id']}")
            drafts = views.outreach(self.biz)["drafts"]
            self.assertEqual(drafts[0]["lead_id"], lead)
        else:
            self.assertIn(result["code"], {"not_qualified", "missing_email", "outreach_blocked"})
        self.assertEqual(desk_actions.draft({"lead_id": lead, "action": "send"})["code"], "refused")

    def test_inbox_sync_fails_closed_without_imap(self):
        result = desk_actions.inbox_action({"action": "sync", "business_id": self.biz})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "imap_not_configured")
        self.assertEqual(desk_actions.inbox_action({"action": "delete"})["code"], "bad_action")

    def test_editing_a_brand_keeps_its_icp_mail_choice_and_policy(self):
        setup.save({"action": "icp", "business_id": self.biz, "industries": ["logistics"],
                    "locations": ["Jakarta"], "buyer_roles": ["Fleet Manager"]})
        setup.save({"action": "skip_mail", "business_id": self.biz})
        before = setup.status()
        result = setup.save({"action": "business", "business_id": self.biz, "name": "Kinetra Mobility",
                             "products": "Electric MPV sales", "target_market": "Fleets in Jakarta",
                             "website": "https://aletra.test"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["icp"]["industries"], ["logistics"])
        self.assertEqual(result["icp"]["buyer_roles"], ["Fleet Manager"])
        self.assertEqual(result["mail"]["research_only"], before["mail"]["research_only"])
        self.assertEqual(result["business"]["products"], "Electric MPV sales")
        self.assertEqual(result["followup_policy"]["days"], 5)
        with storage.read_only() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0], 1)
            self.assertEqual(storage.get_business(conn, self.biz)["default_country"], "ID")


if __name__ == "__main__":
    unittest.main()
