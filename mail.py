"""SMTP composition and delivery. Secrets stay out of this module's return values."""

from __future__ import annotations

import html
import re
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Callable

DAILY_CAP = 5
REPEAT_DAYS = 7
_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_TRANSPORT: Callable[..., Any] | None = None


def set_transport_for_tests(fn: Callable[..., Any] | None) -> None:
    global _TRANSPORT
    _TRANSPORT = fn


def header_value(value: str, field: str) -> str:
    text = str(value or "")
    if any(char in text for char in "\r\n\x00"):
        raise ValueError(f"{field} contains a line break")
    return text.strip()


def valid_email(value: str) -> bool:
    text = header_value(value, "email")
    return bool(text) and len(text) <= 254 and _EMAIL.fullmatch(text) is not None


def body_text(value: str) -> str:
    """Multi-line body text such as a signature: normalised line endings, no NULs. Never a header."""
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "").strip()


def html_signature(plain: str) -> str:
    # A signature is body text, not a header: line breaks are expected and become <br>.
    body = html.escape(body_text(plain)).replace("\n", "<br>\n")
    return f"<p>{body}</p>"


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
        raise RuntimeError("TLS certificate validation is not enabled")
    return context


def validate_account(fields: dict[str, Any]) -> dict[str, Any]:
    security = str(fields.get("security") or "starttls").strip().lower()
    if security not in {"starttls", "tls"}:
        raise ValueError("security must be starttls or tls")
    host = header_value(str(fields.get("host") or ""), "host")
    if not host or "://" in host or "@" in host or host.lower() in {"metadata", "metadata.google.internal"}:
        raise ValueError("SMTP host is not usable")
    if host in {"169.254.169.254", "fd00:ec2::254"}:
        raise ValueError("metadata host is refused")
    port = int(fields.get("port") or (465 if security == "tls" else 587))
    if port < 1 or port > 65535:
        raise ValueError("SMTP port is out of range")
    sender = header_value(str(fields.get("from_address") or ""), "from_address")
    if not valid_email(sender):
        raise ValueError("from_address is not a valid email")
    signature = body_text(str(fields.get("signature_text") or ""))
    return {
        "host": host,
        "port": port,
        "security": security,
        "from_address": sender,
        "from_name": header_value(str(fields.get("from_name") or ""), "from_name")[:120],
        "position": header_value(str(fields.get("position") or ""), "position")[:120],
        "company": header_value(str(fields.get("company") or ""), "company")[:160],
        "contact": header_value(str(fields.get("contact") or ""), "contact")[:160],
        "signature_text": signature[:2000],
        "signature_html": html_signature(signature) if signature else "",
    }


def compose(account: dict[str, Any], draft: dict[str, Any]) -> EmailMessage:
    recipient = header_value(str(draft.get("recipient") or ""), "recipient")
    if not valid_email(recipient):
        raise ValueError("recipient is not a valid email")
    subject = header_value(str(draft.get("subject") or ""), "subject")
    if not subject:
        raise ValueError("subject is empty")
    body = str(draft.get("body") or "").replace("\x00", "").strip()
    signature = str(account.get("signature_text") or "").strip()
    if signature and signature not in body:
        body = f"{body}\n\n{signature}"
    message = EmailMessage()
    sender = formataddr((account.get("from_name") or "", account["from_address"]))
    message["From"] = header_value(sender, "from")
    message["To"] = recipient
    message["Subject"] = subject
    message_id = make_msgid(domain="salespilot.local")
    message["Message-ID"] = header_value(message_id, "message-id")
    message.set_content(body)
    if account.get("signature_html"):
        message.add_alternative(
            f"<html><body><p>{html.escape(str(draft.get('body') or '')).replace(chr(10), '<br>')}</p>{account['signature_html']}</body></html>",
            subtype="html",
        )
    return message


def deliver(account: dict[str, Any], username: str, password: str, message: EmailMessage, *, timeout: int = 20) -> dict[str, Any]:
    """One SMTP transaction. Accepted means the server took the message, not that an inbox showed it."""
    message_id = str(message["Message-ID"])
    recipient = str(message["To"])
    if _TRANSPORT is not None:
        code, ambiguous = _TRANSPORT(account, username, password, message)
        return _outcome(code, ambiguous, message_id, recipient)
    context = tls_context()
    client = None
    sent_data = False
    try:
        if account["security"] == "tls":
            client = smtplib.SMTP_SSL(account["host"], int(account["port"]), timeout=timeout, context=context)
        else:
            client = smtplib.SMTP(account["host"], int(account["port"]), timeout=timeout)
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        if username:
            client.login(username, password)
        client.send_message(message)
        sent_data = True
        client.quit()
        return _outcome(250, False, message_id, recipient)
    except smtplib.SMTPResponseException as exc:
        return _outcome(int(exc.smtp_code), sent_data, message_id, recipient)
    except (TimeoutError, OSError, smtplib.SMTPException):
        return _outcome(0, sent_data, message_id, recipient)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def probe(account: dict[str, Any], username: str, password: str, *, timeout: int = 20) -> dict[str, Any]:
    if _TRANSPORT is not None:
        code, _ambiguous = _TRANSPORT(account, username, password, None)
        return {"ok": code == 250, "checked": True, "credentials_logged": False}
    context = tls_context()
    client = None
    try:
        if account["security"] == "tls":
            client = smtplib.SMTP_SSL(account["host"], int(account["port"]), timeout=timeout, context=context)
        else:
            client = smtplib.SMTP(account["host"], int(account["port"]), timeout=timeout)
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        if username:
            client.login(username, password)
        client.noop()
        client.quit()
        return {"ok": True, "checked": True, "credentials_logged": False}
    except Exception:
        return {"ok": False, "checked": True, "credentials_logged": False}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _outcome(code: int, ambiguous: bool, message_id: str, recipient: str) -> dict[str, Any]:
    if ambiguous or code == 0:
        state = "unknown"
    elif 200 <= code < 300:
        state = "accepted"
    else:
        state = "rejected"
    return {
        "state": state,
        "smtp_code": code,
        "message_id": message_id,
        "recipient": recipient,
        "inbox_delivery_proven": False,
        "retryable": state == "rejected" and not ambiguous,
    }


def new_message_id() -> str:
    return make_msgid(idstring=uuid.uuid4().hex[:12], domain="salespilot.local")
