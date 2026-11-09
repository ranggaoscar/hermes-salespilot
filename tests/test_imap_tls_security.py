"""Isolated IMAP transport security regression tests; no external services."""

import ssl
import unittest
from unittest import mock

import inbox
import plugin_settings


class ImapTlsSecurityTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = inbox.ImapFetcher("imap.example.test", 993, "user", "password")

    def test_valid_tls_uses_verified_context_before_login(self):
        client = mock.MagicMock()
        client.search.return_value = ("OK", [b""])
        with mock.patch.object(inbox.imaplib, "IMAP4_SSL", return_value=client) as connect:
            self.assertEqual(self.fetcher.search_recent(), [])
        args, kwargs = connect.call_args
        self.assertEqual(args, ("imap.example.test", 993))
        context = kwargs["ssl_context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        client.login.assert_called_once_with("user", "password")

    def test_certificate_and_hostname_failures_never_login_or_fallback(self):
        for reason in ("certificate verify failed", "hostname mismatch"):
            for method in ("search_recent", "fetch_incremental"):
                with self.subTest(reason=reason, method=method):
                    error = ssl.SSLCertVerificationError(reason)
                    with mock.patch.object(inbox.imaplib, "IMAP4_SSL", side_effect=error) as secure, \
                         mock.patch.object(inbox.imaplib, "IMAP4") as plaintext:
                        with self.assertRaises(ssl.SSLCertVerificationError):
                            getattr(self.fetcher, method)()
                    secure.assert_called_once()
                    plaintext.assert_not_called()

    def test_plaintext_refused_before_connection_and_credentials(self):
        with mock.patch.object(inbox.imaplib, "IMAP4") as plaintext, \
             mock.patch.object(inbox.imaplib, "IMAP4_SSL") as secure:
            with self.assertRaisesRegex(ValueError, "requires TLS"):
                inbox.ImapFetcher("imap.example.test", 143, "user", "password", use_ssl=False)
            self.fetcher.use_ssl = False
            for method in ("search_recent", "fetch_incremental"):
                with self.assertRaisesRegex(ValueError, "requires TLS"):
                    getattr(self.fetcher, method)()
            plaintext.assert_not_called()
            secure.assert_not_called()
        with mock.patch.object(inbox.storage, "get_imap_settings", return_value={
            "host": "imap.example.test", "username": "user", "use_ssl": 0,
        }), mock.patch.object(plugin_settings, "credentials") as credentials, \
             mock.patch.object(inbox.imaplib, "IMAP4") as plaintext, \
             mock.patch.object(inbox.imaplib, "IMAP4_SSL") as secure:
            result = inbox.run(None, "synthetic", {"action": "sync"})
        self.assertEqual(result["code"], "imap_tls_required")
        credentials.assert_not_called()
        plaintext.assert_not_called()
        secure.assert_not_called()

    def test_sync_fails_closed_on_certificate_errors(self):
        settings = {"host": "imap.example.test", "username": "user", "use_ssl": 1}
        with mock.patch.object(inbox.storage, "get_imap_settings", return_value=settings), \
             mock.patch.object(inbox.storage, "get_cursor", return_value={}), \
             mock.patch.object(plugin_settings, "credentials", return_value=("user", "password", "")), \
             mock.patch.object(inbox.imaplib, "IMAP4_SSL", side_effect=ssl.SSLCertVerificationError("invalid")), \
             mock.patch.object(inbox, "sync") as sync, \
             mock.patch.object(inbox.storage, "mark_imap_sync") as mark:
            result = inbox.run(None, "synthetic", {"action": "sync"})
        self.assertEqual(result["code"], "imap_failed")
        self.assertEqual(result["error"], "SSLCertVerificationError")
        sync.assert_not_called()
        mark.assert_not_called()


if __name__ == "__main__":
    unittest.main()
