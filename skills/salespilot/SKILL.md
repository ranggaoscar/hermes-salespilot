---
name: salespilot
description: Use when operating SalesPilot sales workflows. Email requires host approval for every send.
version: 1.1.1
author: Hermes SalesPilot contributors
license: MIT
metadata:
  hermes:
    tags: [sales, crm, outreach, b2b]
    related_skills: []
---

# SalesPilot

## Overview

SalesPilot is a native Hermes plugin. It stores business profiles, customers, research, drafts,
approvals and follow-ups. Email sends only through `/salespilot-send <draft_id>` on an attended
Hermes surface after the host's `ctx.ask_choice` explicitly returns `send`. Requires Hermes >=0.23.0.
WhatsApp sending and Gmail OAuth are unavailable.

Load this skill before the first sales tool call in a session.

## When to Use

- The user wants a pipeline, lead qualification, a follow-up list, an outreach draft, or a sales report.
- Never blast, scrape private CRMs, or invent missing contact facts. A model tool cannot authorize sending.

## Operating loop

1. If the operator gives a public URL, call `salespilot_onboard_business` with `authorized=true` and `url`. Private, loopback, and metadata hosts are refused. If they paste page text instead, pass `sources` with `permitted=true`.
2. Import CSV only with `authorized=true`, a mapping, and an authorization note.
3. Discover prospects with `discovery_url` on `salespilot_research_opportunity`. Companies must be quoted on that page. `use_hermes_search=true` may call Hermes `web_search` when dispatch exists. An empty or failed search creates zero companies.
4. Qualify the returned `lead_id`.
5. Draft only after `decision=qualified`. `check_smtp=true` reports whether secret names are set, never the values.
6. Plan follow-ups; reminders never send automatically.
7. Report from the tool result.
8. Do not treat `human_confirmed` as permission to send. `/salespilot-send <draft_id>` is the only send path. It asks with Hermes `ask_choice` inside the slash command. A tool call cannot authorize SMTP. Cancel, a missing prompt, cron, and gateway tool turns fail closed.

Done when report counts reconcile to persisted data. Approval-ledger transitions do not send.
Only an explicit host-confirmed slash command can hand an email to SMTP.

## Gates

A lead is qualified only when the tool says so. Required: company, evidence, http(s) source, ICP segment and geo when the profile sets them, and one format-valid public email or phone.

- Masked or partial numbers stay empty. Never guess digits.
- Format-valid is not WhatsApp registration, deliverability, or consent.
- Competitor phrases in the profile exclude list are rejects.
- Missing facts are holds, not invented answers.
- Dedupe on normalized company, email, and phone before treating a row as new.

## Draft and approval

- One CTA. No second ask, no fake urgency, no claim that is not in `evidence`.
- Reuse the returned draft when `reused` is true. Do not create a near-duplicate by changing whitespace.
- Approval decisions require the host approval prompt. A model-supplied `human_confirmed=true` is ignored.
- Review sender, recipient, subject, content and signature, then use `/salespilot-send <draft_id>`.
  Each email needs its own host choice. Cancel, missing choice binding, unattended tool/cron turns fail closed.
- Never bypass a blocked send using SMTP, Evolution, n8n, a shell or another adapter.
- SMTP `accepted` is a handoff, not inbox delivery. An accepted or unknown delivery is not retried;
  reuse its delivery ledger and Message-ID rather than making another draft to bypass idempotency.

## Mailbox configuration

- Only the operator configures transport and sender identity in Hermes Settings or the Desktop wizard.
  The wizard asks the operator to confirm the host, port, TLS mode and sender before saving.
- `salespilot_configure_mail` supports only `status`, `check`, and `suppress`. Never pass host, port,
  security, sender, credentials, or a fabricated confirmation to this tool.
- Hermes Settings are authoritative. Legacy saved transport requires operator reconfirmation;
  never use an untrusted saved host or infer one from researched web content.
- Credentials belong in Hermes secret scope, never chat, tool arguments, SQLite or logs.
- IMAP requires verified TLS. Plaintext and certificate/hostname failures stop before login.

## Follow-up actions

| Action | Do |
|---|---|
| `fill_gap` | Ask for the missing evidence, source, or contact. |
| `draft_outreach` | Call the draft tool. |
| `request_approval` | Record a pending approval. |
| `wait_for_decision` | Do not draft again and do not send. |
| `revise_draft` | Change the ask or stop. |
| `hold_approved_unsent` | Wait for an attended `/salespilot-send` and its separate host approval. |
| `no_action` | Rejected lead. Leave it. |

## Common Pitfalls

1. Treating SMTP acceptance, a tool result, or an approval record as confirmed inbox delivery.
2. Importing customer files without authorization, mapping and a source label. Use fictional data for demos.
3. Qualifying from memory. Pass only facts present in the user message or a source the caller already opened.
4. Calling a channel adapter, webhook, or workflow and treating its HTTP 200 as delivery.
5. Reading `.env`, `auth.json`, or pasting credentials into notes; use only Hermes secret scope.
