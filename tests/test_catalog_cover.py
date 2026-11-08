"""Catalog cover is a real PNG at the marketplace ratio. No plugin runtime."""

from __future__ import annotations

import struct
import unittest
from pathlib import Path


class CatalogCoverTests(unittest.TestCase):
    def test_png_is_exact_and_readable(self):
        path = Path("assets/catalog-cover.png")
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual((width, height), (1200, 600))
        self.assertGreater(len(data), 1000)
        # The cover is rendered from HTML so it can carry a real (synthetic-fixture) UI capture.
        source = Path("assets/catalog-cover.html").read_text(encoding="utf-8")
        self.assertIn("SalesPilot", source)
        self.assertIn("ROCK", source)
        self.assertIn("synthetic", source.lower())
        for asset in ("assets/brand/app-icon.svg", "assets/brand/ui-customers.png"):
            self.assertTrue(Path(asset).is_file(), asset)
        self.assertNotIn("image:", Path("plugin.yaml").read_text(encoding="utf-8"))
