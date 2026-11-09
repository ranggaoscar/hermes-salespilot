"""Native Hermes settings carry the SMTP secrets; the wizard never accepts a password."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import commands
import mail
import plugin_settings
import setup
import storage

MANIFEST = Path(__file__).resolve().parents[1] / "plugin.yaml"


def _schema() -> dict:
    from utils import fast_safe_load
    return (fast_safe_load(MANIFEST.read_text(encoding="utf-8")) or {}).get("config_schema") or {}


class ManifestTests(unittest.TestCase):
    def test_password_is_declared_as_a_secret_with_the_env_the_code_reads(self):
        schema = _schema()
        self.assertEqual(schema["smtp_password"]["type"], "secret")
        self.assertEqual(schema["smtp_password"]["env"], plugin_settings.SECRET_PASSWORD)
        self.assertEqual(schema["smtp_username"]["env"], plugin_settings.SECRET_USERNAME)

    def test_sender_identity_and_signature_are_declared(self):
        schema = _schema()
        for key in ("smtp_host", "smtp_port", "smtp_security", "from_address", "from_name", "signature_text"):
            self.assertIn(key, schema)

    def test_installed_hermes_renders_the_secret_type(self):
        try:
            from hermes_cli.plugins_manifest import _CONFIG_SCHEMA_TYPES
            from hermes_cli.plugins_settings import _field_type, secret_env_name
        except ImportError:
            self.skipTest("hermes_cli is not importable outside the installed app")
        self.assertIn("secret", _CONFIG_SCHEMA_TYPES)
        spec = _schema()["smtp_password"]
        self.assertEqual(_field_type(spec), "secret")
        self.assertEqual(secret_env_name(plugin_settings.PLUGIN_ID, "smtp_password", spec), "SALESPILOT_SMTP_PASSWORD")


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        storage.set_data_dir(Path(self.tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        self.addCleanup(setattr, plugin_settings, "settings", plugin_settings.settings)

    def _business(self) -> str:
        saved = setup.save({"action": "business", "name": "Stone Co", "website": "https://example.com", "products": "Slabs", "target_market": "Villa builders"})
        self.assertTrue(saved["ok"])
        return saved["business_id"]

    def test_native_settings_supply_an_account_before_the_wizard_saves_one(self):
        plugin_settings.settings = lambda: {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "from_address": "sales@example.com",
            "from_name": "Stone Sales",
            "signature_text": "Stone Co",
        }
        account, source = plugin_settings.effective_account(None)
        self.assertEqual(source, "plugin_settings")
        self.assertEqual(account["host"], "smtp.example.com")
        self.assertEqual(account["from_address"], "sales@example.com")

    def test_native_settings_win_over_legacy_saved_account(self):
        plugin_settings.settings = lambda: {
            "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_security": "starttls",
            "from_address": "sales@example.com", "from_name": "Native", "signature_text": "",
        }
        saved = {"host": "smtp.wizard.test", "port": 465, "security": "tls", "from_address": "ops@wizard.test", "from_name": "Wizard", "signature_text": "W"}
        account, source = plugin_settings.effective_account(saved)
        self.assertEqual(source, "plugin_settings")
        self.assertEqual(account["host"], "smtp.example.com")
        self.assertEqual(account["signature_text"], "")

    def test_native_settings_are_read_through_the_public_context(self):
        class Ctx:
            def get_config(self, key, default=None):
                return {
                    "smtp_host": "smtp.ctx.test",
                    "smtp_port": 465,
                    "smtp_security": "tls",
                    "from_address": "ops@ctx.test",
                    "from_name": "Ctx",
                    "signature_text": "Ctx signature",
                }.get(key, default)

        self.addCleanup(setattr, plugin_settings, "_CTX", None)
        plugin_settings.bind(Ctx())
        values = plugin_settings.settings()
        self.assertEqual(values["smtp_host"], "smtp.ctx.test")
        account, source = plugin_settings.effective_account(None)
        self.assertEqual(source, "plugin_settings")
        self.assertEqual(account["port"], 465)

    def test_check_response_never_carries_the_password(self):
        business_id = self._business()
        with storage.unit_of_work() as conn:
            storage.save_mail_settings(conn, business_id, mail.validate_account({
                "host": "smtp.example.com", "port": 587, "security": "starttls",
                "from_address": "sales@example.com", "from_name": "Sales", "signature_text": "",
            }))
        original_credentials = plugin_settings.credentials
        plugin_settings.credentials = lambda: ("user", "another-secret-value", "")
        self.addCleanup(setattr, plugin_settings, "credentials", original_credentials)
        original_probe = mail.probe
        mail.probe = lambda account, username, password, **kw: {"ok": False, "checked": True, "credentials_logged": False}
        self.addCleanup(setattr, mail, "probe", original_probe)
        body = setup.save({"action": "check", "business_id": business_id})
        text = json.dumps(body)
        self.assertNotIn("another-secret-value", text)
        self.assertFalse(body["ok"] is False and body.get("password_returned"))

    def test_missing_settings_report_incomplete_instead_of_guessing(self):
        plugin_settings.settings = lambda: dict(plugin_settings.DEFAULTS)
        self.assertEqual(plugin_settings.effective_account(None)[1], "incomplete")

    def test_status_never_returns_the_password(self):
        self._business()
        original = plugin_settings.credentials
        plugin_settings.credentials = lambda: ("user@example.com", "supersecret-value", "")
        self.addCleanup(setattr, plugin_settings, "credentials", original)
        body = json.dumps(setup.status())
        self.assertNotIn("supersecret-value", body)
        self.assertTrue(setup.status()["mail"]["password_present"])

    def test_connection_state_is_explicit(self):
        business_id = self._business()
        self.assertEqual(setup.status()["mail"]["connection"], "not_configured")
        plugin_settings.settings = lambda: {
            "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_security": "starttls",
            "from_address": "sales@example.com", "from_name": "", "signature_text": "",
        }
        original = plugin_settings.credentials
        plugin_settings.credentials = lambda: ("", "", "")
        self.addCleanup(setattr, plugin_settings, "credentials", original)
        self.assertEqual(setup.status()["mail"]["connection"], "missing_credentials")
        plugin_settings.credentials = lambda: ("user", "pass", "")
        self.assertEqual(setup.status()["mail"]["connection"], "unverified")
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, business_id)
            profile = dict(business.get("profile") or {})
            profile["last_mail_check"] = {"ran": True, "ok": False, "at": "2026-11-05T00:00:00+00:00", "code": "smtp_probe_failed"}
            storage.save_business(conn, {
                "name": business["name"], "offer": business["offer"], "offer_short": business["offer_short"],
                "default_cta": business["default_cta"], "icp": business["icp"], "profile": profile,
                "citations": business.get("citations") or [],
            })
        self.assertEqual(setup.status()["mail"]["connection"], "failed")

    def test_research_only_mode_needs_no_credentials(self):
        business_id = self._business()
        skipped = setup.save({"action": "skip_mail", "business_id": business_id})
        self.assertTrue(skipped["ok"])
        self.assertTrue(skipped["mail"]["research_only"])
        self.assertEqual(skipped["mail"]["connection"], "not_configured")
        self.assertEqual(skipped["step"], 3)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mail.set_transport_for_tests, None)

    def test_connection_test_sends_no_message(self):
        seen = {}

        def transport(account, username, password, message):
            seen["account"] = account["host"]
            seen["message"] = message
            seen["password"] = password
            return 250, False

        mail.set_transport_for_tests(transport)
        account = mail.validate_account({
            "host": "smtp.example.com", "port": 587, "security": "starttls",
            "from_address": "sales@example.com", "from_name": "Sales", "signature_text": "",
        })
        result = mail.probe(account, "user", "pass")
        self.assertTrue(result["ok"])
        self.assertIsNone(seen["message"])
        self.assertTrue(result["credentials_logged"] is False)

    def test_check_reports_not_configured_without_touching_smtp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        storage.set_data_dir(Path(tmp.name))
        self.addCleanup(storage.set_data_dir, None)
        saved = setup.save({"action": "business", "name": "Stone Co", "products": "Slabs", "target_market": "Villa builders"})
        result = json.loads(commands.configure_mail({"action": "check", "business_id": saved["business_id"]}))
        self.assertFalse(result["ok"])
        self.assertIn(result["code"], {"mail_not_configured"})
        self.assertFalse(result["sent"])


if __name__ == "__main__":
    unittest.main()
