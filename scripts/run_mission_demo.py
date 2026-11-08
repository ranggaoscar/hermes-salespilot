"""Reproducible mission demo. Synthetic companies. No send."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mission
import storage
import tools
DNA = """
Differentiator: schedules stone before the architect locks the lobby
Offer: fixture schedules
Segment: interior studio
"""
PAGE = """
Company: Harborline Studio
Date: 2026-03-12
Signal: published a lobby renovation brief
Offer: fixture schedules
"""


def main() -> None:
    data = ROOT / "data" / "mission-demo"
    if data.exists():
        for child in data.glob("*"):
            child.unlink()
    storage.set_data_dir(data)
    onboard = json.loads(tools.onboard_business({
        "authorized": True,
        "authorization_note": "synthetic demo",
        "name": "Cedarline Fixture Studio",
        "offer": "Fixture schedules.",
        "offer_short": "Fixture schedules",
        "default_cta": "Reply if a one-page schedule would help.",
        "default_country": "ID",
    }))
    saved = json.loads(mission.mission({
        "action": "save_dna",
        "name": "Lobby radar",
        "business_id": onboard["business"]["id"],
        "url": "https://example.invalid/cedarline",
        "text": DNA,
        "permitted": True,
    }))
    scanned = json.loads(mission.mission({
        "action": "scan",
        "name": "Lobby radar",
        "business_id": onboard["business"]["id"],
        "url": "https://example.invalid/harborline",
        "text": PAGE,
        "permitted": True,
    }))
    resumed = json.loads(mission.mission({
        "action": "resume",
        "name": "Lobby radar",
        "business_id": onboard["business"]["id"],
    }))
    lines = [
        "# SalesPilot mission demo",
        "",
        "Synthetic companies. Quotes come from the fixture text. No email was sent.",
        "",
        "```json",
        json.dumps({"dna": saved["dna"], "card": scanned["cards"][0], "resumed": resumed["mission_id"] == saved["mission_id"], "sent": False}, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    out = ROOT / "docs" / "mission-demo-transcript.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
