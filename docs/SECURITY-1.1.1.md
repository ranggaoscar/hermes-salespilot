# SalesPilot 1.1.1 — security review delta

Scope: the three blockers and two recommendations in teknium1's review of PR
[NousResearch/hermes-agent#151239](https://github.com/NousResearch/hermes-agent/pull/151239#pullrequestreview-5823121676).
No redesign, production installation, mailbox sync, or real email is part of this patch.

## SMTP credential destination authority

- The model tool `salespilot_configure_mail` only supports `status`, `check`, and `suppress`.
  Host, port, TLS mode, sender identity, signature, unknown properties and forged confirmation
  parameters are rejected by the handler, not merely omitted from its schema.
- The Desktop wizard no longer delegates transport writes to the model tool. Its Save sender action
  shows an explicit confirmation naming the host, port, security and sender. Cancellation or a missing
  confirmation API does not save. The setup backend requires the confirmed Desktop request.
  This boolean is not a model authorization surface: no model tool accepts it or calls wizard save.
- Native Hermes Settings are authoritative for the whole account. Invalid or incomplete native
  destination/identity settings fail closed, without fallback to a saved host. A Settings read error
  also fails closed; it is never interpreted as an empty configuration permitting wizard fallback.
- Old SQLite accounts cannot be distinguished as tool-created versus operator-created. They remain
  intact but are not eligible for authentication until an operator reconfirms them in the wizard,
  or configures native Settings. A new metadata fingerprint binds wizard confirmation to the
  exact transport and sender identity; a raw settings write invalidates that confirmation.
- Both `action: check` (SMTP authentication without email) and `/salespilot-send` resolve the same
  trusted effective account before reading SMTP credentials. Tests plant an attacker-controlled
  legacy host and prove neither path uses it. Unconfirmed legacy-only checks stop before secret lookup.
- This is a plugin-model boundary, not a sandbox against an operator-authorized filesystem/shell
  agent or anyone with authenticated administrative access to the Desktop configuration API.

## IMAP TLS

IMAP uses an explicit `ssl.create_default_context()` for certificate-chain and hostname validation.
Plaintext IMAP is unsupported and refused before credentials are retrieved in the sync path and
before any connection/login in the fetcher. TLS errors do not fall back to plaintext or disable
verification. The tests exercise successful TLS, certificate failure, hostname mismatch and plaintext
refusal without connecting to a real mailbox.

## Package-loaded send and duplicate protection

The outbound timeline recorder uses package-relative imports first, with the existing standalone
fallback. The regression test loads the plugin as a package without the plugin directory on
`sys.path`, mocks SMTP acceptance, and checks the returned Message-ID against the delivery ledger,
outbound message, and timeline event. Repeating the slash command reuses the accepted delivery
without another SMTP call. SMTP acceptance remains distinct from confirmed inbox delivery.

## Compatibility and operator action

- Manifest and package version: 1.1.1; minimum Hermes: >=0.23.0 (`ctx.ask_choice`).
- Bundled skill now documents the attended slash-command send path and per-email host approval.
- On upgrade: review and reconfirm any old wizard SMTP transport, or fill native Hermes Settings.
  No customer/message records are removed and no credential values are migrated.
- Existing legacy plaintext IMAP configurations stop syncing until TLS is configured.

## Reproduction

```sh
python -m unittest tests.test_smtp_authority tests.test_imap_tls_security tests.test_package_send -v
python -m unittest discover -s tests -t . -v
node --test tests/desktop/plugin-lifecycle.test.mjs tests/desktop/select-dropdown.test.mjs
hermes plugins doctor . --ci
hermes plugins validate . --install-deps
```

All fixtures use disposable databases and synthetic identities. SMTP is mocked. Plugin doctor and
validation run discovery/registration, not a live email send or production plugin activation.

Local release gates: 185 Python unittest cases and 23 Desktop node:test cases passed; plugin doctor
and validation passed (11 registered tools, security scan safe). The package-send test reproduces
`ModuleNotFoundError: accounts` on the originally reviewed dad697e6 commit and passes after the fix.
The IMAP tests also fail on that baseline for missing verified context and plaintext acceptance.
Certificate failure tests mock the IMAP constructor; no real mailbox or live TLS handshake is claimed.
