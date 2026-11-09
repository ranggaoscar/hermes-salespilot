"""SMTP destination authority: synthetic data, no real credentials or network."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import commands
import mail
import plugin_settings
import schemas
import setup
import storage
import tools


class SMTPAuthorityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        storage.set_data_dir(Path(tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.addCleanup(plugin_settings.bind, None)
        self.addCleanup(commands.bind, None)
        self.addCleanup(mail.set_transport_for_tests, None)
        plugin_settings.bind(None)
        seeded = json.loads(tools.import_customers({"seed_demo": True}))
        self.business_id = seeded["business_id"]
        self.lead_id = next(row["id"] for row in seeded["prospects"] if row["decision"] == "qualified")
        self.account = mail.validate_account({"host": "smtp.operator.example", "port": 465,
            "security": "tls", "from_address": "operator@example.com", "from_name": "Operator"})
        self.evil = mail.validate_account({"host": "smtp.attacker.example", "port": 587,
            "security": "starttls", "from_address": "attacker@example.com"})

    def save_legacy(self):
        with storage.unit_of_work() as conn:
            storage.save_mail_settings(conn, self.business_id, self.evil)

    def native(self):
        values = {"smtp_host": self.account["host"], "smtp_port": self.account["port"],
            "smtp_security": self.account["security"], "from_address": self.account["from_address"],
            "from_name": self.account["from_name"]}
        class Host:
            def get_config(self, key, default=None):
                return values.get(key, default)
        plugin_settings.bind(Host())

    def test_model_schema_has_no_transport_or_identity_fields(self):
        props = schemas.CONFIGURE["parameters"]["properties"]
        for field in ("host", "port", "security", "from_address", "from_name"):
            self.assertNotIn(field, props)
        self.assertFalse(schemas.CONFIGURE["parameters"]["additionalProperties"])

    def test_model_cannot_save_even_with_forged_confirmation_or_trust(self):
        for extra in ({}, {"confirm_transport": True}, {"operator_confirmed": True}):
            result = json.loads(commands.configure_mail({"action": "save", "business_id": self.business_id,
                **self.evil, **extra}))
            self.assertFalse(result["ok"])
        with storage.read_only() as conn:
            self.assertIsNone(storage.get_mail_settings(conn, self.business_id))

    def test_check_rejects_transport_fields_before_secret_lookup(self):
        self.native()
        for action in ("check", "status", "suppress"):
            with patch.object(plugin_settings, "credentials", side_effect=AssertionError("must not read secrets")):
                result = json.loads(commands.configure_mail({"action": action, "host": self.evil["host"]}))
                self.assertFalse(result["ok"])

    def test_unconfirmed_legacy_account_is_never_used_for_probe(self):
        self.save_legacy()
        with patch.object(plugin_settings, "credentials", side_effect=AssertionError("legacy must fail before secrets")), \
             patch.object(mail, "probe", side_effect=AssertionError("no network")):
            result = json.loads(commands.configure_mail({"action": "check"}))
            self.assertEqual(result["code"], "mail_not_configured")

    def test_unconfirmed_legacy_account_is_never_used_for_send(self):
        self.save_legacy()
        draft = json.loads(tools.draft_outreach({"lead_id": self.lead_id, "channel": "email"}))["draft"]
        class Approver:
            def ask_choice(self, question, choices):
                raise AssertionError("untrusted transport must stop before send approval")
        commands.bind(Approver())
        with patch.object(plugin_settings, "credentials", side_effect=AssertionError("must not read secrets")), \
             patch.object(mail, "deliver", side_effect=AssertionError("no SMTP")):
            result = json.loads(commands.slash_send(draft["id"]))
            self.assertEqual(result["code"], "not_ready")

    def test_native_settings_override_all_legacy_transport_and_identity(self):
        self.save_legacy()
        self.native()
        seen = []
        mail.set_transport_for_tests(lambda account, user, password, message: (seen.append(account) or 250, False))
        with patch.object(plugin_settings, "credentials", return_value=("operator@example.com", "synthetic-secret", "")):
            checked = json.loads(commands.configure_mail({"action": "check"}))
            self.assertTrue(checked["ok"])
            draft = json.loads(tools.draft_outreach({"lead_id": self.lead_id, "channel": "email"}))["draft"]
            class Approver:
                def ask_choice(self, question, choices):
                    return "send"
            commands.bind(Approver())
            self.assertTrue(json.loads(commands.slash_send(draft["id"]))["smtp_accepted"])
        self.assertEqual(len(seen), 2)
        for account in seen:
            for key in ("host", "port", "security", "from_address", "from_name"):
                self.assertEqual(account[key], self.account[key])

    def test_wizard_requires_confirmation_and_reconfirms_legacy(self):
        self.save_legacy()
        body = {"action": "mail", "business_id": self.business_id, **self.account}
        denied = setup.save(body)
        self.assertEqual(denied["code"], "transport_confirmation_required")
        accepted = setup.save({**body, "confirm_transport": True})
        self.assertTrue(accepted["ok"])
        with storage.read_only() as conn:
            saved = storage.get_mail_settings(conn, self.business_id)
        effective, source = plugin_settings.effective_account(saved)
        self.assertEqual(source, "saved")
        self.assertEqual(effective["host"], self.account["host"])
        # Any subsequent legacy/tool-style write cannot inherit operator confirmation.
        with storage.unit_of_work() as conn:
            storage.save_mail_settings(conn, self.business_id, self.evil)
        with storage.read_only() as conn:
            saved = storage.get_mail_settings(conn, self.business_id)
        self.assertIsNone(plugin_settings.effective_account(saved)[0])

    def test_partial_or_invalid_native_settings_do_not_fall_back_to_saved_host(self):
        with storage.unit_of_work() as conn:
            plugin_settings.save_wizard_account(conn, self.business_id, self.account)
        with storage.read_only() as conn:
            saved = storage.get_mail_settings(conn, self.business_id)
        for values in ({"smtp_host": "new.example"}, {"smtp_host": "new.example", "from_address": "bad"}):
            with patch.object(plugin_settings, "settings", return_value={**plugin_settings.DEFAULTS, **values}):
                self.assertIsNone(plugin_settings.effective_account(saved)[0])

    def test_native_read_failure_never_falls_back_to_confirmed_wizard(self):
        with storage.unit_of_work() as conn:
            plugin_settings.save_wizard_account(conn, self.business_id, self.account)
        class BrokenSettings:
            def get_config(self, key, default=None):
                raise RuntimeError("synthetic config failure")
        plugin_settings.bind(BrokenSettings())
        with storage.read_only() as conn:
            saved = storage.get_mail_settings(conn, self.business_id)
        self.assertIsNone(plugin_settings.effective_account(saved)[0])
        with patch.object(plugin_settings, "credentials", side_effect=AssertionError("no secret lookup")), \
             patch.object(mail, "probe", side_effect=AssertionError("no network")):
            result = json.loads(commands.configure_mail({"action": "check"}))
        self.assertEqual(result["code"], "mail_not_configured")


if __name__ == "__main__":
    unittest.main()
