# E2E acceptance plan — one real mailbox, zero prospect contact

Status: **not executed**. This is the script to run once ROCK approves a real mailbox test.
Nothing here sends to a prospect; the only recipient is an address the operator controls.

## 0. Preconditions (all must be true before step 1)

| Item | Where | Current state |
| --- | --- | --- |
| Explicit approval for one real SMTP send | chat | **not given** |
| SMTP/IMAP secret pair in the profile secret scope | Hermes secrets (`SALESPILOT_SMTP_USERNAME`, `SALESPILOT_SMTP_PASSWORD`) | **absent** |
| Sender account row for the brand | `accounts` (created by Settings → Sender accounts) | **none** |
| SMTP host/port/from address for the brand | brand mail settings | **empty** |
| IMAP host/port/username | brand IMAP settings | **empty** |
| Operator test mailbox address | owned by ROCK | to confirm |

Stop at any row that is not satisfied. No hidden fallback exists: a missing slot fails closed.

## 1. Test identity

- Sender: the brand account, e.g. `sales@<brand-domain>`.
- Recipient: **one address the operator owns** (a dedicated test mailbox, e.g. `qa@<operator-domain>`),
  never a discovered prospect.
- Subject prefix: `[SP-TEST] <date>` so the thread is obvious in both mailboxes.
- One message only. No follow-up schedule is armed for this lead.

## 2. Steps and evidence

| # | Action | Expected | Evidence to capture |
| --- | --- | --- | --- |
| 1 | Create sender account + SMTP/IMAP settings through Settings (secret typed in the Hermes secret prompt, never in chat or a form field) | account row `status=active`, credential slot `default` | screenshot of Settings, `GET /accounts` (no secret fields) |
| 2 | Create a lead that is the operator's own test address, with quoted evidence and a buyer role | stage `ready_for_outreach` after operator qualification | `pipeline` list row + stage |
| 3 | Approve exactly one draft via `/salespilot-send` | `smtp_accepted` recorded with Message-ID, sender, timestamp | `messages` row: `direction=outbound`, `message_id`, `account_id`, `smtp_accepted` |
| 4 | Open the test mailbox, confirm arrival, reply manually | real inbound message exists | screenshot of the received mail + reply |
| 5 | Run inbox sync once (`/accounts` → sync, or `inbox` tool `action=sync`) | reply matched to the thread by `In-Reply-To`/`References`; `replied_at` set; follow-up state `stopped` | `messages` inbound row, cursor `last_uid` advanced, `follow_ups` state |
| 6 | Run the same sync again | zero new rows, same cursor behaviour | second sync report: `duplicate: true`/`matched: 0` |
| 7 | Send a neutral/ambiguous reply variant and sync | lands in `inbox_review` with `uncertain_intent`, **not** hot | `/review` count + reason |
| 8 | Negative check: sync a message with no thread headers from an unknown sender | `inbox_review`, never auto-matched | review row |
| 9 | Negative check: qualification of a role mailbox (`reservation@`, `cs@`) | stage `discovered`, `outreach_ready=false` | `pipeline` row |
| 10 | Verify Hot Prospects | only the human-confirmed interest appears | `/hot` payload |

## 3. Abort conditions

- Any outbound message addressed to a discovered prospect → stop, treat as incident.
- Secret value visible in DB row, log, API response, or chat → stop.
- Reply matched to the wrong thread/company → stop, leave row in review, do not send.
- Cursor regression or duplicate inbound rows growing on repeat sync → stop, keep DB copy.

## 4. What this plan cannot prove

- Deliverability to third parties (only the operator mailbox is tested).
- Inbox placement (spam folder) for real prospects.
- Multi-mailbox operation: Hermes currently exposes one SMTP/IMAP secret pair per profile, so a
  second authenticated mailbox is not available yet.

## 5. Rollback

Snapshot the SQLite DB (`sqlite3 .backup`) before step 2. Rollback = stop gateway writes, restore
the snapshot, re-open. The test thread stays in the operator mailbox and is not part of the DB.
