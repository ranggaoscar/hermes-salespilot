# Prospect pipeline

SalesPilot stores a prospect only when the company and any contact are quoted in permitted text. A missing email stays blank. Buying intent is not inferred.

Lifecycle events are `discovered`, `status_changed`, `note_added`, `archived`, `deleted`, `smtp_accepted`, and `reply_observed`. SMTP acceptance sets `smtp_accepted` and leaves inbox delivery unverified. A reply is recorded only from an authorized mailbox observation with a message id and a quote.

`do_not_contact`, archive, and explicit delete suppress the address and block a new draft. Delete requires `confirm_delete`. The desktop route `POST /pipeline` can change status, add a note, archive, or delete. It cannot send.

Gmail OAuth is not connected on this host. The onboarding preference records that state and stores no token. Custom SMTP remains the existing Hermes-secret path. Research-only mode does not require an email account.

RockScraper is not imported.
