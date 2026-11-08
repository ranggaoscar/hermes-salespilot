# SalesPilot — 90-second demo storyboard

**Goal:** a judge understands in one viewing what SalesPilot does, that Hermes does the work, and that
a person approves every email. **Data:** the synthetic Kinetra Mobility fixture only (fictional
companies on `.test` domains). Never record a live database or a real inbox.

**Format:** 1920×1080, Hermes Desktop light theme, window at ~1440 px wide, system cursor visible,
no zoom effects. One voice-over, calm pace (~140 words a minute). Burned-in captions for the key
lines. Music optional and low.

| # | Time | On screen | Voice-over | Caption |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:07 | Cover frame (`assets/catalog-cover.png`), slow cross-fade into Hermes Desktop with SalesPilot in the sidebar | "Small sales teams don't lose deals for lack of leads. They lose them in the gaps." | — |
| 2 | 0:07–0:17 | Click **SalesPilot** in the sidebar. Customers page: hover over **Today**, then the six-step journey | "SalesPilot is the sales desk inside Hermes. Hermes does the work. You see everything here — and you make the calls." | *Hermes does the work. You decide.* |
| 3 | 0:17–0:29 | **Find leads with Hermes** → the prompt lands in chat. Cut (do not wait) to two new rows in Customers with evidence quotes | "Ask Hermes to find companies that match your ideal customer. Every lead keeps the public quote that made it a lead." | *Quoted evidence, not guesses* |
| 4 | 0:29–0:37 | **Import CSV** → mapping auto-filled from Indonesian headers → tick permission → *Import 2 rows* → toast | "Or bring the list you already have. Columns map themselves; duplicates are skipped." | — |
| 5 | 0:37–0:52 | Open **PT Gemilang Kargo** → Step 3 · Approve, draft visible → **Send with approval** → Hermes chat shows the confirmation question. Stop on the question; **do not press send on camera** unless the SMTP host is a sandbox | "Drafts wait for you. Send opens Hermes, shows the exact email, and asks before one message leaves your own mailbox. Nothing is ever sent in bulk." | *A person approves every email* |
| 6 | 0:52–1:04 | Table: point at **Emailed / Replied / Next step**. Open **Samudra Bay Resort** — the reply quoted, activity timeline | "You always know who got an email, when they replied, what they said, and what to do next." | — |
| 7 | 1:04–1:16 | **Hot Prospects** tab: two cards, reply as proof, heat bars, *Reply personally* → **Draft reply with Hermes** | "Hot Prospects shows only people who answered with interest — in their own words — hottest first." | *Interest you can prove* |
| 8 | 1:16–1:24 | Brand switch in the header → Saltgrass Studio (empty pipeline) → back. Settings → **What works today** | "Several brands, kept apart. And Settings tells you honestly what works, what needs setup, and what isn't supported yet." | *Honest by design* |
| 9 | 1:24–1:30 | End card: app icon, "SalesPilot for Hermes", "Created by ROCK" | "SalesPilot. Find customers, approve every email, follow up on time." | *Created by ROCK* |

## Recording notes

- Rebuild the fixture right before recording so relative times ("5h ago") look fresh.
- Hide any personal Hermes sessions in the sidebar, or use a dedicated demo profile (`HERMES_HOME`).
- Shot 5: the honest demo stops at Hermes' confirmation question. If a real send is wanted, point
  SMTP at a local sandbox (for example a MailHog/Mailpit container) and say so in a caption.
- Shot 3: live discovery can take a minute. Record the prompt landing in chat, then cut to the result.
  Do not imply it is instant.
- Keep the cursor still while speaking; move only on the action.
- Export: H.264, 1080p30, < 50 MB. Add a 2-second still of the cover as the thumbnail frame.

## 15-second cut (social / marketplace preview)

Shots 2 → 5 → 7 → 9, voice-over: "SalesPilot is the sales desk inside Hermes. Hermes finds and
writes; you approve every email; interested replies rise to the top. Created by ROCK."
