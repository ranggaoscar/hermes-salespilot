"""Hardening: strict reply matching, auto-reply/bounce, cursors, policy, hot evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import accounts
import domain
import followstate
import inbox
import storage
import tools
import views


def onboard(name: str) -> str:
    saved = json.loads(tools.onboard_business({
        "name": name, "offer": f"{name} offer for fleet buyers.",
        "offer_short": name[:40], "default_cta": "Reply if this matches a project.",
    }))
    return saved["business"]["id"]


def discover(brand: str, company: str, email: str) -> str:
    source = {
        "url": "https://example.test/brief", "permitted": True,
        "text": (f"Company: {company}\nEmail: {email}\nRole: Fleet Manager\nSegment: Corporate fleet\n"
                 f"Country: Jakarta\nFact: published a 12-unit tender\nURL: https://example.test/brief\n"),
    }
    found = json.loads(tools.pipeline_action({"action": "discover", "brand": brand, "sources": [source]}))
    return (found.get("prospect") or {}).get("id", "")


def reply(sender: str, to: str, subject: str, body: str, in_reply_to: str = "",
          message_id: str = "", extra: dict[str, str] | None = None) -> bytes:
    headers = [
        f"From: {sender}", f"To: {to}", f"Subject: {subject}",
        f"Message-ID: {message_id or '<r-' + str(abs(hash((sender, subject, body))))[:8] + '@client.test>'}",
        "MIME-Version: 1.0", "Content-Type: text/plain; charset=utf-8",
        f"Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')}",
    ]
    if in_reply_to:
        headers += [f"In-Reply-To: {in_reply_to}", f"References: {in_reply_to}"]
    for key, value in (extra or {}).items():
        headers.append(f"{key}: {value}")
    return ("\r\n".join(headers) + "\r\n\r\n" + body).encode("utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.aletra = onboard("Kinetra Mobility")
        self.cedarline = onboard("Cedarline")
        with storage.unit_of_work() as conn:
            accounts.ensure_account(conn, self.aletra, "sales@kinetramobility.test")
            accounts.ensure_account(conn, self.cedarline, "hello@demostone.test")

    def outbound(self, lead_id: str, brand: str, message_id: str, sender: str = "sales@kinetramobility.test",
                 recipient: str = "buyer@example.test") -> None:
        with storage.unit_of_work() as conn:
            inbox.record_message(conn, brand, {
                "message_id": message_id, "in_reply_to": "", "references": [], "subject": "Intro",
                "sender": sender, "recipient": recipient, "sent_at": domain.iso(), "received_at": "",
                "body": "Intro", "body_sha256": "h",
            }, direction="outbound", lead_id=lead_id, evidence_level="smtp_accepted")


class ClassifyKindTests(Base):
    def test_auto_reply_headers(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test", "Re: Intro",
                                           "I am away", extra={"Auto-Submitted": "auto-replied"}))
        self.assertEqual(inbox.classify_kind(parsed), "auto_reply")

    def test_out_of_office_subject(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test",
                                           "Out of office: back Monday", "away"))
        self.assertEqual(inbox.classify_kind(parsed), "auto_reply")

    def test_bounce_from_mailer_daemon(self):
        parsed = inbox.parse_message(reply("mailer-daemon@example.test", "sales@kinetramobility.test",
                                           "Undelivered Mail Returned to Sender", "failure"))
        self.assertEqual(inbox.classify_kind(parsed), "bounce")

    def test_bounce_by_content_type(self):
        parsed = inbox.parse_message(reply("postmaster@example.test", "sales@kinetramobility.test",
                                           "Delivery Status Notification (Failure)", "x",
                                           extra={"Content-Type": "multipart/report; report-type=delivery-status"}))
        self.assertEqual(inbox.classify_kind(parsed), "bounce")

    def test_human_message(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test",
                                           "Re: Intro", "Tertarik, kirim penawaran ya"))
        self.assertEqual(inbox.classify_kind(parsed), "human")


class MatchTests(Base):
    def setUp(self):
        super().setUp()
        self.lead = discover("Kinetra Mobility", "Harborline Logistics", "buyer@example.test")
        self.outbound(self.lead, self.aletra, "<out-1@kinetramobility.test>")

    def test_thread_match_wins(self):
        parsed = inbox.parse_message(reply("someone-else@example.test", "sales@kinetramobility.test",
                                           "Re: Intro", "Kirim penawaran", "<out-1@kinetramobility.test>"))
        with storage.read_only() as conn:
            lead_id, reason, review = inbox.find_lead_for(conn, self.aletra, parsed)
        self.assertEqual((lead_id, reason, review), (self.lead, "thread", ""))

    def test_ambiguous_thread_goes_to_review(self):
        other = discover("Kinetra Mobility", "Second Co", "second@example.test")
        self.outbound(other, self.aletra, "<out-2@kinetramobility.test>", recipient="second@example.test")
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test", "Re: Intro",
                                           "hello", extra={"References": "<out-1@kinetramobility.test> <out-2@kinetramobility.test>"}))
        with storage.read_only() as conn:
            lead_id, _reason, review = inbox.find_lead_for(conn, self.aletra, parsed)
        self.assertEqual(lead_id, "")
        self.assertEqual(review, "ambiguous_thread")

    def test_sender_fallback_requires_our_mailbox(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "someone@elsewhere.test", "Intro", "hello"))
        with storage.read_only() as conn:
            _lead, _reason, review = inbox.find_lead_for(conn, self.aletra, parsed)
        self.assertEqual(review, "recipient_not_mailbox")

    def test_sender_fallback_when_unique(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test", "Intro", "hello"))
        with storage.read_only() as conn:
            lead_id, reason, review = inbox.find_lead_for(conn, self.aletra, parsed)
        self.assertEqual((lead_id, reason, review), (self.lead, "sender", ""))

    def test_ambiguous_sender_goes_to_review(self):
        twin = discover("Kinetra Mobility", "Twin Co", "twin@example.test")
        with storage.unit_of_work() as conn:
            conn.execute("UPDATE leads SET email='buyer@example.test' WHERE id=?", (twin,))
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test", "Intro", "hello"))
        with storage.read_only() as conn:
            _lead, _reason, review = inbox.find_lead_for(conn, self.aletra, parsed)
        self.assertEqual(review, "ambiguous_sender")

    def test_unknown_sender_goes_to_review_and_is_recorded(self):
        parsed = inbox.parse_message(reply("stranger@example.test", "sales@kinetramobility.test", "Intro", "hello"))
        with storage.unit_of_work() as conn:
            result = inbox.sync(conn, self.aletra, [reply("stranger@example.test", "sales@kinetramobility.test",
                                                          "Intro", "hello")])
            queue = storage.list_review(conn, self.aletra)
        self.assertEqual(result["matched"], [])
        self.assertEqual(result["review"][0]["reason"], "unknown_sender")
        self.assertEqual(len(queue), 1)

    def test_cross_brand_mail_never_matches(self):
        parsed = inbox.parse_message(reply("buyer@example.test", "sales@kinetramobility.test", "Intro", "hello"))
        with storage.read_only() as conn:
            lead_id, _reason, review = inbox.find_lead_for(conn, self.cedarline, parsed)
        self.assertEqual(lead_id, "")
        self.assertEqual(review, "recipient_not_mailbox")


class KindEffectTests(Base):
    def setUp(self):
        super().setUp()
        self.lead = discover("Kinetra Mobility", "Harborline Logistics", "buyer@example.test")
        self.outbound(self.lead, self.aletra, "<out-1@kinetramobility.test>")

    def _sync(self, raw: bytes):
        with storage.unit_of_work() as conn:
            return inbox.sync(conn, self.aletra, [raw])

    def test_auto_reply_does_not_mark_replied(self):
        result = self._sync(reply("buyer@example.test", "sales@kinetramobility.test", "Automatic reply: away",
                                  "I am out of office", "<out-1@kinetramobility.test>",
                                  extra={"Auto-Submitted": "auto-replied"}))
        self.assertTrue(result["matched"][0]["lifecycle_unchanged"])
        with storage.read_only() as conn:
            lead = storage.get_lead(conn, self.lead)
            hot = views.hot_prospects(self.aletra)
        self.assertEqual(lead["replied_at"], "")
        self.assertNotEqual(lead["pipeline_status"], "replied")
        self.assertEqual(hot["count"], 0)

    def test_bounce_marks_delivery_and_keeps_status(self):
        self._sync(reply("mailer-daemon@example.test", "sales@kinetramobility.test", "Undelivered Mail",
                         "failure", "<out-1@kinetramobility.test>"))
        with storage.read_only() as conn:
            row = conn.execute("SELECT delivery_state FROM messages WHERE message_id='<out-1@kinetramobility.test>'").fetchone()
            lead = storage.get_lead(conn, self.lead)
        self.assertEqual(row["delivery_state"], "bounced")
        self.assertNotEqual(lead["pipeline_status"], "replied")


class CursorTests(Base):
    def test_uidvalidity_change_forces_resync(self):
        plan = inbox.next_cursor("100", 42, "200", [1, 2, 3])
        self.assertTrue(plan["resync"])
        self.assertEqual(plan["last_uid"], 0)

    def test_incremental_cursor_is_saved_and_survives_restart(self):
        with storage.unit_of_work() as conn:
            storage.save_cursor(conn, self.aletra, "acct_1", "777", 15)
        storage.set_data_dir(Path(self.tmp.name))  # simulate a restart: new connections, same file
        with storage.read_only() as conn:
            cursor = storage.get_cursor(conn, self.aletra, "acct_1")
        self.assertEqual(cursor["uidvalidity"], "777")
        self.assertEqual(cursor["last_uid"], 15)

    def test_resync_after_restart_does_not_duplicate_messages(self):
        lead = discover("Kinetra Mobility", "Cursor Co", "cursor@example.test")
        self.outbound(lead, self.aletra, "<out-c@kinetramobility.test>", recipient="cursor@example.test")
        raw = reply("cursor@example.test", "sales@kinetramobility.test", "Re: Intro", "Kirim penawaran",
                    "<out-c@kinetramobility.test>")
        with storage.unit_of_work() as conn:
            first = inbox.sync(conn, self.aletra, [raw])
            storage.save_cursor(conn, self.aletra, "acct_1", "9", 30)
        storage.set_data_dir(Path(self.tmp.name))
        with storage.unit_of_work() as conn:
            second = inbox.sync(conn, self.aletra, [raw])
            total = conn.execute("SELECT COUNT(*) FROM messages WHERE lead_id=?", (lead,)).fetchone()[0]
        self.assertEqual(len(first["matched"]), 1)
        self.assertEqual(len(second["matched"]), 0)
        self.assertEqual(len(second["duplicates"]), 1)
        self.assertEqual(total, 2)  # one outbound + one inbound


class PolicyTests(Base):
    def test_policy_is_per_brand(self):
        with storage.unit_of_work() as conn:
            followstate.set_policy(conn, self.aletra, 2, 2, 10)
            followstate.set_policy(conn, self.cedarline, 7, 5, 40)
        with storage.read_only() as conn:
            a = followstate.policy_for(conn, self.aletra)
            m = followstate.policy_for(conn, self.cedarline)
        self.assertEqual(a["followup_days"], 2)
        self.assertEqual(m["followup_days"], 7)
        self.assertEqual(m["max_attempts"], 5)

    def test_reply_stops_scheduled_followups(self):
        lead = discover("Kinetra Mobility", "Stop Co", "stop@example.test")
        with storage.unit_of_work() as conn:
            conn.execute(
                "INSERT INTO followups(id, business_id, lead_id, draft_id, action, reason, due_on, status,"
                " send_recommended, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("fu_sched", self.aletra, lead, "", "follow_up", "no reply", "2026-11-10", "scheduled", 1, domain.iso()))
        self.outbound(lead, self.aletra, "<out-s@kinetramobility.test>", recipient="stop@example.test")
        with storage.unit_of_work() as conn:
            inbox.sync(conn, self.aletra, [reply("stop@example.test", "sales@kinetramobility.test", "Re: Intro",
                                                 "Tertarik", "<out-s@kinetramobility.test>")])
            status = conn.execute("SELECT status FROM followups WHERE id='fu_sched'").fetchone()["status"]
        self.assertEqual(status, "stopped")


class HotEvidenceTests(Base):
    def test_neutral_reply_is_not_hot(self):
        lead = discover("Kinetra Mobility", "Neutral Co", "neutral@example.test")
        self.outbound(lead, self.aletra, "<out-n@kinetramobility.test>", recipient="neutral@example.test")
        with storage.unit_of_work() as conn:
            inbox.sync(conn, self.aletra, [reply("neutral@example.test", "sales@kinetramobility.test",
                                                 "Re: Intro", "Terima kasih infonya.", "<out-n@kinetramobility.test>")])
        hot = views.hot_prospects(self.aletra)
        self.assertEqual(hot["count"], 0)
        with storage.read_only() as conn:
            queue = storage.list_review(conn, self.aletra)
        self.assertEqual([row["reason"] for row in queue], ["uncertain_intent"])

    def test_interested_reply_is_hot_with_evidence(self):
        lead = discover("Kinetra Mobility", "Warm Co", "warm@example.test")
        self.outbound(lead, self.aletra, "<out-w@kinetramobility.test>", recipient="warm@example.test")
        with storage.unit_of_work() as conn:
            inbox.sync(conn, self.aletra, [reply("warm@example.test", "sales@kinetramobility.test", "Re: Intro",
                                                 "Tertarik, boleh kirim penawaran 12 unit?", "<out-w@kinetramobility.test>")])
        hot = views.hot_prospects(self.aletra)
        self.assertEqual(hot["count"], 1)
        self.assertEqual(hot["prospects"][0]["lead_id"], lead)
        self.assertTrue(hot["prospects"][0]["interest_evidence"])


class DiscoveryToolPathTests(Base):
    def test_agent_style_discovery_writes_to_the_database(self):
        """Tool path with an injected search dispatcher and a stubbed page fetch.

        This exercises tools -> discovery -> storage exactly as an agent call would, but the
        gateway itself is not involved; that boundary stays unproven until a real session runs it.
        """
        import fetch as fetch_module

        calls: list[tuple] = []

        class FakeCtx:
            def dispatch_tool(self, name, args):
                calls.append((name, args))
                return {"results": [{"url": "https://example.test/prospect"}]}

        original = fetch_module.fetch_public_url
        fetch_module.fetch_public_url = lambda url: {
            "ok": True, "url": url, "fetched": True,
            "text": ("Company: Nusantara Fleet\nEmail: ops@nusantara.example\nRole: Procurement\n"
                     "Segment: Corporate fleet\nCountry: Jakarta\nWhy: opened a 20-unit tender\n"),
        }
        tools.bind(FakeCtx())
        self.addCleanup(tools.bind, None)
        self.addCleanup(setattr, fetch_module, "fetch_public_url", original)

        result = json.loads(tools._discover({
            "brand": "Kinetra Mobility", "authorized": True, "use_hermes_search": True,
            "query": "perusahaan fleet jakarta",
        }))
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(result.get("prospects"), result)
        self.assertTrue(calls and calls[0][0] == "web_search")
        self.assertFalse(result.get("sent"))
        with storage.read_only() as conn:
            saved = conn.execute("SELECT * FROM leads WHERE company=?", ("Nusantara Fleet",)).fetchone()
        self.assertIsNotNone(saved)
        self.assertEqual(saved["email"], "ops@nusantara.example")
        self.assertTrue(saved["source_url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()


class ImapSettingsTests(Base):
    def test_secret_fields_are_never_persisted(self):
        with storage.unit_of_work() as conn:
            saved = storage.save_imap_settings(conn, self.aletra, {
                "host": "imap.example.test", "port": 993, "username": "sales@kinetramobility.test",
                "password": "should-not-be-stored", "token": "nope", "use_ssl": True,
            })
            row = conn.execute("SELECT * FROM imap_settings WHERE business_id=?", (self.aletra,)).fetchone()
        dumped = json.dumps(dict(row))
        self.assertNotIn("should-not-be-stored", dumped)
        self.assertNotIn("nope", dumped)
        self.assertEqual(saved["host"], "imap.example.test")
        self.assertEqual(saved["username"], "sales@kinetramobility.test")
