"""Desktop write actions that reuse the existing tools. None of them can send a message.

Each one maps a UI button onto a tool the chat agent already uses, so the desktop and the chat
stay on one code path: CSV import, stored-lead qualification, email draft, inbox status/sync, and
the imported-customer list. Sending stays on `/salespilot-send` with its host choice prompt.
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from . import inbox, pipeline, storage, tools
except ImportError:
    import inbox
    import pipeline
    import storage
    import tools

_SECRET = re.compile(r"pass|secret|token|credential", re.I)


def _refuse(body: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False}
    leaked = sorted(key for key in body if _SECRET.search(str(key)))
    if leaked or pipeline.SECRET_KEYS.intersection(body) or body.get("action") == "send":
        return {"ok": False, "code": "refused", "rejected_fields": leaked,
                "error": "This route cannot send or store a secret.", "sent": False}
    return None


def _business_ref(conn, ref: str) -> dict[str, Any] | None:
    if ref:
        brand, _reason = storage.resolve_brand(conn, ref)
        return None if brand is None else storage.get_business(conn, brand["business_id"])
    return storage.get_business(conn)


def _lead_in_scope(lead_id: str, business_ref: str) -> dict[str, Any] | None:
    """The lead must belong to the requested (or active) brand: a stale pane cannot touch another brand."""
    with storage.read_only() as conn:
        lead = storage.get_lead(conn, lead_id)
        business = _business_ref(conn, business_ref)
    if lead is None or business is None or lead.get("deleted_at"):
        return None
    return lead if lead["business_id"] == business["id"] else None


def import_csv(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body)
    if refused:
        return refused
    if body.get("authorized") is not True:
        return {"ok": False, "code": "not_authorized",
                "error": "Confirm you have permission to contact these customers.", "sent": False}
    note = str(body.get("authorization_note") or "").strip()
    if not note:
        return {"ok": False, "code": "missing_authorization_note",
                "error": "Say where this list came from.", "sent": False}
    text = str(body.get("csv_text") or "")
    if len(text) > 2_000_000:
        return {"ok": False, "code": "too_large", "error": "Keep one import under 2 MB.", "sent": False}
    mapping = body.get("mapping") if isinstance(body.get("mapping"), dict) else {}
    result = json.loads(tools.import_customers({
        "csv_text": text,
        "mapping": {str(k): str(v) for k, v in mapping.items() if v},
        "authorized": True,
        "authorization_note": note[:300],
        "source": str(body.get("source") or "csv").strip()[:120] or "csv",
        "business_id": str(body.get("business_id") or ""),
    }))
    result["sent"] = False
    return result


def customers(business_ref: str = "", limit: int = 500) -> dict[str, Any]:
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "customers": [], "sent": False}
        business = _business_ref(conn, business_ref)
        if business is None:
            return {"ok": True, "customers": [], "count": 0, "sent": False}
        rows = storage.list_customers(conn, business["id"])
    items = [
        {
            "id": row["id"],
            "company": row.get("company") or "",
            "contact_name": row.get("contact_name") or "",
            "email": row.get("email") or "",
            "email_valid": bool(row.get("email_valid")),
            "phone": row.get("phone") or "",
            "phone_valid": bool(row.get("phone_valid")),
            "segment": row.get("segment") or "",
            "source": row.get("source") or "",
            "notes": row.get("notes") or "",
            "synthetic": bool(row.get("synthetic")),
            "created_at": row.get("created_at") or "",
        }
        for row in rows[:limit]
    ]
    return {"ok": True, "business_id": business["id"], "customers": items, "count": len(items),
            "total": len(rows), "sent": False}


def qualify(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body)
    if refused:
        return refused
    lead_id = str(body.get("lead_id") or "")
    if _lead_in_scope(lead_id, str(body.get("business_id") or "")) is None:
        return {"ok": False, "code": "lead_not_found", "error": "That customer is not in this brand.", "sent": False}
    result = json.loads(tools.qualify_lead({"lead_id": lead_id}))
    result["sent"] = False
    return result


def draft(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body)
    if refused:
        return refused
    lead_id = str(body.get("lead_id") or "")
    if _lead_in_scope(lead_id, str(body.get("business_id") or "")) is None:
        return {"ok": False, "code": "lead_not_found", "error": "That customer is not in this brand.", "sent": False}
    result = json.loads(tools.draft_outreach({"lead_id": lead_id, "channel": "email"}))
    if result.get("ok") and result.get("draft"):
        result["send_command"] = f"/salespilot-send {result['draft']['id']}"
    result["sent"] = False
    return result


def inbox_action(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body)
    if refused:
        return refused
    action = str(body.get("action") or "status").strip().lower()
    if action not in {"status", "sync"}:
        return {"ok": False, "code": "bad_action", "error": "Use status or sync.", "sent": False}
    with storage.unit_of_work() as conn:
        business = _business_ref(conn, str(body.get("business_id") or ""))
        if business is None:
            return {"ok": False, "code": "missing_business", "error": "Set up a brand first.", "sent": False}
        try:
            result = inbox.run(conn, business["id"], {"action": action, "days": int(body.get("days") or 30)})
        except Exception as exc:  # network/IMAP errors surface as a readable failure, never a crash
            return {"ok": False, "code": "imap_error", "error": f"Inbox check failed: {type(exc).__name__}.", "sent": False}
    result["sent"] = False
    return result
