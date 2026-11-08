---
name: salespilot
description: Use when operating SalesPilot — onboard a business, import synthetic customers, qualify B2B leads, record research, draft outreach, plan follow-ups, or report pipeline. Sending stays disabled.
version: 0.1.0
author: Hermes SalesPilot contributors
license: MIT
metadata:
  hermes:
    tags: [sales, crm, outreach, b2b]
    related_skills: []
---

# SalesPilot

## Overview

SalesPilot is a native Hermes plugin. It stores a business profile, customer records, lead decisions, research notes, drafts, approvals, and follow-ups. Phase 1 never sends email or WhatsApp.

Load this skill before the first sales tool call in a session.

## When to Use

- The user wants a pipeline, lead qualification, a follow-up list, an outreach draft, or a sales report.
- Do not use it to send, blast, scrape private CRMs, or invent missing contact facts.

## Operating loop

1. If the operator gives a public URL, call `salespilot_onboard_business` with `authorized=true` and `url`. Private, loopback, and metadata hosts are refused. If they paste page text instead, pass `sources` with `permitted=true`.
2. Import CSV only with `authorized=true`, a mapping, and an authorization note.
3. Discover prospects with `discovery_url` on `salespilot_research_opportunity`. Companies must be quoted on that page. `use_hermes_search=true` may call Hermes `web_search` when dispatch exists. An empty or failed search creates zero companies.
4. Qualify the returned `lead_id`.
5. Draft only after `decision=qualified`. `check_smtp=true` reports whether secret names are set, never the values.
6. Plan follow-ups. Never send.
7. Report from the tool result.
8. Do not treat `human_confirmed` as permission to send. `/salespilot-send <draft_id>` is the only send path. It asks with Hermes `ask_choice` inside the slash command. A tool call cannot authorize SMTP. Cancel, a missing prompt, cron, and gateway tool turns fail closed.

Done when report `summary.customers` and `by_decision` match the rows just written, and every approval `sent` field is false.

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
- `request` records pending. `approve` records approved and still does not send. `reject` means revise or stop.
- If the adapter reason is `sending_disabled_phase_1`, stop. Do not retry through SMTP, Evolution, n8n, or a shell.

## Follow-up actions

| Action | Do |
|---|---|
| `fill_gap` | Ask for the missing evidence, source, or contact. |
| `draft_outreach` | Call the draft tool. |
| `request_approval` | Record a pending approval. |
| `wait_for_decision` | Do not draft again and do not send. |
| `revise_draft` | Change the ask or stop. |
| `hold_approved_unsent` | Tell the user sending is disabled. |
| `no_action` | Rejected lead. Leave it. |

## Common Pitfalls

1. Treating a tool error as a sent message. `sent` is false unless a later phase explicitly returns true, which Phase 1 never does.
2. Importing real customer files while Phase 1 requires `synthetic: true`.
3. Qualifying from memory. Pass only facts present in the user message or a source the caller already opened.
4. Calling a channel adapter, webhook, or workflow and treating its HTTP 200 as delivery.
5. Reading `.env`, `auth.json`, or pasting tokens into notes. Credentials are out of scope until a later phase uses Hermes secret scope.
