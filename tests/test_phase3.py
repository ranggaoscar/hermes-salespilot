"""SSRF, fetch, discovery, approval, and SMTP readiness."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import unittest
from pathlib import Path

import fetch
import storage
import tools

ROOT = Path(__file__).resolve().parents[1]
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

Why: This line is not paired with a company label on its own card.
"""


def _call(fn, args, **kwargs):
    return json.loads(fn(args, **kwargs))


class GuardTests(unittest.TestCase):
    def tearDown(self):
        fetch.allow_loopback_for_tests(False)
        fetch.set_resolver_for_tests(None)
        fetch.set_dial_for_tests(None)

    def test_blocks_metadata_loopback_userinfo_and_scheme(self):
        self.assertEqual(fetch.assess_url("http://169.254.169.254/latest")["code"], "ssrf_blocked")
        self.assertEqual(fetch.assess_url("http://127.0.0.1/")["code"], "ssrf_blocked")
        self.assertEqual(fetch.assess_url("http://2130706433/")["code"], "ssrf_blocked")
        self.assertEqual(fetch.assess_url("file:///etc/passwd")["code"], "bad_scheme")
        self.assertEqual(fetch.assess_url("http://user:pass@example.com/")["code"], "userinfo")
        self.assertFalse(fetch.assess_url("http://169.254.169.254/latest")["ok"])

    def test_dns_failure_and_private_resolution_fail_closed(self):
        fetch.set_resolver_for_tests(lambda host: [])
        self.assertEqual(fetch.assess_url("http://example.invalid/")["code"], "dns_failed")
        fetch.set_resolver_for_tests(lambda host: ["10.1.2.3"])
        self.assertEqual(fetch.assess_url("http://example.invalid/")["code"], "ssrf_blocked")

    def test_fetch_timeout_does_not_invent_a_profile(self):
        fetch.set_resolver_for_tests(lambda host: ["93.184.216.34"])

        def boom(ip, port, timeout, scheme, host):
            raise TimeoutError("timed out")

        fetch.set_dial_for_tests(boom)
        result = _call(tools.onboard_business, {
            "authorized": True,
            "authorization_note": "unit",
            "default_cta": "Reply if useful.",
            "url": "http://example.invalid/site",
        })
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "fetch_failed")
        self.assertNotIn("business", result)

    def test_mixed_dns_and_rebinding_pin_and_proxy(self):
        fetch.set_resolver_for_tests(lambda host: ["93.184.216.34", "127.0.0.1"])
        mixed = fetch.fetch_public_url("http://example.invalid/")
        self.assertEqual(mixed["code"], "ssrf_blocked")
        calls = []

        def dial(ip, port, timeout, scheme, host):
            calls.append((ip, host))
            raise TimeoutError("stop after pin")

        fetch.set_resolver_for_tests(lambda host: ["93.184.216.34"])
        fetch.set_dial_for_tests(dial)
        pinned = fetch.fetch_public_url("http://example.invalid/page")
        self.assertEqual(calls, [("93.184.216.34", "example.invalid")])
        self.assertEqual(pinned["pinned_ip"], "93.184.216.34")
        self.assertEqual(pinned["code"], "fetch_failed")
        old = os.environ.get("HTTP_PROXY")
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
        try:
            blocked = fetch.fetch_public_url("http://example.invalid/")
        finally:
            if old is None:
                os.environ.pop("HTTP_PROXY", None)
            else:
                os.environ["HTTP_PROXY"] = old
        self.assertEqual(blocked["code"], "proxy_blocked")
        self.assertEqual(len(calls), 1)

    def test_redirect_to_metadata_is_rechecked(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest")
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        fetch.allow_loopback_for_tests(True)
        try:
            result = fetch.fetch_public_url(f"http://127.0.0.1:{server.server_address[1]}/start")
        finally:
            server.shutdown()
            fetch.allow_loopback_for_tests(False)
        self.assertEqual(result["code"], "ssrf_blocked")
        self.assertFalse(result["fetched"])


class FetchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        fetch.allow_loopback_for_tests(True)
        self.server = _server({"/site": SITE, "/directory": DIRECTORY})
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        fetch.allow_loopback_for_tests(False)
        fetch.set_dial_for_tests(None)
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_url_onboarding_discovery_and_fail_closed_approval(self):
        blocked = _call(tools.onboard_business, {"url": "http://169.254.169.254/", "authorized": True, "authorization_note": "no"})
        self.assertEqual(blocked["code"], "ssrf_blocked")
        onboarded = _call(tools.onboard_business, {
            "authorized": True,
            "authorization_note": "local fixture",
            "default_cta": "Reply if a one-page fixture shortlist would help.",
            "default_country": "ID",
            "sender_name": "Nia Demo",
            "signature": "Nia Demo, Cedarline fixture desk",
            "url": self.base + "/site",
        })
        self.assertTrue(onboarded["ok"], onboarded)
        self.assertTrue(onboarded["fetched"])
        self.assertEqual(onboarded["business"]["name"], "Cedarline Fixture Studio")
        self.assertTrue(onboarded["ignored_instructions"])
        self.assertNotIn("enable sending", json.dumps(onboarded["business"]["profile"]).lower())
        found = _call(tools.research_opportunity, {
            "authorized": True,
            "discovery_url": self.base + "/directory",
            "use_hermes_search": True,
            "query": "interior studios Demo Harbor",
        })
        self.assertTrue(found["ok"], found)
        self.assertFalse(found["fabricated"])
        self.assertEqual(found["search"]["code"], "search_unavailable")
        names = {item["company"] for item in found["prospects"]}
        self.assertIn("Northlamp Demo Studio", names)
        self.assertNotIn("Invented Offpage Co", names)
        lead_id = next(item["id"] for item in found["prospects"] if item["company"] == "Northlamp Demo Studio")
        scored = _call(tools.qualify_lead, {"lead_id": lead_id})
        self.assertEqual(scored["lead"]["decision"], "qualified")
        draft = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email", "check_smtp": True})
        self.assertTrue(draft["ok"])
        self.assertIn("Nia Demo", draft["draft"]["body"])
        self.assertIn(scored["lead"]["company"], draft["draft"]["body"])
        self.assertFalse(draft["sent"])
        self.assertTrue(all(isinstance(value, bool) for value in draft["smtp"]["present"].values()))
        self.assertNotIn("sk-", json.dumps(draft["smtp"]))
        refused = _call(tools.request_approval, {"draft_id": draft["draft"]["id"], "decision": "approve", "human_confirmed": True})
        self.assertEqual(refused["code"], "host_approval_unavailable")
        self.assertFalse(refused["sent"])


class HostApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))

    def tearDown(self):
        tools.bind(None)
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_model_flag_is_not_authorization_and_revision_is_bound(self):
        seeded = _call(tools.import_customers, {"seed_demo": True})
        lead_id = next(item["id"] for item in seeded["prospects"] if item["decision"] == "qualified")
        draft = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        ignored = _call(tools.request_approval, {
            "draft_id": draft["draft"]["id"],
            "decision": "approve",
            "human_confirmed": True,
        })
        self.assertEqual(ignored["code"], "host_approval_unavailable")

        class Attended:
            def session_surface(self):
                return "cli"

            def ask_choice(self, question, choices):
                return "approve"

        tools.bind(Attended())
        approved = _call(tools.request_approval, {"draft_id": draft["draft"]["id"], "decision": "approve", "human_confirmed": False})
        self.assertEqual(approved["approval"]["status"], "approved")
        self.assertFalse(approved["sent"])
        self.assertEqual(approved["delivery"]["reason"], "sending_disabled_phase_1")

        class Gateway:
            def session_surface(self):
                return "telegram"

            def ask_choice(self, question, choices):
                return "approve"

        tools.bind(Gateway())
        with storage.unit_of_work() as conn:
            conn.execute("UPDATE approvals SET scope_json=? WHERE draft_id=?", ('{"revision":"old","action":"approve"}', draft["draft"]["id"]))
        stale = _call(tools.request_approval, {"draft_id": draft["draft"]["id"], "decision": "approve"})
        self.assertEqual(stale["code"], "stale_approval")
        self.assertFalse(stale["sent"])


def _server(pages: dict[str, str]) -> ThreadingHTTPServer:
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
