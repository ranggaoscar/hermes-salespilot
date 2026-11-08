"""Phase 4 mail gates. No external inbox is contacted."""

from __future__ import annotations

import json
import ssl
import tempfile
import unittest
from pathlib import Path

import commands
import mail
import storage
import tools


def _call(fn, args):
    return json.loads(fn(args))


class MailSecurityTests(unittest.TestCase):
    def tearDown(self):
        mail.set_transport_for_tests(None)
        commands.bind(None)

    def test_tls_context_validates_certificates(self):
        context = mail.tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_headers_and_html_are_contained(self):
        with self.assertRaises(ValueError):
            mail.header_value("Ann\r\nBcc: evil@example.com", "from_name")
        with self.assertRaises(ValueError):
            mail.validate_account({"host": "169.254.169.254", "from_address": "a@example.com"})
        account = mail.validate_account({
            "host": "smtp.example.com",
            "from_address": "nia@example.com",
            "signature_text": "<script>alert(1)</script>",
        })
        self.assertNotIn("<script>", account["signature_html"])
        self.assertIn("&lt;script&gt;", account["signature_html"])

    def test_signature_keeps_its_line_breaks(self):
        """The Settings signature box is multi-line; a two-line sign-off must save, not fail as a header."""
        account = mail.validate_account({
            "host": "smtp.example.com",
            "from_address": "nia@example.com",
            "signature_text": "Best regards,\r\nNia Demo\x00",
        })
        self.assertEqual(account["signature_text"], "Best regards,\nNia Demo")
        self.assertEqual(account["signature_html"], "<p>Best regards,<br>\nNia Demo</p>")
        with self.assertRaises(ValueError):
            mail.validate_account({"host": "smtp.example.com", "from_address": "nia@example.com",
                                   "from_name": "Nia\r\nBcc: x@example.com"})


class SlashSendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage.set_data_dir(Path(self.tmp.name))
        seeded = _call(tools.import_customers, {"seed_demo": True})
        self.business_id = seeded["business_id"]
        self.lead_id = next(item["id"] for item in seeded["prospects"] if item["decision"] == "qualified")
        self.draft = _call(tools.draft_outreach, {"lead_id": self.lead_id, "channel": "email"})
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
        self.assertNotIn("password", json.dumps(saved))
        self.calls = []

        def transport(account, username, password, message):
            self.calls.append({"username": username, "has_message": message is not None})
            return 250, False

        mail.set_transport_for_tests(transport)

    def tearDown(self):
        mail.set_transport_for_tests(None)
        commands.bind(None)
        storage.set_data_dir(None)
        self.tmp.cleanup()

    def test_password_argument_is_refused(self):
        refused = _call(commands.configure_mail, {"password": "secret-value", "business_id": self.business_id})
        self.assertEqual(refused["code"], "secret_in_args")
        self.assertNotIn("secret-value", json.dumps(refused))

    def test_tool_approval_and_unbound_choice_do_not_send(self):
        approval = _call(tools.request_approval, {
            "draft_id": self.draft["draft"]["id"],
            "decision": "approve",
            "human_confirmed": True,
        })
        self.assertFalse(approval["sent"])
        self.assertEqual(approval["code"], "host_approval_unavailable")
        unbound = json.loads(commands.slash_send(self.draft["draft"]["id"]))
        self.assertEqual(unbound["code"], "host_approval_unavailable")
        self.assertEqual(self.calls, [])

    def test_host_choice_sends_once_and_retry_does_not(self):
        class Host:
            def ask_choice(self, question, choices):
                return "send"

        commands.bind(Host())
        first = json.loads(commands.slash_send(self.draft["draft"]["id"]))
        self.assertTrue(first["smtp_accepted"])
        self.assertFalse(first["inbox_delivery_proven"])
        self.assertFalse(first["sent"])
        self.assertEqual(len(self.calls), 1)
        second = json.loads(commands.slash_send(self.draft["draft"]["id"]))
        self.assertTrue(second["reused"])
        self.assertEqual(len(self.calls), 1)

    def test_cancel_and_suppression_do_not_send(self):
        class Host:
            def ask_choice(self, question, choices):
                return "cancel"

        commands.bind(Host())
        denied = json.loads(commands.slash_send(self.draft["draft"]["id"]))
        self.assertEqual(denied["code"], "host_declined")
        self.assertEqual(self.calls, [])
        lead = None
        with storage.unit_of_work() as conn:
            lead = storage.get_lead(conn, self.lead_id)
        _call(commands.configure_mail, {
            "action": "suppress",
            "business_id": self.business_id,
            "email": lead["email"],
        })

        class Send:
            def ask_choice(self, question, choices):
                return "send"

        commands.bind(Send())
        blocked = json.loads(commands.slash_send(self.draft["draft"]["id"]))
        self.assertEqual(blocked["code"], "suppressed")
        self.assertEqual(self.calls, [])

    def test_real_asker_is_unbound_for_tool_context(self):
        from hermes_cli.plugin_choices import ask_choice, bind_asker

        self.assertIsNone(ask_choice("Send?", ["send", "cancel"]))
        with bind_asker(lambda question, labels: "send"):
            self.assertEqual(ask_choice("Send?", ["send", "cancel"]), "send")
