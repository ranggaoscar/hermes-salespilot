"""ICP configuration: structured fields, ambiguity handling, and the Settings save path."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import domain
import setup
import storage

LEAD = {
    "company": "Palm Court Demo Villas",
    "role": "Fleet Manager",
    "email": "wayan.sudiarta@palmcourt.example",
    "country": "Bali",
    "segment": "hospitality",
    "source_url": "https://palmcourt.example/contact/",
    "evidence": "Jl. Demo Raya 1, Kuta, Badung, Bali 80361, Indonesia",
}

STRUCTURED = {
    "industries": ["logistics", "hospitality"],
    "locations": ["Jakarta", "Bali"],
    "buyer_roles": ["Fleet Manager", "Procurement"],
}


class NormalizeIcpTest(unittest.TestCase):
    def test_structured_icp_is_configured(self):
        result = domain.normalize_icp(STRUCTURED)
        self.assertEqual(result["status"], "configured")
        self.assertEqual(result["industries"], ["logistics", "hospitality"])
        self.assertEqual(result["locations"], ["Jakarta", "Bali"])
        self.assertEqual(result["buyer_roles"], ["Fleet Manager", "Procurement"])
        self.assertEqual(result["issues"], [])

    def test_legacy_sentence_needs_configuration(self):
        legacy = {"segments": ["Corporate fleet managers in Jakarta and Bali"], "geos": []}
        result = domain.normalize_icp(legacy)
        self.assertEqual(result["status"], "needs_configuration")
        self.assertTrue(any("buyer_role" in issue for issue in result["issues"]))

    def test_empty_icp_is_missing(self):
        self.assertEqual(domain.normalize_icp({})["status"], "missing")
        self.assertEqual(domain.normalize_icp(None)["status"], "missing")

    def test_role_inside_industry_is_flagged(self):
        result = domain.normalize_icp({"industries": ["fleet manager"], "locations": ["Bali"]})
        self.assertEqual(result["status"], "needs_configuration")


class CompanyFitWithIcpTest(unittest.TestCase):
    def test_needs_configuration_is_unproven_not_outside(self):
        profile = {"icp": {"segments": ["Corporate fleet managers in Jakarta and Bali"]}}
        result = domain.qualify(profile, LEAD)
        self.assertEqual(result["company_fit"]["status"], "unproven")
        self.assertEqual(result["company_fit"]["reason"], "icp_needs_configuration")
        self.assertEqual(result["stage"], "discovered", "an unusable ICP must not qualify or reject")

    def test_configured_icp_can_reject_a_company_as_outside(self):
        profile = {"icp": {**STRUCTURED, "industries": ["mining"]}}
        result = domain.qualify(profile, LEAD)
        self.assertEqual(result["company_fit"]["status"], "outside_icp")

    def test_configured_icp_matches(self):
        result = domain.qualify({"icp": STRUCTURED}, LEAD)
        self.assertEqual(result["company_fit"]["status"], "fit")
        self.assertEqual(result["stage"], "qualified_company")

    def test_missing_icp_is_unproven(self):
        result = domain.qualify({"icp": {}}, LEAD)
        self.assertEqual(result["company_fit"]["status"], "unproven")
        self.assertIn("icp_not_defined", result["reasons"])


class SettingsIcpSaveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        with storage.unit_of_work() as conn:
            self.business = storage.save_business(conn, {
                "name": "Kinetra Mobility", "offer": "Electric MPV fleet sales",
                "offer_short": "Electric MPV fleet", "default_cta": "Reply if relevant.",
                "icp": {"segments": ["Corporate fleet managers in Jakarta and Bali"], "geos": []},
            })

    def test_status_reports_needs_configuration_for_legacy(self):
        state = setup.status()
        self.assertEqual(state["icp"]["status"], "needs_configuration")
        self.assertTrue(state["icp"]["issues"])

    def test_save_splits_fields_and_persists(self):
        result = setup.save({
            "action": "icp",
            "industries": "logistics, hospitality",
            "locations": "Jakarta, Bali",
            "buyer_roles": "Fleet Manager, Procurement",
        })
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["icp"]["status"], "configured")
        with storage.unit_of_work() as conn:
            stored = storage.get_business(conn, self.business["id"])["icp"]
        self.assertEqual(stored["industries"], ["logistics", "hospitality"])
        self.assertEqual(stored["locations"], ["Jakarta", "Bali"])
        self.assertEqual(stored["buyer_roles"], ["Fleet Manager", "Procurement"])

    def test_save_refuses_ambiguous_single_field(self):
        result = setup.save({"action": "icp", "industries": "Corporate fleet managers in Jakarta and Bali"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "icp_ambiguous")
        self.assertTrue(result["issues"])

    def test_save_refuses_empty(self):
        result = setup.save({"action": "icp", "industries": "", "locations": "", "buyer_roles": ""})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "missing_icp")

    def test_save_never_accepts_secrets(self):
        result = setup.save({"action": "icp", "industries": "logistics", "password": "hunter2"})
        self.assertFalse(result["ok"])
        self.assertNotIn("hunter2", str(result))


if __name__ == "__main__":
    unittest.main()
