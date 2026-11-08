"""Send-path safety: consent and lifecycle are read at send time, not at draft time.

The gap these cover: `/salespilot-send` checked suppression, the daily cap and the repeat window, but
not the lead's current lifecycle. A draft written before a refusal could therefore still be sent after
the repeat window passed, and a "not interested" reply was a label rather than a suppression. These
tests pin the fail-closed behaviour on an isolated temp database; nothing is mailed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import commands
import inbox
import mail
import pipeline
import storage
import tools


def _call(fn, args):
    return json.loads(fn(args))


class SendSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        seeded = _call(tools.import_customers, {"seed_demo": True})
        self.business_id = seeded["business_id"]
        self.lead_id = next(item["id"] for item in seeded["prospects"] if item["decision"] == "qualified")
        self.draft_id = _call(tools.draft_outreach, {"lead_id": self.lead_id, "channel": "email"})["draft"]["id"]
        saved = _call(commands.configure_mail, {
            "business_id": self.business_id,
            "host": "smtp.example.com",
            "port": 587,
            "security": "starttls",
            "from_address": "nia@example.com",
            "from_name": "Nia Demo",
            "signature_text": "Nia Demo, Cedarline",
        })
        self.assertTrue(saved["ok"])
        self.calls = []

        def transport(account, username, password, message):
            self.calls.append({"recipient": message["To"]})
            return 250, False

        mail.set_transport_for_tests(transport)

        class Willing:
            def ask_choice(self, question, choices):
                return "send"

        commands.bind(Willing())

    def tearDown(self):
        mail.set_transport_for_tests(None)
        commands.bind(None)
        storage.set_data_dir(None)
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------------------------------

    def _lead(self):
        with storage.unit_of_work() as conn:
            return storage.get_lead(conn, self.lead_id)

    def _status(self, status):
        with storage.unit_of_work() as conn:
            result = pipeline.set_status(conn, self.business_id, self.lead_id, status)
        self.assertTrue(result["ok"], result)
        return result

    def _send(self):
        return json.loads(commands.slash_send(self.draft_id))

    def _reply(self, body, subject="Re: your enquiry"):
        parsed = {
            "message_id": "<reply-1@example.invalid>",
            "sender": "buyer@example.invalid",
            "recipient": "nia@example.com",
            "subject": subject,
            "body": body,
            "received_at": "2026-11-08T09:00:00+00:00",
            "headers": {},
        }
        with storage.unit_of_work() as conn:
            return inbox.apply_reply(conn, self.business_id, self.lead_id, parsed)

    def _suppression_reason(self, email):
        with storage.unit_of_work() as conn:
            row = conn.execute(
                "SELECT reason FROM suppressions WHERE business_id=? AND email_key=?",
                (self.business_id, email.strip().lower()),
            ).fetchone()
        return row["reason"] if row else ""

    # -- lifecycle gates -------------------------------------------------------------------------

    def test_not_interested_blocks_a_draft_written_before_the_refusal(self):
        self._status("not_interested")
        blocked = self._send()
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["code"], "lead_not_interested")
        self.assertFalse(blocked["sent"])
        self.assertEqual(self.calls, [], "nothing may leave the process")

    def test_do_not_contact_blocks_the_send(self):
        self._status("do_not_contact")
        blocked = self._send()
        self.assertEqual(blocked["code"], "lead_do_not_contact")
        self.assertEqual(self.calls, [])

    def test_archived_and_deleted_leads_block_the_send(self):
        with storage.unit_of_work() as conn:
            storage.set_pipeline_fields(conn, self.lead_id, archived=1)
        self.assertEqual(self._send()["code"], "lead_archived")
        self.assertEqual(self.calls, [])

        with storage.unit_of_work() as conn:
            storage.set_pipeline_fields(conn, self.lead_id, deleted_at="2026-11-08T00:00:00+00:00")
        self.assertEqual(self._send()["code"], "lead_deleted")
        self.assertEqual(self.calls, [])

    def test_recorded_bounce_blocks_the_send(self):
        lead = self._lead()
        with storage.unit_of_work() as conn:
            inbox.record_message(conn, self.business_id, {
                "message_id": "<out-1@example.invalid>",
                "sender": "nia@example.com",
                "recipient": lead["email"],
                "subject": "Earlier attempt",
                "sent_at": "2026-11-07T08:00:00+00:00",
                "body": "Earlier attempt",
            }, direction="outbound", lead_id=self.lead_id, delivery_state="bounced")
            self.assertTrue(storage.bounced_recipient(conn, self.business_id, lead["email"]))
        blocked = self._send()
        self.assertEqual(blocked["code"], "recipient_bounced")
        self.assertEqual(self.calls, [])

    def test_blocked_lead_is_reported_as_blocked_on_the_row(self):
        self._status("not_interested")
        with storage.unit_of_work() as conn:
            row = pipeline.public_row(storage.get_lead(conn, self.lead_id))
        self.assertTrue(row["outreach_blocked"], "the UI must not offer a send that will be refused")

    # -- refusal vs neutral ----------------------------------------------------------------------

    def test_negative_reply_suppresses_and_records_the_reason(self):
        lead = self._lead()
        result = self._reply("Thanks, but we are not interested.")
        self.assertEqual(result["intent"], "not_interested")
        self.assertEqual(self._lead()["pipeline_status"], "not_interested")
        self.assertEqual(self._suppression_reason(lead["email"]), "not_interested")
        self.assertEqual(self._send()["code"], "lead_not_interested")
        self.assertEqual(self.calls, [])

    def test_unsubscribe_reply_suppresses_as_do_not_contact(self):
        lead = self._lead()
        result = self._reply("Please unsubscribe me.")
        self.assertEqual(result["intent"], "unsubscribe")
        self.assertEqual(self._suppression_reason(lead["email"]), "unsubscribe")
        self.assertEqual(self._lead()["pipeline_status"], "do_not_contact")
        self.assertEqual(self._send()["code"], "lead_do_not_contact")

    def test_neutral_or_timing_later_reply_does_not_suppress(self):
        lead = self._lead()
        result = self._reply("We are reviewing suppliers next quarter, ping me in March.")
        self.assertEqual(result["intent"], "neutral")
        self.assertEqual(self._suppression_reason(lead["email"]), "", "timing-later is not a refusal")
        self.assertNotEqual(self._lead()["pipeline_status"], "not_interested")
        with storage.unit_of_work() as conn:
            review = conn.execute(
                "SELECT 1 FROM inbox_review WHERE business_id=? AND reason='uncertain_intent'", (self.business_id,)
            ).fetchone()
        self.assertIsNotNone(review, "an undecidable reply opens a review instead of a refusal")

    def test_marking_not_interested_from_the_page_suppresses(self):
        lead = self._lead()
        self._status("not_interested")
        self.assertEqual(self._suppression_reason(lead["email"]), "not_interested")

    # -- approval gate unchanged -----------------------------------------------------------------

    def test_human_approval_is_still_required(self):
        commands.bind(None)
        unbound = self._send()
        self.assertEqual(unbound["code"], "host_approval_unavailable")
        self.assertEqual(self.calls, [], "no asker means no send")

        class Declining:
            def ask_choice(self, question, choices):
                return "cancel"

        commands.bind(Declining())
        self.assertEqual(self._send()["code"], "host_declined")
        self.assertEqual(self.calls, [])

    def test_healthy_lead_still_sends_once(self):
        first = self._send()
        self.assertTrue(first["smtp_accepted"])
        self.assertEqual(len(self.calls), 1)
        again = self._send()
        self.assertTrue(again.get("reused"))
        self.assertEqual(len(self.calls), 1, "a retry must not send twice")


if __name__ == "__main__":
    unittest.main()
