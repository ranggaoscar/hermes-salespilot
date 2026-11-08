"""Lead quality gate: company fit and recipient readiness are separate axes.

A hotel that only publishes reservation@ is still a matching company; it is simply not addressable
until someone with a fleet or procurement role is on file. Nothing here sends or opens a mailbox.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import domain
import pipeline
import storage

ALETRA_DNA = {
    "icp": {
        "industries": ["logistics", "logistik", "freight forwarding", "hospitality", "hotel", "resort"],
        "geos": ["Jakarta", "Bali", "Bandung"],
        "roles": ["Director", "Fleet Manager", "General Manager", "Owner", "Procurement"],
        "exclude": ["competitor motors"],
    },
    "business_dna": {"summary": "Electric MPV fleet sales for Indonesian operators"},
}

BASE_LEAD = {
    "company": "Palm Court Demo Villas",
    "role": "Fleet Manager",
    "email": "wayan.sudiarta@palmcourt.example",
    "country": "Bali",
    "segment": "hospitality",
    "source_url": "https://palmcourt.example/contact/",
    "evidence": "Jl. Demo Raya 1, Kuta, Badung, Bali 80361, Indonesia",
}


class RecipientProfileTest(unittest.TestCase):
    def test_role_mailboxes_are_not_people(self):
        for address in (
            "reservation@quiethotel.example",
            "cs@besttrans.example",
            "info@example.test",
            "sales@example.test",
            "commercial@cendanawati.example",
        ):
            with self.subTest(address=address):
                recipient = domain.recipient_profile(address)
                self.assertEqual(recipient["kind"], "role", recipient)
                self.assertTrue(recipient["role"])
                self.assertEqual(recipient["deliverability"], "unverified")

    def test_named_mailbox_is_a_person(self):
        person = domain.recipient_profile("wayan.sudiarta@palmcourt.example")
        self.assertEqual(person["kind"], "person")
        self.assertEqual(person["deliverability_reason"], "syntax_only_no_domain_or_mailbox_check")

    def test_freemail_is_not_a_corporate_buyer(self):
        free = domain.recipient_profile("demo.prospect@gmail.com")
        self.assertEqual(free["kind"], "freemail")
        self.assertTrue(free["freemail"])

    def test_invalid_and_missing_are_explicit(self):
        self.assertEqual(domain.recipient_profile("not-an-email")["kind"], "invalid")
        self.assertEqual(domain.recipient_profile("")["kind"], "missing")


class RecipientReadinessTest(unittest.TestCase):
    def test_generic_desks_are_not_decision_makers(self):
        for address in (
            "reservation@quiethotel.example",
            "cs@besttrans.example",
            "info@example.test",
            "demo.prospect@gmail.com",
        ):
            with self.subTest(address=address):
                readiness = domain.recipient_readiness(address, "")
                self.assertEqual(readiness["status"], "role_generic", readiness)
                self.assertFalse(readiness["buyer_role"])

    def test_procurement_and_partnership_desks_are_business_contacts(self):
        for address in (
            "procurement@example.test",
            "purchasing@example.test",
            "partnership@example.test",
            "fleet@example.test",
        ):
            with self.subTest(address=address):
                readiness = domain.recipient_readiness(address, "")
                self.assertEqual(readiness["status"], "business_contact", readiness)
                self.assertTrue(readiness["requires_review"])

    def test_named_person_with_buyer_title_is_decision_maker(self):
        readiness = domain.recipient_readiness("wayan.sudiarta@palmcourt.example", "Fleet Manager")
        self.assertEqual(readiness["status"], "decision_maker")
        self.assertFalse(readiness["requires_review"])

    def test_named_person_without_title_needs_review(self):
        readiness = domain.recipient_readiness("wayan.sudiarta@palmcourt.example", "")
        self.assertEqual(readiness["status"], "person_unknown_role")
        self.assertTrue(readiness["requires_review"])

    def test_deliverability_is_never_claimed(self):
        readiness = domain.recipient_readiness("procurement@example.test", "")
        self.assertEqual(readiness["deliverability"], "unverified")


class CompanyFitTest(unittest.TestCase):
    def test_company_fit_is_independent_of_the_mailbox(self):
        for address in (
            "reservation@palmcourt.example",
            "cs@palmcourt.example",
            "wayan.sudiarta@palmcourt.example",
        ):
            with self.subTest(address=address):
                result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"email": address})
                self.assertEqual(result["company_fit"]["status"], "fit")
                self.assertEqual(result["stage"], "qualified_company")

    def test_industry_outside_icp_stays_discovered(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"segment": "retail fashion", "company": "Kopi Senja"})
        self.assertEqual(result["stage"], "discovered")
        self.assertEqual(result["company_fit"]["status"], "outside_icp")
        self.assertIn("industry_outside_icp", result["reasons"])

    def test_geo_outside_icp_stays_discovered(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"country": "Surabaya"})
        self.assertEqual(result["stage"], "discovered")
        self.assertIn("geo_outside_icp", result["reasons"])

    def test_undefined_icp_cannot_qualify_a_company(self):
        result = domain.qualify({"icp": {}}, BASE_LEAD)
        self.assertEqual(result["stage"], "discovered")
        self.assertEqual(result["company_fit"]["status"], "unproven")
        self.assertIn("icp_not_defined", result["reasons"])

    def test_excluded_company_is_rejected(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"company": "Competitor Motors Indonesia"})
        self.assertEqual(result["stage"], "rejected")

    def test_missing_evidence_leaves_company_unproven(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"evidence": ""})
        self.assertEqual(result["stage"], "discovered")
        self.assertEqual(result["company_fit"]["status"], "unproven")

    def test_icp_rules_do_not_mutate_the_profile(self):
        profile = copy.deepcopy(ALETRA_DNA)
        domain.qualify(profile, BASE_LEAD)
        self.assertEqual(profile, ALETRA_DNA, "qualification must never rewrite the brand config")


class RecommendationTest(unittest.TestCase):
    def test_role_desk_recommends_finding_the_pic(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"role": "", "email": "reservation@palmcourt.example"})
        self.assertEqual(result["recommendation"]["action"], "find_decision_maker")
        self.assertTrue(result["recommendation"]["targets"])

    def test_business_contact_recommends_review(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD | {"role": "", "email": "procurement@palmcourt.example"})
        self.assertEqual(result["recommendation"]["action"], "review_business_contact")

    def test_decision_maker_waits_for_approval(self):
        result = domain.qualify(ALETRA_DNA, BASE_LEAD)
        self.assertEqual(result["recommendation"]["action"], "await_approval")
        self.assertFalse(result["outreach_ready"])
        self.assertFalse(result["send_allowed"])


class StageLabelTest(unittest.TestCase):
    def test_stage_ladder(self):
        self.assertEqual(domain.stage_label("discovered", "discovered", "role_generic"), "discovered")
        self.assertEqual(domain.stage_label("qualified_company", "discovered", "role_generic"), "qualified_company")
        self.assertEqual(
            domain.stage_label("qualified_company", "qualified", "decision_maker"), "ready_for_outreach")
        self.assertEqual(
            domain.stage_label("qualified_company", "qualified", "business_contact"), "qualified_company",
            "an official desk needs review before it is offered for outreach")
        self.assertEqual(
            domain.stage_label("qualified_company", "draft_ready", "business_contact"), "ready_for_outreach")
        self.assertEqual(
            domain.stage_label("qualified_company", "qualified", "person_unknown_role"), "qualified_company")
        self.assertEqual(domain.stage_label("qualified_company", "do_not_contact", "decision_maker"), "suppressed")
        self.assertEqual(
            domain.stage_label("qualified_company", "qualified", "decision_maker", suppressed=True), "suppressed")
        self.assertEqual(domain.stage_label("qualified_company", "archived", "decision_maker"), "archived")
        self.assertEqual(domain.stage_label("rejected", "discovered", "decision_maker"), "rejected")


class StoredStageTest(unittest.TestCase):
    """Persistence: stages survive save/read, dedupe keeps PICs, isolation and suppression hold."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        with storage.unit_of_work() as conn:
            self.business = storage.save_business(conn, {
                "name": "Kinetra Mobility", "offer": "Electric MPV fleet sales",
                "offer_short": "Electric MPV fleet", "default_cta": "Reply if relevant.", **ALETRA_DNA,
            })
            self.other = storage.save_business(conn, {
                "name": "Cedarline Fixture Studio", "offer": "Fixture studio",
                "offer_short": "Fixtures", "default_cta": "Reply if relevant.", "icp": {},
            })

    def _save(self, lead):
        with storage.unit_of_work() as conn:
            return storage.save_lead(conn, self.business["id"], lead, domain.qualify(self.business, lead))

    def test_role_desk_company_is_stored_as_qualified_company(self):
        lead = self._save(BASE_LEAD | {"role": "", "email": "reservation@palmcourt.example"})
        row = pipeline.public_row(lead)
        self.assertEqual(row["stage"], "qualified_company")
        self.assertFalse(row["outreach_ready"])
        self.assertEqual(row["recommended_action"], "find_decision_maker")
        self.assertEqual(row["company_fit"], "fit")
        self.assertEqual(row["recipient"]["deliverability"], "unverified")

    def test_decision_maker_becomes_ready_only_after_operator_step(self):
        lead = self._save(BASE_LEAD)
        self.assertEqual(pipeline.public_row(lead)["stage"], "qualified_company")
        with storage.unit_of_work() as conn:
            promoted = pipeline.set_status(conn, self.business["id"], lead["id"], "qualified")
        self.assertEqual(promoted["prospect"]["stage"], "ready_for_outreach")
        self.assertTrue(promoted["prospect"]["outreach_ready"])

    def test_business_contact_needs_review_before_ready(self):
        lead = self._save(BASE_LEAD | {"role": "", "email": "procurement@palmcourt.example"})
        with storage.unit_of_work() as conn:
            qualified = pipeline.set_status(conn, self.business["id"], lead["id"], "qualified")
        self.assertEqual(qualified["prospect"]["stage"], "qualified_company")
        self.assertEqual(qualified["prospect"]["recommended_action"], "review_business_contact")
        with storage.unit_of_work() as conn:
            drafted = pipeline.set_status(conn, self.business["id"], lead["id"], "draft_ready")
        self.assertEqual(drafted["prospect"]["stage"], "ready_for_outreach")

    def test_generic_desk_never_becomes_ready(self):
        lead = self._save(BASE_LEAD | {"role": "", "email": "cs@besttrans.example"})
        with storage.unit_of_work() as conn:
            promoted = pipeline.set_status(conn, self.business["id"], lead["id"], "qualified")
        self.assertEqual(promoted["prospect"]["stage"], "qualified_company")
        self.assertFalse(promoted["prospect"]["outreach_ready"])

    def test_many_pics_per_company_are_kept(self):
        desk = self._save(BASE_LEAD | {"role": "", "email": "reservation@palmcourt.example"})
        pic = self._save(BASE_LEAD | {"contact_name": "Wayan", "email": "wayan.sudiarta@palmcourt.example"})
        self.assertNotEqual(desk["id"], pic["id"])
        with storage.unit_of_work() as conn:
            rows, total = pipeline.list_prospects(conn, self.business["id"])
        self.assertEqual(total, 2)
        self.assertEqual({row["company"] for row in rows}, {"Palm Court Demo Villas"})

    def test_same_mailbox_is_deduped(self):
        first = self._save(BASE_LEAD)
        second = self._save(BASE_LEAD)
        self.assertEqual(first["id"], second["id"])
        with storage.unit_of_work() as conn:
            total = conn.execute("SELECT COUNT(*) FROM leads WHERE business_id=?", (self.business["id"],)).fetchone()[0]
        self.assertEqual(total, 1)

    def test_history_is_preserved_across_resaves(self):
        lead = self._save(BASE_LEAD)
        self._save(BASE_LEAD | {"role": "General Manager"})
        with storage.unit_of_work() as conn:
            events = conn.execute("SELECT COUNT(*) FROM events WHERE ref_id=?", (lead["id"],)).fetchone()[0]
            created = storage.get_lead(conn, lead["id"])["created_at"]
        self.assertGreaterEqual(events, 2)
        self.assertEqual(created, lead["created_at"])

    def test_suppressed_address_is_not_actionable(self):
        lead = self._save(BASE_LEAD)
        with storage.unit_of_work() as conn:
            pipeline.set_status(conn, self.business["id"], lead["id"], "qualified")
            storage.add_suppression(conn, self.business["id"], BASE_LEAD["email"], "manual")
            rows, _total = pipeline.list_prospects(conn, self.business["id"])
        self.assertEqual(rows[0]["stage"], "suppressed")
        self.assertFalse(rows[0]["outreach_ready"])

    def test_brand_isolation_hides_other_brand_leads(self):
        self._save(BASE_LEAD)
        with storage.unit_of_work() as conn:
            rows, total = pipeline.list_prospects(conn, self.other["id"])
        self.assertEqual((len(rows), total), (0, 0))


if __name__ == "__main__":
    unittest.main()
