"""Search result URLs are fetched. Missing search results are not invented."""

from __future__ import annotations

import json
import threading
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import fetch
import storage
import tools
import views

DIRECTORY = """
Company: Northlamp Demo Studio
Segment: interior studio
Country: ID
Why: Publishes a studio contact page and lists hospitality interiors.
Email: hello@northlamp.example
Phone: 628120000411
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = DIRECTORY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def _call(fn, args):
    return json.loads(fn(args))


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        fetch.allow_loopback_for_tests(True)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/directory"
        self.business = _call(tools.onboard_business, {
            "name": "Cedarline",
            "offer": "Fixture schedules for lobby stone.",
            "offer_short": "Fixture schedules",
            "default_cta": "Reply if the brief is still open.",
            "research_only": True,
            "segments": ["interior studio"],
            "geos": ["ID"],
            "default_country": "ID",
        })["business"]

    def tearDown(self):
        tools.bind(None)
        self.server.shutdown()
        fetch.allow_loopback_for_tests(False)
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_search_url_lands_in_pipeline_and_repeats_do_not_duplicate(self):
        class Ctx:
            def dispatch_tool(self, name, args):
                self.seen = (name, args)
                return json.dumps({"success": True, "data": {"web": [{"url": self_url, "title": "directory"}]}})

        self_url = self.url
        ctx = Ctx()
        tools.bind(ctx)
        first = _call(tools.research_opportunity, {"authorized": True, "use_hermes_search": True, "query": "northlamp demo"})
        second = _call(tools.research_opportunity, {"authorized": True, "use_hermes_search": True, "query": "northlamp demo"})
        self.assertEqual(ctx.seen[0], "web_search")
        self.assertTrue(first["fetched"])
        self.assertFalse(first["fabricated"])
        self.assertEqual(len(first["prospects"]), 1)
        self.assertEqual(first["prospects"][0]["id"], second["prospects"][0]["id"])
        listed = views.pipeline_view(self.business["id"])
        self.assertEqual(listed["count"], 1)
        row = listed["prospects"][0]
        self.assertEqual(row["company"], "Northlamp Demo Studio")
        self.assertTrue(row["contact_source"])
        self.assertEqual(row["inbox_delivery"], "not_observed")
        self.assertFalse(listed["gmail_oauth_connected"])
        self.assertEqual(listed["gmail_oauth"], "unavailable")
        self.assertFalse(listed["mail"]["password_present"])
        self.assertNotIn("hello@northlamp.example", json.dumps(listed["mail"]))

    def test_empty_search_does_not_invent_a_prospect(self):
        class Ctx:
            def dispatch_tool(self, name, args):
                return json.dumps({"success": True, "data": {"web": []}})

        tools.bind(Ctx())
        found = _call(tools.research_opportunity, {"authorized": True, "use_hermes_search": True, "query": "nothing"})
        self.assertEqual(found["prospects"], [])
        self.assertFalse(found["fabricated"])
        self.assertEqual(views.pipeline_view(self.business["id"])["count"], 0)

    def test_lifecycle_archive_delete_and_restart(self):
        found = _call(tools.research_opportunity, {"authorized": True, "discovery_url": self.url})
        lead_id = found["prospects"][0]["id"]
        _call(tools.qualify_lead, {"lead_id": lead_id})
        drafted = _call(tools.draft_outreach, {"lead_id": lead_id, "channel": "email"})
        self.assertTrue(drafted["ok"])
        accepted = _call(tools.pipeline_action, {"action": "smtp_accepted", "lead_id": lead_id, "message_id": "<sim@example>"})
        self.assertFalse(accepted["reply_inferred"])
        due = _call(tools.pipeline_action, {"action": "status", "lead_id": lead_id, "status": "follow_up_due"})
        done = _call(tools.pipeline_action, {"action": "status", "lead_id": lead_id, "status": "follow_up_done"})
        self.assertEqual(done["prospect"]["status"], "followed_up")
        archived = _call(tools.pipeline_action, {"action": "archive", "lead_id": lead_id})
        self.assertTrue(archived["prospect"]["archived"])
        self.assertFalse(archived["prospect"]["deleted"])
        hidden = _call(tools.pipeline_action, {"action": "list"})
        self.assertEqual(hidden["count"], 0)
        visible = _call(tools.pipeline_action, {"action": "list", "include_archived": True})
        self.assertEqual(visible["count"], 1)
        _call(tools.pipeline_action, {"action": "delete", "lead_id": lead_id, "confirm_delete": True})
        with storage.unit_of_work() as conn:
            self.assertTrue(storage.is_suppressed(conn, self.business["id"], "hello@northlamp.example"))
            lead = storage.get_lead(conn, lead_id)
            self.assertTrue(lead["deleted_at"])
        again = views.pipeline_view(self.business["id"])
        self.assertEqual(again["count"], 0)
        self.assertFalse(due["sent"])
