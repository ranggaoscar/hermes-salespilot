"""Brand boundaries: explicit resolution, isolation, and a refusal instead of a guess."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import domain
import storage
import tools
import views


class BrandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.aletra = self._onboard("Kinetra Mobility", "Electric MPV fleet sales for Jakarta and Bali businesses.")
        self.cedarline = self._onboard("Cedarline", "Lighting and fixture specification for interior studios.")

    def _onboard(self, name: str, offer: str) -> str:
        saved = json.loads(tools.onboard_business({
            "name": name,
            "offer": offer,
            "offer_short": offer[:60],
            "default_cta": "Reply if this matches a current project.",
        }))
        self.assertTrue(saved.get("ok"), saved)
        return saved["business"]["id"]

    def test_each_business_gets_one_brand(self):
        with storage.read_only() as conn:
            rows = storage.list_brands(conn)
        by_id = {r["business_id"] for r in rows}
        self.assertEqual(by_id, {self.aletra, self.cedarline})
        self.assertEqual(len(rows), 2, "one brand row per business")

    def test_a_brand_resolves_by_name_slug_and_id(self):
        with storage.read_only() as conn:
            by_name, reason = storage.resolve_brand(conn, "cedarline")
            by_id, _ = storage.resolve_brand(conn, self.cedarline)
        self.assertEqual(reason, "")
        self.assertEqual(by_name["business_id"], self.cedarline)
        self.assertEqual(by_id["business_id"], self.cedarline)

    def test_an_unknown_brand_fails_closed(self):
        with storage.read_only() as conn:
            brand, reason = storage.resolve_brand(conn, "Northwind Traders")
        self.assertIsNone(brand)
        self.assertEqual(reason, "unknown_brand")
        refused = json.loads(tools.pipeline_action({"action": "list", "brand": "Northwind Traders"}))
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["code"], "missing_business")

    def test_switching_brand_moves_the_default_and_keeps_records_apart(self):
        with storage.unit_of_work() as conn:
            storage.set_active_brand(conn, self.cedarline)
        state = views.switch_brand({"brand": "Kinetra Mobility"})
        self.assertTrue(state["ok"])
        self.assertEqual(state["active"]["id"], self.aletra)
        self.assertEqual(len(state["brands"]), 2)

    def test_customer_rows_stay_inside_their_brand(self):
        imported = json.loads(tools.import_customers({
            "brand": "Cedarline",
            "authorized": True,
            "authorization_note": "synthetic test rows authored by the operator",
            "source_label": "synthetic-test",
            "csv_text": "company,email\nBali Villa Works,ops@balivillaworks.example\n",
            "mapping": {"company": "company", "email": "email"},
        }))
        self.assertTrue(imported.get("ok"), imported)
        with storage.read_only() as conn:
            cedarline_rows = storage.list_customers(conn, self.cedarline)
            aletra_rows = storage.list_customers(conn, self.aletra)
        self.assertEqual(len(cedarline_rows), 1)
        self.assertEqual(aletra_rows, [])

    def test_migration_backfills_brands_for_existing_businesses(self):
        with storage.read_only() as conn:
            version = storage.schema_version(conn)
            brands = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
            businesses = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
            again = storage.migrate_schema(conn)
        self.assertEqual(version, domain.SCHEMA_VERSION)
        self.assertFalse(again)
        self.assertEqual(brands, businesses)


if __name__ == "__main__":
    unittest.main()
