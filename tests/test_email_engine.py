"""Email-first engine: accounts, inbound replies, follow-up state."""

from __future__ import annotations

import json
import sqlite3
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


def onboard(name: str, offer: str) -> str:
    saved = json.loads(tools.onboard_business({
        "name": name, "offer": offer, "offer_short": offer[:50],
        "default_cta": "Reply if this matches a current project.",
    }))
    return saved["business"]["id"]


def discover(brand: str, company: str, email: str) -> str:
    source = {
        "url": "https://example.test/brief",
        "text": f"Company: {company}\nEmail: {email}\nWhy: published a lobby brief\nURL: https://example.test/brief\n",
        "permitted": True,
    }
    found = json.loads(tools.pipeline_action({"action": "discover", "brand": brand, "sources": [source]}))
    return (found.get("prospect") or {}).get("id", "")


def raw_reply(sender: str, to: str, subject: str, body: str, in_reply_to: str = "", message_id: str = "<reply@example.test>") -> bytes:
    headers = [
        f"From: {sender}",
        f"To: {to}",
        f"Subject: {subject}",
        f"Message-ID: {message_id}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=utf-8",
        "Date: Tue, 04 Nov 2026 09:15:00 +0700",
    ]
    if in_reply_to:
        headers.append(f"In-Reply-To: {in_reply_to}")
        headers.append(f"References: {in_reply_to}")
    return ("\r\n".join(headers) + "\r\n\r\n" + body).encode("utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.aletra = onboard("Kinetra Mobility", "Electric MPV fleet sales.")
        self.cedarline = onboard("Cedarline", "Lighting and fixture specification.")


class AccountTests(Base):
    def test_one_account_per_saved_sender_and_no_cross_brand(self):
        with storage.unit_of_work() as conn:
            row = accounts.ensure_account(conn, self.aletra, "sales@kinetramobility.test", display_name="Kinetra Sales")
            same = accounts.ensure_account(conn, self.aletra, "SALES@kinetramobility.test")
            other, reason = accounts.resolve(conn, self.cedarline)
        self.assertEqual(row["id"], same["id"], "address must be unique per brand")
        self.assertIsNone(other)
        self.assertEqual(reason, "no_account")

    def test_alias_addresses_stay_separate_rows(self):
        with storage.unit_of_work() as conn:
            a = accounts.ensure_account(conn, self.aletra, "sales@kinetramobility.test")
            b = accounts.ensure_account(conn, self.aletra, "fleet@kinetramobility.test")
            chosen, reason = accounts.resolve(conn, self.aletra)
            listed = accounts.list_accounts(conn, self.aletra)
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(len(listed), 2)
        self.assertEqual(reason, "multiple_accounts")
        self.assertEqual(chosen["credential_slot"], "default")

    def test_disabled_account_is_refused(self):
        with storage.unit_of_work() as conn:
            row = accounts.ensure_account(conn, self.aletra, "sales@kinetramobility.test")
            conn.execute("UPDATE accounts SET status='disabled' WHERE id=?", (row["id"],))
            account, reason = accounts.resolve(conn, self.aletra, "sales@kinetramobility.test")
        self.assertIsNone(account)
        self.assertEqual(reason, "account_disabled")


class ReplyTests(Base):
    def setUp(self):
        super().setUp()
        self.lead = discover("Kinetra Mobility", "Harborline Studio", "ops@harborline.example")
        with storage.unit_of_work() as conn:
            inbox.record_message(conn, self.aletra, {
                "message_id": "<out-1@kinetramobility.test>", "in_reply_to": "", "references": [],
                "subject": "MPV untuk proyek Anda", "sender": "sales@kinetramobility.test",
                "recipient": "ops@harborline.example", "sent_at": domain.iso(), "received_at": "",
                "body": "Intro", "body_sha256": "x",
            }, direction="outbound", lead_id=self.lead, delivery_state="accepted", evidence_level="smtp_accepted")

    def test_reply_is_matched_by_thread_and_moves_lifecycle(self):
        raw = [raw_reply("ops@harborline.example", "sales@kinetramobility.test", "Re: MPV",
                         "Tertarik, boleh kirim penawaran untuk 12 unit?", "<out-1@kinetramobility.test>")]
        with storage.unit_of_work() as conn:
            result = inbox.sync(conn, self.aletra, raw)
        self.assertEqual(len(result["matched"]), 1)
        self.assertEqual(result["matched"][0]["intent"], "interested")
        with storage.read_only() as conn:
            lead = storage.get_lead(conn, self.lead)
            messages = storage.list_messages(conn, self.aletra, self.lead, 10)
        self.assertEqual(lead["pipeline_status"], "replied")
        self.assertTrue(lead["replied_at"])
        self.assertEqual(lead["needs_human"], 1)
        inbound = [m for m in messages if m["direction"] == "inbound"]
        self.assertEqual(inbound[0]["evidence_level"], "imap_verified")

    def test_second_sync_of_the_same_message_is_a_noop(self):
        raw = [raw_reply("ops@harborline.example", "sales@kinetramobility.test", "Re: MPV", "Boleh kirim katalog", "<out-1@kinetramobility.test>")]
        with storage.unit_of_work() as conn:
            inbox.sync(conn, self.aletra, raw)
        with storage.unit_of_work() as conn:
            again = inbox.sync(conn, self.aletra, raw)
        self.assertEqual(again["matched"], [])
        self.assertEqual(len(again["duplicates"]), 1)

    def test_unsubscribe_suppresses_and_stops_followups(self):
        with storage.unit_of_work() as conn:
            conn.execute(
                "INSERT INTO followups(id, business_id, lead_id, draft_id, action, reason, due_on, status,"
                " send_recommended, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("fu_1", self.aletra, self.lead, "", "follow_up", "no reply", "2026-11-01", "recommended", 1, domain.iso()),
            )
        raw = [raw_reply("ops@harborline.example", "sales@kinetramobility.test", "Re: MPV",
                         "Please unsubscribe me. Jangan hubungi lagi.", "<out-1@kinetramobility.test>")]
        with storage.unit_of_work() as conn:
            result = inbox.sync(conn, self.aletra, raw)
        self.assertEqual(result["matched"][0]["intent"], "unsubscribe")
        with storage.read_only() as conn:
            lead = storage.get_lead(conn, self.lead)
            suppressed = storage.is_suppressed(conn, self.aletra, "ops@harborline.example")
            followup = conn.execute("SELECT status FROM followups WHERE id='fu_1'").fetchone()["status"]
        self.assertEqual(lead["pipeline_status"], "do_not_contact")
        self.assertTrue(suppressed)
        self.assertEqual(followup, "stopped")  # a reply stops queued follow-ups outright

    def test_unmatched_sender_is_reported_not_guessed(self):
        raw = [raw_reply("stranger@elsewhere.example", "sales@kinetramobility.test", "Hello", "interested")]
        with storage.unit_of_work() as conn:
            result = inbox.sync(conn, self.aletra, raw)
        self.assertEqual(result["matched"], [])
        self.assertEqual(len(result["unmatched"]), 1)
        self.assertEqual(result["unmatched"][0]["sender"], "stranger@elsewhere.example")

    def test_preview_classifies_without_writing(self):
        with storage.unit_of_work() as conn:
            before = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            preview = inbox.run(conn, self.aletra, {"action": "preview", "text": "Tidak tertarik, terima kasih"})
            after = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(preview["intent"], "not_interested")
        self.assertEqual(before, after)

    def test_sync_refuses_when_imap_is_not_configured(self):
        with storage.unit_of_work() as conn:
            result = inbox.run(conn, self.aletra, {"action": "sync"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "imap_not_configured")


class FollowStateTests(Base):
    def _touch(self, lead_id: str, days_ago: int, direction: str = "outbound", message_id: str = "") -> None:
        when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")
        with storage.unit_of_work() as conn:
            inbox.record_message(conn, self.aletra, {
                "message_id": message_id or f"<m{lead_id}{days_ago}{direction}@x>", "in_reply_to": "", "references": [],
                "subject": "s", "sender": "sales@kinetramobility.test", "recipient": "a@b.example",
                "sent_at": when if direction == "outbound" else "", "received_at": when if direction == "inbound" else "",
                "body": "body", "body_sha256": "h",
            }, direction=direction, lead_id=lead_id,
                evidence_level="smtp_accepted" if direction == "outbound" else "imap_verified")

    def test_states_are_computed_from_history(self):
        fresh = discover("Kinetra Mobility", "Fresh Co", "a@fresh.example")
        due = discover("Kinetra Mobility", "Due Co", "b@due.example")
        answered = discover("Kinetra Mobility", "Replied Co", "c@replied.example")
        self._touch(due, 5)
        self._touch(answered, 10)
        self._touch(answered, 3, direction="inbound")

        with storage.read_only() as conn:
            policy = followstate.policy_for(conn, self.aletra)
            s_fresh = followstate.state_for(conn, self.aletra, storage.get_lead(conn, fresh), policy)
            s_due = followstate.state_for(conn, self.aletra, storage.get_lead(conn, due), policy)
            s_answered = followstate.state_for(conn, self.aletra, storage.get_lead(conn, answered), policy)
        self.assertEqual(s_fresh["state"], "not_contacted")
        self.assertEqual(s_due["state"], "followup_due")
        self.assertEqual(s_answered["state"], "replied")
        self.assertTrue(s_answered["paused"])

    def test_two_old_attempts_become_cold_not_deleted(self):
        cold = discover("Kinetra Mobility", "Cold Co", "cold@example.test")
        self._touch(cold, 30, message_id="<old1@x>")
        self._touch(cold, 25, message_id="<old2@x>")
        with storage.read_only() as conn:
            policy = followstate.policy_for(conn, self.aletra)
            state = followstate.state_for(conn, self.aletra, storage.get_lead(conn, cold), policy)
            still_there = storage.get_lead(conn, cold)
        self.assertEqual(state["state"], "cold")
        self.assertIsNotNone(still_there)

    def test_board_groups_every_prospect(self):
        discover("Kinetra Mobility", "Board Co", "board@example.test")
        with storage.read_only() as conn:
            board = followstate.board(conn, self.aletra)
        self.assertTrue(board["ok"])
        self.assertEqual(sum(board["counts"].values()), 1)

    def test_disabled_account_never_sends(self):
        target = discover("Kinetra Mobility", "No Send Co", "nosend@example.test")
        with storage.unit_of_work() as conn:
            accounts.ensure_account(conn, self.aletra, "sales@kinetramobility.test")
        with storage.read_only() as conn:
            from pipeline import list_prospects
            rows, _ = list_prospects(conn, self.aletra, limit=50)
        self.assertTrue(any(row["id"] == target for row in rows))


class HotViewTests(Base):
    def test_reply_puts_the_contact_in_hot_prospects(self):
        lead = discover("Kinetra Mobility", "Warm Co", "warm@example.test")
        with storage.unit_of_work() as conn:
            inbox.record_message(conn, self.aletra, {
                "message_id": "<out-warm@x>", "in_reply_to": "", "references": [], "subject": "Intro",
                "sender": "sales@kinetramobility.test", "recipient": "warm@example.test",
                "sent_at": domain.iso(), "received_at": "", "body": "intro", "body_sha256": "h",
            }, direction="outbound", lead_id=lead, evidence_level="smtp_accepted")
            inbox.sync(conn, self.aletra, [raw_reply("warm@example.test", "sales@kinetramobility.test",
                                                     "Re: Intro", "Kirim penawaran ya", "<out-warm@x>")])
        hot = views.hot_prospects(self.aletra)
        self.assertEqual(hot["count"], 1)
        self.assertEqual(hot["prospects"][0]["lead_id"], lead)
        self.assertTrue(hot["prospects"][0]["reply_excerpt"])
        inbox_view = views.pipeline_view(self.aletra)
        self.assertIn("followup_counts", inbox_view)


if __name__ == "__main__":
    unittest.main()
