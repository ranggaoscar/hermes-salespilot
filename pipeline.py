"""Persistent prospect pipeline. No network, no secrets, no send."""

from __future__ import annotations

from typing import Any

try:
    from . import domain, extract, storage
except ImportError:
    import domain
    import extract
    import storage

STATUSES = (
    "discovered",
    "qualified",
    "draft_ready",
    "contacted",
    "replied",
    "follow_up_due",
    "followed_up",
    "not_interested",
    "do_not_contact",
    "archived",
)
# Rows written by earlier versions keep their value; the read path maps them once.
LEGACY_STATUSES = {
    "new": "discovered",
    "drafted": "draft_ready",
    "smtp_accepted": "contacted",
    "follow_up_done": "followed_up",
}
SORTS = ("updated", "company", "status")
SECRET_KEYS = {"password", "token", "access_token", "refresh_token", "smtp_password", "secret"}

# A lead in one of these states must never be mailed again, whatever a draft says. The draft is a
# snapshot from the moment it was written; consent and refusal are not. `send_block_reason` is the one
# gate the send path reads, so a stale draft cannot outlive a refusal, a bounce or an archive.
BLOCKED_STATUSES = (
    "not_interested",
    "do_not_contact",
    "bounced",
    "rejected",
    "suppressed",
    "archived",
)
BLOCKED_STAGES = ("rejected", "suppressed", "archived")


def send_block_reason(lead: dict[str, Any] | None) -> str:
    """Return the reason this lead must not receive email, or '' when it may be drafted/sent."""
    if not lead:
        return "lead_missing"
    if lead.get("deleted_at"):
        return "lead_deleted"
    if lead.get("archived"):
        return "lead_archived"
    status = LEGACY_STATUSES.get(str(lead.get("pipeline_status") or ""), str(lead.get("pipeline_status") or ""))
    if status in BLOCKED_STATUSES:
        return f"lead_{status}"
    stage = str(lead.get("stage") or "")
    if stage in BLOCKED_STAGES:
        return f"lead_{stage}"
    return ""


def preferences(args: dict[str, Any]) -> dict[str, Any]:
    mode = str(args.get("mail_mode") or "").strip().lower()
    if mode not in {"", "none", "smtp", "gmail_oauth"}:
        mode = ""
    research_only = bool(args.get("research_only")) or mode == "none"
    mail = {
        "mode": mode,
        "research_only": research_only,
        "gmail_oauth_connected": False,
        "token_stored": False,
        "inbox_delivery": "not_observed",
    }
    if mode == "gmail_oauth":
        mail["blocker"] = "This host has no Gmail OAuth scope. No token is stored."
    return {
        "research_only": research_only,
        "target_market": str(args.get("target_market") or "").strip()[:240],
        "discovery_query": str(args.get("discovery_query") or "").strip()[:240],
        "mail": mail,
    }


def public_row(lead: dict[str, Any], suppressed: bool = False) -> dict[str, Any]:
    status = lead.get("pipeline_status") or lead.get("stage") or "discovered"
    status = LEGACY_STATUSES.get(status, status)
    readiness = domain.recipient_readiness(lead.get("email"), lead.get("role"))
    stage = domain.stage_label(
        str(lead.get("stage") or ""),
        status,
        readiness["status"],
        suppressed=suppressed,
        approved_contact=status == "draft_ready",
    )
    recommended = "skip"
    if stage == "discovered":
        recommended = "research_company"
    elif stage == "qualified_company":
        if readiness["status"] == "business_contact":
            recommended = "review_business_contact"
        elif readiness["status"] in {"role_generic", "missing", "person_unknown_role"}:
            recommended = "find_decision_maker"
        else:
            recommended = "qualify_for_outreach"
    elif stage == "ready_for_outreach":
        recommended = "await_approval"
    next_action = {
        "discovered": "Review the quoted evidence before qualifying.",
        "qualified": "Draft stays behind /salespilot-send.",
        "draft_ready": "Wait for slash-command approval. Do not send from this page.",
        "contacted": "SMTP accepted is not inbox delivery. Follow up only if a reply is recorded.",
        "replied": "Read the reply before any further send.",
        "follow_up_due": "Record the follow-up when it is actually done.",
        "followed_up": "No automatic next send.",
        "not_interested": "Leave the record. Do not draft again.",
        "do_not_contact": "Suppressed. Do not re-enter outreach.",
        "archived": "Archived. Restore it before any new outreach.",
    }.get(status, "Review the record.")
    if stage == "qualified_company":
        if recommended == "find_decision_maker":
            next_action = "Company matches the ICP. Find the fleet or procurement owner; the desk on file is not a buyer."
        elif recommended == "review_business_contact":
            next_action = "Official procurement/partnership desk. Keep it, review before drafting."
        else:
            next_action = "Company and contact both fit. Qualify to release it for drafting."
    elif stage == "ready_for_outreach":
        next_action = "Relevant contact on a verified source. Send still waits for /salespilot-send approval."
    elif stage == "suppressed":
        next_action = "Suppressed. Do not re-enter outreach."
    return {
        "id": lead["id"],
        "company": lead.get("company") or "",
        "contact_name": lead.get("contact_name") or "",
        "email": lead.get("email") or "",
        "contact_source": lead.get("source_url") or "",
        "source_url": lead.get("source_url") or "",
        "evidence": lead.get("evidence") or "",
        "offer_match": lead.get("decision") or "",
        "status": status,
        "stage": stage,
        "outreach_ready": stage == "ready_for_outreach",
        "recommended_action": recommended,
        "company_fit": "fit" if str(lead.get("stage") or "") == "qualified_company" else (
            "excluded" if stage == "rejected" else "unproven"),
        "readiness": {
            "status": readiness["status"],
            "reason": readiness["reason"],
            "desk": readiness["desk"],
            "requires_review": readiness["requires_review"],
            "deliverability": readiness["deliverability"],
            "deliverability_reason": readiness["deliverability_reason"],
        },
        "recipient": {
            "kind": readiness["kind"],
            "role": readiness["role_label"],
            "deliverability": readiness["deliverability"],
            "reason": readiness["deliverability_reason"],
        },
        "note": lead.get("owner_note") or "",
        "archived": bool(lead.get("archived")),
        "deleted": bool(lead.get("deleted_at")),
        "outreach_blocked": bool(send_block_reason({**lead, "pipeline_status": status})),
        "inbox_delivery": "not_observed",
        "last_activity": lead.get("updated_at") or "",
        "next_action": next_action,
        "updated_at": lead.get("updated_at") or "",
        "sent": False,
    }


def list_prospects(
    conn,
    business_id: str,
    query: str = "",
    status: str = "",
    sort: str = "updated",
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Paged prospects plus the total that match, filtered in SQLite."""
    leads, total = storage.list_leads_page(
        conn,
        business_id,
        query=query,
        status=status,
        sort=sort,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    suppressed = storage.suppressed_emails(conn, business_id)
    return [public_row(lead, suppressed=str(lead.get("email") or "").lower() in suppressed) for lead in leads], total


def _lead(conn, business_id: str, lead_id: str) -> dict[str, Any] | None:
    lead = storage.get_lead(conn, lead_id)
    if lead is None or lead.get("business_id") != business_id:
        return None
    return lead


def set_status(conn, business_id: str, lead_id: str, status: str, actor: str = "operator") -> dict[str, Any]:
    status = LEGACY_STATUSES.get(status, status)
    if status not in STATUSES:
        return {"ok": False, "code": "bad_status", "error": "Status is not in the lifecycle."}
    lead = _lead(conn, business_id, lead_id)
    if lead is None or lead.get("deleted_at"):
        return {"ok": False, "code": "missing_lead", "error": "Prospect is not in this business."}
    current = lead.get("pipeline_status") or "new"
    if current == status:
        return {"ok": True, "prospect": public_row(lead), "changed": False, "sent": False}
    storage.set_pipeline_fields(conn, lead_id, pipeline_status=status)
    # A refusal is consent data, not just a label: both "do not contact" and "not interested" suppress
    # the address, so a later draft (or an older one) cannot mail this person again.
    if status == "do_not_contact" and lead.get("email"):
        storage.add_suppression(conn, business_id, lead["email"], "do_not_contact")
    elif status == "not_interested" and lead.get("email"):
        storage.add_suppression(conn, business_id, lead["email"], "not_interested")
    storage.add_event(conn, "status_changed", business_id, lead_id, {"from": current, "to": status, "actor": actor})
    saved = storage.get_lead(conn, lead_id)
    return {"ok": True, "prospect": public_row(saved or lead), "changed": True, "sent": False}


def add_note(conn, business_id: str, lead_id: str, note: str) -> dict[str, Any]:
    text = note.strip()
    if not text or len(text) > 500:
        return {"ok": False, "code": "bad_note", "error": "Note must be 1 to 500 characters."}
    lead = _lead(conn, business_id, lead_id)
    if lead is None or lead.get("deleted_at"):
        return {"ok": False, "code": "missing_lead", "error": "Prospect is not in this business."}
    storage.set_pipeline_fields(conn, lead_id, owner_note=text)
    storage.add_event(conn, "note_added", business_id, lead_id, {"note": text})
    saved = storage.get_lead(conn, lead_id)
    return {"ok": True, "prospect": public_row(saved or lead), "sent": False}


def archive(conn, business_id: str, lead_id: str) -> dict[str, Any]:
    lead = _lead(conn, business_id, lead_id)
    if lead is None or lead.get("deleted_at"):
        return {"ok": False, "code": "missing_lead", "error": "Prospect is not in this business."}
    if lead.get("archived"):
        return {"ok": True, "prospect": public_row(lead), "changed": False, "sent": False}
    storage.set_pipeline_fields(conn, lead_id, archived=1)
    storage.add_event(conn, "archived", business_id, lead_id, {})
    saved = storage.get_lead(conn, lead_id)
    return {"ok": True, "prospect": public_row(saved or lead), "changed": True, "sent": False}


def delete(conn, business_id: str, lead_id: str) -> dict[str, Any]:
    lead = _lead(conn, business_id, lead_id)
    if lead is None:
        return {"ok": False, "code": "missing_lead", "error": "Prospect is not in this business."}
    if lead.get("deleted_at"):
        return {"ok": True, "deleted": True, "changed": False, "sent": False}
    storage.set_pipeline_fields(conn, lead_id, deleted_at=domain.iso(), pipeline_status="do_not_contact")
    if lead.get("email"):
        storage.add_suppression(conn, business_id, lead["email"], "deleted")
    storage.add_event(conn, "deleted", business_id, lead_id, {"explicit": True})
    return {"ok": True, "deleted": True, "changed": True, "sent": False}


def record_smtp_accepted(conn, business_id: str, lead_id: str, message_id: str) -> dict[str, Any]:
    result = set_status(conn, business_id, lead_id, "contacted", actor="smtp")
    if not result.get("ok"):
        return result
    storage.add_event(conn, "smtp_accepted", business_id, lead_id, {
        "message_id": message_id,
        "inbox_delivery": "not_observed",
        "reply_inferred": False,
    })
    result["inbox_delivery"] = "not_observed"
    result["reply_inferred"] = False
    return result


def record_reply(conn, business_id: str, lead_id: str, observation: dict[str, Any]) -> dict[str, Any]:
    message_id = str(observation.get("message_id") or "").strip()
    quote = str(observation.get("quote") or "").strip()
    if not message_id or not quote:
        return {"ok": False, "code": "reply_not_observed", "error": "A reply needs an authorized message id and a quoted body. SMTP success is not a reply."}
    if observation.get("authorized") is not True:
        return {"ok": False, "code": "reply_not_authorized", "error": "Reply detection requires an authorized mailbox observation."}
    lead = _lead(conn, business_id, lead_id)
    if lead is None:
        return {"ok": False, "code": "missing_lead", "error": "Prospect is not in this business."}
    storage.add_event(conn, "reply_observed", business_id, lead_id, {"message_id": message_id, "quote": quote[:240]})
    return {"ok": True, "reply_observed": True, "inbox_delivery": "observed", "sent": False}


def discover(conn, business: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    extracted = extract.extract_prospect("", sources)
    if not extracted.get("ok"):
        return {**extracted, "sent": False, "saved": False}
    email = str(extracted.get("email") or "")
    if email and email.lower() not in "\n".join(str(item.get("text") or "") for item in sources).lower():
        return {"ok": False, "code": "contact_not_in_source", "error": "Contact was not in the permitted text.", "sent": False}
    lead = {
        "company": extracted.get("company") or "",
        "contact_name": extracted.get("contact_name") or "",
        "role": extracted.get("role") or "",
        "email": email,
        "phone": extracted.get("phone") or "",
        "segment": extracted.get("segment") or "",
        "country": extracted.get("country") or "",
        "source_url": extracted.get("source_url") or "",
        "evidence": extracted.get("evidence") or "",
        "citations": extracted.get("citations") or [],
    }
    from domain import qualify
    result = qualify(business, lead)
    saved = storage.save_lead(conn, business["id"], lead, result)
    suppressed = bool(email) and storage.is_suppressed(conn, business["id"], email)
    status = "do_not_contact" if suppressed else ("qualified" if result["decision"] == "qualified" else "new")
    storage.set_pipeline_fields(conn, saved["id"], pipeline_status=status, email_key=email.lower())
    if suppressed:
        storage.add_event(conn, "suppressed_blocked", business["id"], saved["id"], {"email": email.lower()})
    else:
        storage.add_event(conn, "discovered", business["id"], saved["id"], {"source_url": lead["source_url"]})
    existing = conn.execute(
        "SELECT id FROM opportunities WHERE business_id=? AND lead_id=? LIMIT 1",
        (business["id"], saved["id"]),
    ).fetchone()
    if existing is None:
        storage.save_opportunity(conn, business["id"], {
        "lead_id": saved["id"],
        "title": lead["company"] or "Untitled prospect",
        "verified": [lead["evidence"]] if lead["evidence"] else [],
        "assumptions": [],
        "unknowns": extracted.get("unknowns") or [],
        "fit": result["decision"],
        "next_question": "Confirm the quoted contact before any draft.",
        "citations": extracted.get("citations") or [],
        "grounded": bool(lead["evidence"]),
    })
    fresh = storage.get_lead(conn, saved["id"]) or saved
    return {
        "ok": True,
        "saved": True,
        "duplicate": bool(saved.get("updated")),
        "prospect": public_row(fresh),
        "outreach_blocked": suppressed or bool(send_block_reason(fresh)),
        "intent": "not_inferred",
        "sent": False,
    }
