"""Human mail commands. Sending exists only after ask_choice returns send."""

from __future__ import annotations

import json
from typing import Any

try:
    from . import domain, mail, pipeline, plugin_settings, storage
except ImportError:
    import domain
    import mail
    import pipeline
    import plugin_settings
    import storage

_CTX = None
SECRET_USER = plugin_settings.SECRET_USERNAME
SECRET_PASSWORD = plugin_settings.SECRET_PASSWORD
_SECRET_ARGS = {"password", "secret", "username", "smtp_password", "smtp_username"}


def bind(ctx) -> None:
    global _CTX
    _CTX = ctx


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _fail(code: str, error: str, **extra: Any) -> str:
    body = {"ok": False, "code": code, "error": error, "sent": False, "sending_enabled": False}
    body.update(extra)
    return _dump(body)


def _secrets() -> tuple[str, str, str]:
    return plugin_settings.credentials()


def secret_flags() -> tuple[bool, bool]:
    username, password, error = _secrets()
    if error:
        return False, False
    return bool(username), bool(password)


def configure_mail(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    if _SECRET_ARGS.intersection(args):
        return _fail("secret_in_args", "SMTP username and password belong in Hermes secrets, not this call.")
    action = str(args.get("action") or "save").strip().lower()
    business_id = str(args.get("business_id") or "")
    with storage.unit_of_work() as conn:
        business = storage.get_business(conn, business_id)
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        business_id = business["id"]
        if action == "suppress":
            email = str(args.get("email") or "")
            if not mail.valid_email(email):
                return _fail("bad_email", "Suppression needs one valid email.")
            storage.add_suppression(conn, business_id, email, str(args.get("reason") or "opt-out"))
            return _dump({"ok": True, "suppressed": email.lower(), "sent": False})
        if action == "status":
            current = storage.get_mail_settings(conn, business_id)
            account, source = plugin_settings.effective_account(current)
            return _dump({"ok": True, "settings": _public_settings(account), "source": source, "sent": False})
        if action == "check":
            current = storage.get_mail_settings(conn, business_id)
            account, source = plugin_settings.effective_account(current)
            if account is None:
                return _fail("mail_not_configured", "Save SMTP settings, or fill SMTP host and sender email in Settings → Plugins → SalesPilot.", source=source)
            username, password, reason = _secrets()
            if reason:
                return _fail(reason, "Hermes secret scope did not return SMTP credentials.", credentials_logged=False)
            result = mail.probe(account, username, password)
            result["sent"] = False
            result["source"] = source
            result["password_present"] = bool(password)
            result["username_present"] = bool(username)
            result["error"] = "" if result.get("ok") else "The SMTP server did not accept this connection. No email was sent."
            return _dump(result)
        try:
            account = mail.validate_account(args)
        except (ValueError, TypeError) as exc:
            return _fail("bad_mail_settings", str(exc))
        storage.save_mail_settings(conn, business_id, account)
        return _dump({"ok": True, "settings": _public_settings(account), "sent": False, "credentials_stored": False})


def slash_send(raw_args: str) -> str:
    draft_id = str(raw_args or "").strip().split()[0] if str(raw_args or "").strip() else ""
    if not draft_id:
        return "Usage: /salespilot-send <draft_id>"
    ctx = _CTX
    ask = getattr(ctx, "ask_choice", None) if ctx is not None else None
    if ask is None:
        return _fail("host_approval_unavailable", "Sending needs the Hermes slash-command choice prompt.")
    with storage.unit_of_work() as conn:
        draft = storage.get_draft(conn, draft_id)
        if draft is None:
            return _fail("draft_not_found", "draft_id was not found.")
        if draft.get("channel") != "email":
            return _fail("not_email", "This command sends email drafts only.")
        lead = storage.get_lead(conn, draft["lead_id"])
        account, account_source = plugin_settings.effective_account(storage.get_mail_settings(conn, draft["business_id"]))
        if lead is None or account is None:
            return _fail("not_ready", "The draft needs a lead and saved mail settings.")
        recipient = str(draft.get("recipient") or "")
        if recipient.lower() != str(lead.get("email") or "").lower() or not lead.get("email_valid"):
            return _fail("unverified_recipient", "Recipient must be the lead's format-valid email. Nothing was sent.")
        plain = str(draft.get("body") or "").strip()
        signature = str(account.get("signature_text") or "").strip()
        if signature and signature not in plain:
            plain = f"{plain}\n\n{signature}"
        revision = domain.draft_revision({**draft, "body": plain})
        existing = storage.get_delivery(conn, draft["business_id"], draft_id, revision, recipient)
        if existing and existing["state"] != "failed":
            existing["retried"] = False
            existing["sent"] = False
            existing["inbox_delivery_proven"] = False
            return _dump({"ok": True, "reused": True, "delivery": existing})
        # Consent and lifecycle are read at send time, not when the draft was written: a refusal,
        # bounce, archive or do-not-contact that arrived after drafting still stops this send. The
        # lifecycle check runs first so the refusal is reported as a refusal, not as a generic
        # suppression entry (which can also come from a plain operator opt-out).
        block = pipeline.send_block_reason(lead)
        if block:
            return _fail(block, "This prospect must not receive email now. Nothing was sent.")
        if storage.is_suppressed(conn, draft["business_id"], recipient):
            return _fail("suppressed", "That address is on the suppression list.")
        if storage.bounced_recipient(conn, draft["business_id"], recipient):
            return _fail("recipient_bounced", "A previous message to this address bounced. Nothing was sent.")
        if storage.recent_delivery_count(conn, draft["business_id"]) >= mail.DAILY_CAP:
            return _fail("rate_limited", "Daily send cap reached. Nothing was sent.")
        if storage.recent_recipient(conn, draft["business_id"], recipient, mail.REPEAT_DAYS):
            return _fail("repeated_contact", "That recipient was already contacted. Nothing was sent.")
        try:
            message = mail.compose(account, draft)
        except ValueError as exc:
            return _fail("bad_message", str(exc))
        question = (
            f"Send one email to {recipient}? Subject: {message['Subject']}. "
            f"Revision {revision}. This is not a bulk send."
        )
        prepared = {
            "business_id": draft["business_id"],
            "draft_id": draft_id,
            "lead_id": draft["lead_id"],
            "revision": revision,
            "recipient": recipient,
            "message_id": str(message["Message-ID"]),
            "subject": str(message["Subject"]),
        }
    choice = ask(question, ["send", "cancel"])
    if choice != "send":
        with storage.unit_of_work() as conn:
            storage.add_event(conn, "send_denied", prepared["business_id"], draft_id, {"choice": choice or ""})
        return _fail("host_declined" if choice else "host_approval_unavailable", "Host did not choose send. Nothing was sent.")
    with storage.unit_of_work() as conn:
        delivery_id = storage.begin_delivery(conn, prepared)
    username, password, reason = _secrets()
    if reason:
        _finish(delivery_id, "failed", 0)
        return _fail(reason, "SMTP secrets are not available. Nothing was sent.")
    if "@" in username and str(account.get("from_address") or "").strip().lower() != username.strip().lower():
        _finish(delivery_id, "failed", 0)
        return _fail(
            "sender_mismatch",
            "This Hermes profile holds one SMTP identity, so a second brand would send under the first "
            "brand's account. Nothing was sent.",
            multi_mailbox_supported=False,
        )
    try:
        result = mail.deliver(account, username, password, message)
    except Exception:
        _finish(delivery_id, "unknown", 0)
        return _fail("smtp_unknown", "SMTP outcome is unknown. It will not be retried.", inbox_delivery_proven=False)
    state = "unknown" if result["state"] == "unknown" else result["state"]
    if state == "rejected":
        state = "failed"
    _finish(delivery_id, state, int(result.get("smtp_code") or 0))
    if state == "accepted":
        _record_sent_message(prepared, draft, account, result, revision)
    return _dump({
        "ok": state == "accepted",
        "sent": False,
        "smtp_accepted": state == "accepted",
        "delivery_status": "smtp_handoff" if state == "accepted" else state,
        "delivery_meaning": "The SMTP server accepted the message. Inbox delivery was not observed." if state == "accepted" else "No inbox delivery was observed.",
        "inbox_delivery_proven": False,
        "delivery": {
            "id": delivery_id,
            "state": state,
            "message_id": result["message_id"],
            "recipient": recipient,
            "revision": revision,
            "smtp_code": result.get("smtp_code"),
        },
    })


def _finish(delivery_id: str, state: str, smtp_code: int) -> None:
    with storage.unit_of_work() as conn:
        storage.finish_delivery(conn, delivery_id, state, smtp_code)


def _record_sent_message(prepared: dict, draft: dict, account: dict, result: dict, revision: str) -> None:
    """Persist the outbound evidence: who sent it, the Message-ID, and the exact content hash."""
    import accounts as accounts_module
    import inbox as inbox_module

    with storage.unit_of_work() as conn:
        account_row = accounts_module.ensure_account(
            conn, prepared["business_id"], account.get("from_address", ""),
            display_name=account.get("from_name", ""),
        )
        stored = inbox_module.record_message(
            conn,
            prepared["business_id"],
            {
                "message_id": result.get("message_id", ""),
                "in_reply_to": "",
                "references": [],
                "subject": str(draft.get("subject") or ""),
                "sender": str(account.get("from_address") or "").lower(),
                "recipient": str(prepared.get("recipient") or "").lower(),
                "sent_at": domain.iso(),
                "received_at": "",
                "body": str(draft.get("body") or "")[:1000],
                "body_sha256": revision,
            },
            direction="outbound",
            lead_id=str(draft.get("lead_id") or ""),
            account_id=(account_row or {}).get("id", ""),
            delivery_state="accepted",
            evidence_level="smtp_accepted",
        )
        if draft.get("lead_id"):
            storage.set_pipeline_fields(
                conn,
                draft["lead_id"],
                contacted_at=domain.iso(),
                account_id=(account_row or {}).get("id", ""),
                pipeline_status="contacted" if (storage.get_lead(conn, draft["lead_id"]) or {}).get("pipeline_status") in {"discovered", "qualified", "draft_ready"} else (storage.get_lead(conn, draft["lead_id"]) or {}).get("pipeline_status", "contacted"),
            )
        storage.add_event(conn, "message_sent", prepared["business_id"], draft.get("lead_id") or "", {
            "message_id": result.get("message_id"),
            "account_id": (account_row or {}).get("id", ""),
            "evidence_level": "smtp_accepted",
            "stored": stored is not None,
        })


def _public_settings(account: dict[str, Any] | None) -> dict[str, Any] | None:
    if not account:
        return None
    hidden = {"signature_html"}
    return {key: value for key, value in account.items() if key not in hidden and "password" not in key}
