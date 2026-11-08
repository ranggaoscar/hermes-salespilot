"""Paged reads and the v1.0 lifecycle names."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pipeline
import storage
import tools
import views


class ScaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.business = json.loads(tools.onboard_business({
            "name": "Kinetra Mobility",
            "offer": "Electric MPV fleet sales for Indonesian businesses.",
            "offer_short": "EV MPV fleet",
            "default_cta": "Reply if this matches a current project.",
        }))["business"]["id"]

    def _rows(self, count: int) -> None:
        with storage.unit_of_work() as conn:
            for index in range(count):
                company = f"Fleet Co {index:03d}"
                conn.execute(
                    "INSERT INTO leads(id, business_id, company, company_key, contact_name, role, email,"
                    " email_valid, phone, phone_key, phone_valid, segment, country, source_url, evidence,"
                    " unknowns_json, score, decision, reasons_json, gates_json, confidence_json,"
                    " pipeline_status, stage, created_at, updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"lead_{index:03d}", self.business, company, company.lower(), "", "",
                        f"ops{index}@fleet{index}.example", 1, "", "", 0, "", "ID",
                        "https://example.com/quote", f"Quoted line for {company}.", "{}", 60,
                        "maybe", "[]", "{}", "{}",
                        "qualified" if index % 2 else "discovered", "qualified",
                        "2026-01-01T00:00:00Z", f"2026-01-01T00:00:{index % 60:02d}Z",
                    ),
                )

    def test_a_page_returns_its_own_slice_and_the_matching_total(self):
        self._rows(120)
        page = views.pipeline_view(self.business, limit=25, offset=0)
        self.assertEqual(page["total"], 120)
        self.assertEqual(page["count"], 25)
        deep = views.pipeline_view(self.business, limit=25, offset=100)
        self.assertEqual(deep["count"], 20)
        self.assertFalse({row["id"] for row in page["prospects"]} & {row["id"] for row in deep["prospects"]})

    def test_status_filter_and_search_run_in_the_query(self):
        self._rows(40)
        filtered = views.pipeline_view(self.business, status="qualified", limit=50)
        self.assertEqual(filtered["total"], 20)
        self.assertTrue(all(row["status"] == "qualified" for row in filtered["prospects"]))
        searched = views.pipeline_view(self.business, query="fleet co 007", limit=50)
        self.assertEqual(searched["total"], 1)
        self.assertEqual(searched["prospects"][0]["company"], "Fleet Co 007")

    def test_the_lifecycle_uses_the_v1_names(self):
        self.assertEqual(
            set(pipeline.STATUSES),
            {"discovered", "qualified", "draft_ready", "contacted", "replied", "follow_up_due",
             "followed_up", "not_interested", "do_not_contact", "archived"},
        )
        self._rows(2)
        moved = views.pipeline_change({"business_id": self.business, "action": "status", "lead_id": "lead_000", "status": "contacted"})
        self.assertEqual(moved["prospect"]["status"], "contacted")
        legacy = views.pipeline_change({"business_id": self.business, "action": "status", "lead_id": "lead_000", "status": "smtp_accepted"})
        self.assertEqual(legacy["prospect"]["status"], "contacted")


if __name__ == "__main__":
    unittest.main()
