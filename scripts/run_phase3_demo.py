"""Reproducible local demo. Fetches a loopback fixture only after the SSRF block is shown."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fetch
import storage
import tools

SITE = (ROOT / "data" / "phase2" / "site.md").read_text(encoding="utf-8")
DIRECTORY = """
Company: Northlamp Demo Studio
Segment: interior studio
Country: Demo Harbor
Page: https://example.invalid/northlamp
Why: Publishes a studio contact page and lists hospitality interiors in Demo Harbor.
Email: hello@northlamp.example.invalid
Phone: 628120000411

Company: Harbor Desk Demo Co
Segment: hospitality
Country: Demo Harbor
Page: https://example.invalid/harbordesk
Why: Public project page names a lobby fit-out and a company phone in Demo Harbor.
Email: buying@harbordesk.example.invalid
Phone: 628120000412

Company: Lumen Room Demo Build
Segment: architect
Country: Demo Harbor
Page: https://example.invalid/lumenroom
Why: Public fit-out note names the coordinator and a company email.
Email: bids@lumenroom.example.invalid
Phone: 628120000413
"""


def call(fn, args, **kwargs):
    return json.loads(fn(args, **kwargs))


def serve(pages: dict[str, str]) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = pages.get(self.path, "").encode("utf-8")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    tmp = tempfile.TemporaryDirectory()
    storage.set_data_dir(Path(tmp.name))
    server = serve({"/site": SITE, "/directory": DIRECTORY})
    base = f"http://127.0.0.1:{server.server_address[1]}"
    steps = []
    steps.append(("ssrf_block", call(tools.onboard_business, {
        "authorized": True,
        "authorization_note": "demo",
        "default_cta": "Reply if a one-page fixture shortlist would help.",
        "url": "http://169.254.169.254/latest/meta-data/",
    })))
    fetch.allow_loopback_for_tests(True)
    steps.append(("onboard_fetch", call(tools.onboard_business, {
        "authorized": True,
        "authorization_note": "demo harness fetched the local fixture after SSRF block",
        "default_cta": "Reply if a one-page fixture shortlist would help.",
        "default_country": "ID",
        "sender_name": "Nia Demo",
        "signature": "Nia Demo, Cedarline fixture desk",
        "url": base + "/site",
    })))
    steps.append(("discover", call(tools.research_opportunity, {
        "authorized": True,
        "use_hermes_search": True,
        "query": "",
        "discovery_url": base + "/directory",
    })))
    for prospect in steps[-1][1].get("prospects") or []:
        if prospect.get("decision") == "qualified":
            steps.append(("qualify", call(tools.qualify_lead, {"lead_id": prospect["id"]})))
            steps.append(("draft", call(tools.draft_outreach, {
                "lead_id": prospect["id"],
                "channel": "email",
                "check_smtp": True,
            })))
            break
    steps.append(("followups", call(tools.plan_followups, {})))
    steps.append(("report", call(tools.report, {"section": "summary"})))
    drafts = [item[1] for item in steps if item[0] == "draft" and item[1].get("ok")]
    if drafts:
        steps.append(("approval_unattended", call(
            tools.request_approval,
            {"draft_id": drafts[0]["draft"]["id"], "decision": "approve", "human_confirmed": True},
            unattended=True,
        )))
    lines = [
        "# SalesPilot Phase 3 demo transcript",
        "",
        "Local fixture server only. Metadata URL was refused. Loopback fetch ran through the same fetcher after the test seam. Approval ignores human_confirmed and fails closed without a host choice. Nothing was sent.",
        "",
    ]
    for name, payload in steps:
        lines.append(f"## {name}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    out = ROOT / "docs" / "phase3-demo-transcript.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    server.shutdown()
    server.server_close()
    fetch.allow_loopback_for_tests(False)
    storage.set_data_dir(None)
    tmp.cleanup()


if __name__ == "__main__":
    main()
