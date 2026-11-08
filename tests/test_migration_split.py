"""Reads do not migrate. Migration of a schema 3 copy is explicit."""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import domain
import storage
import views

LIVE_COPY = Path(r"D:/sp61/backup/pre-62c/salespilot.db")


class MigrationSplitTests(unittest.TestCase):
    def test_read_does_not_change_schema_three_copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name)
        shutil.copy2(LIVE_COPY, dest / "salespilot.db")
        before = (dest / "salespilot.db").stat().st_size
        storage.set_data_dir(dest)
        self.addCleanup(storage.set_data_dir, None)
        result = views.pipeline_view()
        self.assertEqual(result["code"], "schema_pending")
        self.assertFalse(result["migrated"])
        check = sqlite3.connect(dest / "salespilot.db")
        version = check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
        cols = {row[1] for row in check.execute("PRAGMA table_info(leads)")}
        businesses = check.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        missions = check.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
        check.close()
        self.assertEqual(version, "3")
        self.assertNotIn("pipeline_status", cols)
        self.assertEqual(businesses, 1)
        self.assertEqual(missions, 1)
        self.assertEqual((dest / "salespilot.db").stat().st_size, before)

    def test_explicit_migration_is_idempotent_and_preserves_rows(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name)
        shutil.copy2(LIVE_COPY, dest / "salespilot.db")
        storage.set_data_dir(dest)
        self.addCleanup(storage.set_data_dir, None)
        conn = storage._connect(migrate=False)
        try:
            first = storage.migrate_schema(conn)
            businesses = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
            missions = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
            drafts = conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0]
            deliveries = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
            approvals = conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]
            second = storage.migrate_schema(conn)
            version = storage.schema_version(conn)
            brands = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        finally:
            conn.close()
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(version, domain.SCHEMA_VERSION)
        self.assertEqual(brands, businesses)
        self.assertEqual((businesses, missions, drafts, deliveries, approvals), (1, 1, 0, 0, 0))
        check = sqlite3.connect(dest / "salespilot.db")
        self.assertEqual(check.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        check.close()
