"""Run the fictional Phase 2 workflow and write an inspectable transcript."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import storage
import tools
SITE = (ROOT / "data" / "phase2" / "site.md").read_text(encoding="utf-8")
CSV = (ROOT / "data" / "phase2" / "customers.csv").read_text(encoding="utf-8")
PROSPECTS = json.loads((ROOT / "data" / "phase2" / "prospects.json").read_text(encoding="utf-8"))
MAPPING = {
    "Company": "company",
    "Contact": "contact_name",
    "Email": "email",
    "Phone": "phone",
    "Segment": "segment",
    "Notes": "notes",
}


def call(fn, args):
    return json.loads(fn(args))


def main() -> None:
    tmp = tempfile.TemporaryDirectory()
    storage.set_data_dir(Path(tmp.name))
    steps = []
    onboard = call(tools.onboard_business, {
        "authorized": True,
        "authorization_note": "operator supplied fictional page text",
        "default_cta": "Reply if a one-page fixture shortlist would help.",
        "default_country": "ID",
        "sources": [{"url": "https://example.invalid/cedarline", "text": SITE, "permitted": True}],
    })
    steps.append(("onboard", onboard))
    imported = call(tools.import_customers, {
        "csv_text": CSV,
        "mapping": MAPPING,
        "authorized": True,
        "authorization_note": "fictional batch",
        "source": "phase2-fixture-csv",
        "synthetic": True,
    })
    steps.append(("import", imported))
    for prospect in PROSPECTS:
        researched = call(tools.research_opportunity, {
            "title": prospect["url"].rsplit("/", 1)[-1],
            "sources": [{"url": prospect["url"], "text": prospect["text"], "permitted": True}],
        })
        steps.append(("research", researched))
        if researched.get("ok"):
            steps.append(("qualify", call(tools.qualify_lead, {"lead_id": researched["lead"]["id"]})))
    for step_name, payload in list(steps):
        lead = payload.get("lead") or {}
        if step_name == "qualify" and lead.get("decision") == "qualified":
            steps.append(("draft", call(tools.draft_outreach, {"lead_id": lead["id"], "channel": "email"})))
    steps.append(("followups", call(tools.plan_followups, {})))
    steps.append(("report", call(tools.report, {"section": "summary"})))
    drafts = [payload["draft"] for name, payload in steps if name == "draft" and payload.get("ok")]
    if drafts:
        steps.append(("approval", call(tools.request_approval, {
            "draft_id": drafts[0]["id"],
            "lead_id": drafts[0]["lead_id"],
            "decision": "approve",
            "actor": "demo",
            "note": "ledger only",
            "human_confirmed": True,
        })))
    lines = ["# SalesPilot Phase 2 demo transcript", "", "Fictional data only. Nothing was fetched or sent.", ""]
    for name, payload in steps:
        lines.append(f"## {name}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    out = ROOT / "docs" / "demo-transcript.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    storage.set_data_dir(None)
    tmp.cleanup()


if __name__ == "__main__":
    main()
