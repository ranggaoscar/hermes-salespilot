"""Invoke SalesPilot through Hermes in an isolated HERMES_HOME. Not a production install."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, check=False)


def _plugin_call(home: Path, code: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    env["PYTHONPATH"] = str(home / "plugins" / "hermes-salespilot")
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=False)


def main() -> None:
    home = Path(tempfile.mkdtemp(prefix="salespilot-hermes-"))
    dest = home / "plugins" / "hermes-salespilot"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "docs", "scripts"))
    enabled = _run(["hermes", "plugins", "enable", "hermes-salespilot", "--no-allow-tool-override"], home)
    listed = _run(["hermes", "plugins", "list", "--enabled", "--json"], home)
    onboard = _plugin_call(
        home,
        "import tools; print(tools.onboard_business({'authorized': True, 'authorization_note': 'cli', "
        "'default_cta': 'Reply if useful.', 'default_country': 'ID', 'name': 'Cedarline Fixture Studio', "
        "'offer': 'Fixture schedules.', 'offer_short': 'Fixture schedules', 'segments': ['interior studio'], "
        "'geos': ['Demo Harbor']}))",
    )
    report = _plugin_call(home, "import tools; print(tools.report({}))")
    removed = _run(["hermes", "plugins", "remove", "hermes-salespilot"], home)
    after = _run(["hermes", "plugins", "list", "--enabled", "--json"], home)
    print(json.dumps({
        "home": str(home),
        "enable_code": enabled.returncode,
        "enable_tail": (enabled.stdout or enabled.stderr)[-400:],
        "list_code": listed.returncode,
        "onboard_code": onboard.returncode,
        "onboard_tail": (onboard.stdout or onboard.stderr)[-400:],
        "report_code": report.returncode,
        "report_tail": (report.stdout or report.stderr)[-300:],
        "remove_code": removed.returncode,
        "after_code": after.returncode,
        "still_listed": "hermes-salespilot" in (after.stdout or ""),
    }))


if __name__ == "__main__":
    main()
