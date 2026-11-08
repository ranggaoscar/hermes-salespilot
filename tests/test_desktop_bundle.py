"""Gate the desktop bundle through its Node lifecycle tests.

The bundle's failure modes (temporal-dead-zone crash in Settings, duplicate page/nav registration,
polling while hidden) only appear when the module is actually evaluated, so this runs the real
tests/desktop suite with node:test when Node is available.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    ROOT / "tests" / "desktop" / "plugin-lifecycle.test.mjs",
    ROOT / "tests" / "desktop" / "select-dropdown.test.mjs",
)


class DesktopBundleTests(unittest.TestCase):
    def test_lifecycle_suite_passes(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed on this host")
        missing = [str(suite) for suite in SUITES if not suite.exists()]
        if missing:
            self.fail(f"missing desktop suites: {', '.join(missing)}")
        result = subprocess.run(
            [node, "--test", *[str(suite) for suite in SUITES]],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"desktop lifecycle suite failed:\n{output[-3000:]}")
        self.assertIn("pass", output.lower())


if __name__ == "__main__":
    unittest.main()
