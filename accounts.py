"""Sender identities per brand.

A brand may send from several addresses (sales@, fleet@, …). Credentials stay in Hermes secrets;
an account only names the slot that holds them. An account can never inherit another brand's
credential slot, and an unknown slot fails closed instead of quietly reusing the default one.
"""

from __future__ import annotations

from typing import Any

try:
    from . import domain, storage
except ImportError:
    import domain
    import storage

DEFAULT_SLOT = "default"


def _row(row) -> dict[str, Any]:
    return dict(row) if row else {}


def list_accounts(conn, business_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM accounts WHERE business_id=? ORDER BY status='active' DESC, address",
        (business_id,),
    ).fetchall()
    return [_row(row) for row in rows]


def get_account(conn, business_id: str, account_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM accounts WHERE business_id=? AND id=?",
        (business_id, account_id),
    ).fetchone()
    return _row(row) or None


def ensure_account(
    conn,
    business_id: str,
    address: str,
    *,
    display_name: str = "",
    credential_slot: str = DEFAULT_SLOT,
    channel: str = "email",
) -> dict[str, Any]:
    """Idempotent by (brand, address). Never rewrites a slot that is already set to something else."""
    key = str(address or "").strip().lower()
    if not key or "@" not in key:
        raise ValueError("account address must be an email")
    existing = conn.execute(
        "SELECT * FROM accounts WHERE business_id=? AND address_key=?",
        (business_id, key),
    ).fetchone()
    now = domain.iso()
    if existing is not None:
        return _row(existing)
    account_id = domain.new_id("acct")
    conn.execute(
        "INSERT INTO accounts(id, business_id, channel, address, address_key, display_name,"
        " credential_slot, status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (account_id, business_id, channel, key, key, display_name or "", credential_slot or DEFAULT_SLOT,
         "active", now, now),
    )
    return get_account(conn, business_id, account_id) or {}


def seed_from_mail_settings(conn, business_id: str) -> dict[str, Any] | None:
    """A brand that already saved SMTP settings gets one account row, slot 'default'."""
    settings = storage.get_mail_settings(conn, business_id) or {}
    address = str(settings.get("from_address") or "").strip()
    if not address:
        return None
    return ensure_account(
        conn,
        business_id,
        address,
        display_name=str(settings.get("from_name") or ""),
        credential_slot=str(settings.get("credential_slot") or DEFAULT_SLOT),
    )


def resolve(conn, business_id: str, address: str = "") -> tuple[dict[str, Any] | None, str]:
    """Pick the sender account for a brand. Returns (account, reason)."""
    wanted = str(address or "").strip().lower()
    if wanted:
        row = conn.execute(
            "SELECT * FROM accounts WHERE business_id=? AND address_key=?",
            (business_id, wanted),
        ).fetchone()
        if row is None:
            return None, "unknown_account"
        account = _row(row)
        if account.get("status") != "active":
            return None, "account_disabled"
        return account, ""

    active = [a for a in list_accounts(conn, business_id) if a.get("status") == "active"]
    if not active:
        return None, "no_account"
    if len(active) == 1:
        return active[0], ""
    default = next((a for a in active if a.get("credential_slot") == DEFAULT_SLOT), None)
    return (default or active[0]), "multiple_accounts"


def credential_slot_allowed(slot: str, available: set[str]) -> bool:
    return bool(slot) and slot in available


def credential_capacity(conn, business_id: str) -> dict[str, Any]:
    """Many From-addresses are not many connected mailboxes.

    Hermes exposes one SMTP/IMAP secret pair per profile (SALESPILOT_SMTP_USERNAME /
    SALESPILOT_SMTP_PASSWORD). Every account row therefore resolves to the same slot until a
    second secret pair exists; anything else fails closed instead of borrowing credentials.
    """
    rows = list_accounts(conn, business_id)
    slots = sorted({row.get("credential_slot") or DEFAULT_SLOT for row in rows})
    return {
        "addresses": len(rows),
        "slots": slots,
        "connected_mailboxes": 1 if len(slots) <= 1 else 1,
        "max_credentials_available": 1,
        "note": "From-addresses can differ; the authenticated mailbox cannot, until Hermes adds a "
                "second secret slot. A mismatched sender is refused, never silently reused.",
    }
