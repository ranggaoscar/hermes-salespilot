"""Domain rules that must hold without a database."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import domain


PROFILE = {
    "id": "biz_test",
    "name": "Harborline Demo Supply",
    "offer": "Specification support for interior stone.",
    "offer_short": "Stone specification support",
    "default_cta": "Reply if a sample shortlist would help.",
    "default_country": "ID",
    "followup_days": 3,
    "icp": {
        "segments": ["architect", "contractor"],
        "geos": ["demo harbor"],
        "exclude": ["rival stone"],
    },
}


def _lead(**kwargs):
    base = {
        "company": "Northwind Demo Studio",
        "contact_name": "N. Demo",
        "role": "Studio lead",
        "email": "hello@northwind.example.invalid",
        "phone": "08120000111",
        "segment": "architect",
        "country": "Demo Harbor",
        "source_url": "https://example.invalid/northwind",
        "evidence": "Publishes a studio contact page.",
        "unknowns": [],
    }
    base.update(kwargs)
    return base


class PhoneTests(unittest.TestCase):
    def test_indonesia_trunk_zero(self):
        phone = domain.normalize_phone("08120000111", "ID")
        self.assertEqual(phone["digits"], "628120000111")
        self.assertTrue(phone["valid"])
        self.assertFalse(phone["registered"])

    def test_indonesia_rejects_short_and_duplicated_trunk(self):
        self.assertFalse(domain.normalize_phone("62812", "ID")["valid"])
        self.assertFalse(domain.normalize_phone("6208120000111", "ID")["valid"])

    def test_fourteen_digit_exception(self):
        self.assertTrue(domain.normalize_phone("62895123456789", "ID")["valid"])
        self.assertFalse(domain.normalize_phone("62811123456789", "ID")["valid"])

    def test_generic_country_uses_e164_length(self):
        self.assertTrue(domain.normalize_phone("+1 202 555 0143", "US")["valid"])
        self.assertFalse(domain.normalize_phone("123", "US")["valid"])


class QualifyTests(unittest.TestCase):
    def test_qualified_path(self):
        result = domain.qualify(PROFILE, _lead())
        self.assertEqual(result["decision"], "qualified")
        self.assertGreaterEqual(result["score"], 70)
        self.assertIn("phone_format_only_not_registration", result["reasons"])

    def test_hold_when_contact_and_source_missing(self):
        result = domain.qualify(PROFILE, _lead(email="", phone="", source_url="", evidence="Name only."))
        self.assertEqual(result["decision"], "hold")
        self.assertFalse(result["gates"]["contact"])

    def test_reject_excluded_competitor(self):
        result = domain.qualify(PROFILE, _lead(company="Rival Stone Demo Supply", segment="rival stone"))
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(result["score"], 0)

    def test_does_not_invent_missing_email(self):
        result = domain.qualify(PROFILE, _lead(email=""))
        self.assertEqual(result["email"]["value"], "")
        self.assertTrue(result["phone"]["valid"])


class DraftTests(unittest.TestCase):
    def test_draft_refuses_hold_and_keeps_one_cta(self):
        held = {**_lead(), "id": "led_hold", "decision": "hold"}
        refused = domain.render_draft(PROFILE, held, "email")
        self.assertFalse(refused["ok"])
        qualified = {
            **_lead(),
            "id": "led_ok",
            "decision": "qualified",
            "email_valid": True,
            "phone_valid": True,
            "phone": "628120000111",
        }
        draft = domain.render_draft(PROFILE, qualified, "whatsapp")
        self.assertTrue(draft["ok"])
        self.assertTrue(draft["send_blocked"])
        self.assertFalse(draft["sent"])
        self.assertEqual(draft["body"].count("Reply if a sample shortlist would help."), 1)
        again = domain.render_draft(PROFILE, qualified, "whatsapp")
        self.assertEqual(draft["idempotency_key"], again["idempotency_key"])

    def test_plan_never_recommends_send(self):
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        lead = {"id": "led_ok", "company": "Northwind", "decision": "qualified", "updated_at": "2026-11-05T00:00:00Z"}
        planned = domain.plan_one(lead, [], [], now=now, cadence_days=3)
        self.assertEqual(planned["action"], "draft_outreach")
        self.assertFalse(planned["send"])
        approved = domain.plan_one(
            lead,
            [{"id": "dft_1", "lead_id": "led_ok", "created_at": "2026-11-05T01:00:00Z"}],
            [{"draft_id": "dft_1", "status": "approved", "updated_at": "2026-11-05T02:00:00Z"}],
            now=now,
            cadence_days=3,
        )
        self.assertEqual(approved["action"], "hold_approved_unsent")
        self.assertNotIn(approved["action"], {"send", "send_email", "send_whatsapp"})
