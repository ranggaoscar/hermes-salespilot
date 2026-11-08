# Email-first scope: gap analysis and what was built

The Google Sheet is a reference for workflow, not a template. WhatsApp, Evolution API, BCI projects
and sheet migration are out of scope. The six flows below are the product.

## Gap analysis (before this commit)

| Flow | Was | Gap | Now |
|---|---|---|---|
| Collect | `research_opportunity` reads permitted public text through Hermes search, extracts labelled facts | Only works inside the gateway (needs `ctx.dispatch_tool`); no email-first pouring into a brand | unchanged, still evidence-only; discovery drives the rest |
| Store | `leads` + `customers`, brand-scoped, indexed, paged in SQLite | no sender accounts, no message history | `accounts` + `messages`, brand-scoped |
| Outreach | draft → `/salespilot-send` → SMTP, one credential per profile | nothing recorded about *who* sent or the exact content | send path records account, Message-ID, `evidence_level=smtp_accepted`, content hash, `contacted_at` |
| Monitor | none | no IMAP, no thread matching, no intent | `inbox.py`: IMAP fetch, RFC822 parse, thread match (In-Reply-To/References → Message-ID), sender fallback, intent rules, idempotent storage |
| Follow-up | `followups` rows + manual status | no computed state, no pause on reply, no attempt cap | `followstate.py`: state from history (`not_contacted → awaiting_reply → followup_due → cold/exhausted`, `replied`, `stopped`) |
| Organize | radar over `signals`, manual statuses | warm contacts not surfaced from replies | `/hot` endpoint: replied / needs-human contacts with excerpt + evidence trail |

## Verification ladder (unchanged, enforced)

`imported` < `smtp_accepted` < `imap_verified`. Only `imap_verified` may set `replied`. SMTP
acceptance is a handoff, never delivery.

## Multi-account

`accounts(brand, address, credential_slot, status)` — several From-addresses per brand, one row each.
Credentials stay in Hermes secrets; a slot names them. `accounts.resolve()` fails closed
(`no_account`, `unknown_account`, `account_disabled`) and never borrows another brand's slot.

## End-to-end proof (offline)

`D:/sp61/e2e/demo_email_first.py` runs a local TLS SMTP sink on 127.0.0.1:2526 with a throwaway
self-signed certificate and drives the real client code path:

1. two brands, one shared sender account
2. two prospects discovered from permitted fixture text
3. draft → simulated approval prompt → SMTP accepted (2 transactions, TLS negotiated)
4. outbound rows: Message-ID + account + `smtp_accepted`
5. two inbound replies built with `In-Reply-To`; sync matches by thread, classifies
   `interested` and `unsubscribe`
6. second sync is a no-op (idempotent)
7. board: `replied:1, stopped:1`; unsubscribe suppressed and follow-ups paused
8. `/hot` shows the interested contact with its excerpt; the other brand sees zero rows

Zero external email. No gateway restart, no live migration, no push.

## Still open

- Live IMAP has never run: no mailbox credentials on this host. `inbox.run(action="sync")` refuses
  with `imap_not_configured` until settings are saved.
- Natural-language discovery still needs the gateway context (`ctx.dispatch_tool`) — untested here.
- UI wiring for accounts (Settings) and the `/hot` panel is backend-ready but not rendered yet.
