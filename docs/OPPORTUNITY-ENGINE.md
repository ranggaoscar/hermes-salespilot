# Opportunity engine

SalesPilot stays one plugin. The mission tool is the vertical slice. It does not replace fetch, draft, or the slash-command send gate.

```text
permitted text
  -> quote check
  -> DNA claims (differentiator, offer, segment)
  -> dated signals (company, date, quote)
  -> offer map only when the offer was already saved
  -> SQLite mission graph
  -> card: why, offer, evidence, next action, send=false
  -> /salespilot-send still requires ask_choice
```

A signal without a quoted date is dropped. A company that is not in the text is not created. Buying intent stays `not_inferred` unless the quoted signal itself says they requested a quote. That is a statement in the source, not a guess.

SMTP `accepted` is now labeled `smtp_handoff`. It means the server took the message. It does not mean the inbox showed it.

RockScraper is not imported. A later adapter can feed the same permitted text.
