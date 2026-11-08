"""Follow-up state computed from history — never from a hand-set label.

Inputs: outbound messages (verified sends), inbound replies, suppression rows and the brand's
follow-up policy. Output: one state per contact plus the reason, so the UI can explain it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from . import domain, storage
except ImportError:
    import domain
    import storage

DEFAULT_FOLLOWUP_DAYS = 3
COLD_AFTER_DAYS = 21
MAX_ATTEMPTS = 3
STOPPED_STATUSES = {"do_not_contact", "not_interested", "archived"}


def _parse(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def policy_for(conn, business_id: str) -> dict[str, int]:
    """Per-brand policy, stored on the business row so both UI and tools agree."""
    row = conn.execute(
        "SELECT followup_days, followup_max_attempts, followup_cold_days FROM businesses WHERE id=?",
        (business_id,),
    ).fetchone()
    days = int((row["followup_days"] if row else 0) or DEFAULT_FOLLOWUP_DAYS)
    attempts = int((row["followup_max_attempts"] if row else 0) or MAX_ATTEMPTS)
    cold = int((row["followup_cold_days"] if row else 0) or COLD_AFTER_DAYS)
    return {"followup_days": max(1, days), "cold_after_days": max(1, cold), "max_attempts": max(1, attempts)}


def set_policy(conn, business_id: str, days: int, max_attempts: int, cold_days: int) -> dict[str, int]:
    conn.execute(
        "UPDATE businesses SET followup_days=?, followup_max_attempts=?, followup_cold_days=?, updated_at=? WHERE id=?",
        (max(1, int(days)), max(1, int(max_attempts)), max(1, int(cold_days)), domain.iso(), business_id),
    )
    return policy_for(conn, business_id)


def state_for(conn, business_id: str, lead: dict[str, Any], policy: dict[str, int] | None = None) -> dict[str, Any]:
    policy = policy or policy_for(conn, business_id)
    lead_id = lead["id"]
    outbound = conn.execute(
        "SELECT COUNT(*) AS n, MAX(sent_at) AS last FROM messages WHERE business_id=? AND lead_id=? AND direction='outbound'",
        (business_id, lead_id),
    ).fetchone()
    inbound = conn.execute(
        "SELECT COUNT(*) AS n, MAX(received_at) AS last FROM messages WHERE business_id=? AND lead_id=? AND direction='inbound'",
        (business_id, lead_id),
    ).fetchone()
    attempts = int(outbound["n"] or 0)
    last_out = _parse(outbound["last"] or "") or _parse(lead.get("contacted_at") or "")
    last_in = _parse(inbound["last"] or "") or _parse(lead.get("replied_at") or "")
    suppressed = bool(lead.get("email")) and storage.is_suppressed(conn, business_id, lead["email"])
    status = lead.get("pipeline_status") or "discovered"

    if suppressed or status in STOPPED_STATUSES:
        return {
            "state": "stopped", "reason": "suppressed" if suppressed else f"status:{status}",
            "attempts": attempts, "paused": False, "next_due": "", "days_since_outbound": None,
        }

    if int(inbound["n"] or 0) > 0 or lead.get("replied_at"):
        return {
            "state": "replied", "reason": "inbound message verified",
            "attempts": attempts, "paused": True, "next_due": "",
            "days_since_outbound": round((_now() - last_out).total_seconds() / 86400, 1) if last_out else None,
        }

    if not last_out:
        return {"state": "not_contacted", "reason": "no verified send yet", "attempts": 0,
                "paused": False, "next_due": "", "days_since_outbound": None}

    due = last_out + timedelta(days=policy["followup_days"])
    age_days = (_now() - last_out).total_seconds() / 86400
    if age_days >= policy["cold_after_days"] and attempts >= 2:
        return {"state": "cold", "reason": f"no reply after {attempts} attempts and {int(age_days)} days",
                "attempts": attempts, "paused": False, "next_due": "", "days_since_outbound": round(age_days, 1)}
    if attempts >= policy["max_attempts"]:
        return {"state": "exhausted", "reason": f"attempt cap reached ({attempts})",
                "attempts": attempts, "paused": False, "next_due": "", "days_since_outbound": round(age_days, 1)}
    if _now() >= due:
        return {"state": "followup_due", "reason": f"{int(age_days)} days since the last send",
                "attempts": attempts, "paused": False, "next_due": due.isoformat(timespec="seconds"),
                "days_since_outbound": round(age_days, 1)}
    return {"state": "awaiting_reply", "reason": f"{int(age_days)} days since the last send",
            "attempts": attempts, "paused": False, "next_due": due.isoformat(timespec="seconds"),
            "days_since_outbound": round(age_days, 1)}


def board(conn, business_id: str, limit: int = 200) -> dict[str, Any]:
    """Every prospect with its computed state, split into follow-up buckets."""
    policy = policy_for(conn, business_id)
    rows = conn.execute(
        "SELECT * FROM leads WHERE business_id=? AND deleted_at='' ORDER BY updated_at DESC LIMIT ?",
        (business_id, limit),
    ).fetchall()
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        lead = storage._lead_from_row(row)
        if not lead:
            continue
        state = state_for(conn, business_id, lead, policy)
        entry = {
            "lead_id": lead["id"],
            "company": lead.get("company") or "",
            "email": lead.get("email") or "",
            "status": lead.get("pipeline_status") or "discovered",
            **state,
        }
        buckets.setdefault(state["state"], []).append(entry)
    return {
        "ok": True,
        "policy": policy,
        "counts": {name: len(items) for name, items in sorted(buckets.items())},
        "buckets": buckets,
        "sent": False,
    }
