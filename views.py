"""Read-only mission views. No secrets and no send path."""

from __future__ import annotations

from typing import Any

try:
    from . import commands, followstate, graph, inbox, pipeline, storage
except ImportError:
    import commands
    import followstate
    import graph
    import inbox
    import pipeline
    import storage


def _businesses(conn) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM businesses ORDER BY updated_at DESC, id").fetchall()
    return [storage._business_from_row(row) for row in rows]


def _one(conn, business_id: str) -> dict[str, Any] | None:
    if business_id:
        brand, _reason = storage.resolve_brand(conn, business_id)
        if brand is None:
            return None
        return storage.get_business(conn, brand["business_id"])
    brand = storage.active_brand(conn)
    if brand is not None:
        chosen = storage.get_business(conn, brand["business_id"])
        if chosen is not None:
            return chosen
    rows = _businesses(conn)
    return rows[0] if rows else None


def brands() -> dict[str, Any]:
    """Brand switcher payload: every brand plus the active one. Never includes credentials."""
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "brands": [], "active": None, "sent": False}
        rows = storage.list_brands(conn)
        active = storage.active_brand(conn)
        return {
            "ok": True,
            "brands": [
                {
                    "id": item["id"],
                    "slug": item["slug"],
                    "display_name": item["display_name"],
                    "is_default": bool(item["is_default"]),
                }
                for item in rows
            ],
            "active": None if active is None else {"id": active["id"], "slug": active["slug"], "display_name": active["display_name"]},
            "sent": False,
        }


def switch_brand(body: dict[str, Any]) -> dict[str, Any]:
    ref = str((body or {}).get("brand") or (body or {}).get("brand_id") or "").strip()
    with storage.unit_of_work() as conn:
        brand, reason = storage.resolve_brand(conn, ref)
        if brand is None:
            return {"ok": False, "code": reason or "unknown_brand", "error": "That brand was not found.", "sent": False}
        storage.set_active_brand(conn, brand["id"])
    return brands()


def overview(business_id: str = "") -> dict[str, Any]:
    with storage.read_only() as conn:
        rows = _businesses(conn)
        chosen = _one(conn, business_id)
        if chosen is None:
            return {"ok": True, "businesses": [], "missions": [], "counts": {"missions": 0, "signals": 0, "drafts": 0}, "sent": False}
        missions = [dict(row) for row in conn.execute(
            "SELECT * FROM missions WHERE business_id=? ORDER BY updated_at DESC",
            (chosen["id"],),
        ).fetchall()]
        signals = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE business_id=?",
            (chosen["id"],),
        ).fetchone()[0]
        drafts = conn.execute(
            "SELECT COUNT(*) FROM drafts WHERE business_id=?",
            (chosen["id"],),
        ).fetchone()[0]
        return {
            "ok": True,
            "business_id": chosen["id"],
            "business_name": chosen["name"],
            "businesses": [{"id": item["id"], "name": item["name"]} for item in rows],
            "missions": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "updated_at": item["updated_at"],
                    "signals": conn.execute("SELECT COUNT(*) FROM signals WHERE mission_id=?", (item["id"],)).fetchone()[0],
                    "dna": conn.execute("SELECT COUNT(*) FROM dna_claims WHERE mission_id=?", (item["id"],)).fetchone()[0],
                }
                for item in missions
            ],
            "counts": {"missions": len(missions), "signals": signals, "drafts": drafts},
            "sent": False,
            "sending_enabled": False,
        }


def radar(business_id: str = "", mission_id: str = "") -> dict[str, Any]:
    with storage.read_only() as conn:
        business = _one(conn, business_id)
        if business is None:
            return {"ok": True, "cards": [], "unknowns": ["No saved business."], "sent": False}
        query = "SELECT * FROM signals WHERE business_id=?"
        params: list[Any] = [business["id"]]
        if mission_id:
            query += " AND mission_id=?"
            params.append(mission_id)
        query += " ORDER BY observed_on DESC, id"
        signals = [dict(row) for row in conn.execute(query, params).fetchall()]
        cards = []
        for signal in signals:
            card = graph.card_for(signal)
            card["unknowns"] = []
            if not signal.get("email"):
                card["unknowns"].append("No public contact was quoted.")
            if signal.get("offer_fit") != "mapped":
                card["unknowns"].append("No saved offer matched this signal.")
            if signal.get("intent") == "not_inferred":
                card["unknowns"].append("Buying intent was not stated in the source.")
            card["confidence"] = signal.get("confidence") or "sourced"
            card["mission_id"] = signal["mission_id"]
            cards.append(card)
        return {
            "ok": True,
            "business_id": business["id"],
            "cards": cards,
            "duplicate_keys": len(signals) == len({item["dedupe_key"] for item in signals}),
            "sent": False,
            "sending_enabled": False,
        }


def outreach(business_id: str = "") -> dict[str, Any]:
    with storage.read_only() as conn:
        business = _one(conn, business_id)
        if business is None:
            return {"ok": True, "drafts": [], "history": [], "sent": False}
        settings = storage.get_mail_settings(conn, business["id"]) or {}
        drafts = []
        for row in conn.execute("SELECT * FROM drafts WHERE business_id=? ORDER BY created_at DESC", (business["id"],)).fetchall():
            item = dict(row)
            drafts.append({
                "id": item["id"],
                "lead_id": item.get("lead_id") or "",
                "channel": item.get("channel") or "",
                "created_at": item.get("created_at") or "",
                "recipient": item.get("recipient") or "",
                "subject": item.get("subject") or "",
                "body": item.get("body") or "",
                "status": item.get("status") or "",
                "signature": settings.get("signature_text") or "",
                "from": settings.get("from_address") or "",
                "send_command": f"/salespilot-send {item['id']}",
                "sent": False,
            })
        history = []
        for row in conn.execute("SELECT * FROM deliveries WHERE business_id=? ORDER BY created_at DESC", (business["id"],)).fetchall():
            item = dict(row)
            state = item.get("state") or ""
            history.append({
                "id": item["id"],
                "draft_id": item["draft_id"],
                "recipient": item["recipient"],
                "message_id": item["message_id"],
                "delivery_status": "smtp_handoff" if state == "accepted" else state,
                "inbox_delivery": "not_observed",
                "smtp_code": item.get("smtp_code") or 0,
            })
        approvals = [
            {"id": item["id"], "draft_id": item["draft_id"], "status": item["status"]}
            for item in storage.list_approvals(conn, business["id"])
        ]
        return {
            "ok": True,
            "business_id": business["id"],
            "from": settings.get("from_address") or "",
            "signature": settings.get("signature_text") or "",
            "drafts": drafts,
            "history": history,
            "approvals": approvals,
            "send_via_rest": False,
            "sent": False,
            "sending_enabled": False,
        }


def dna(business_id: str = "") -> dict[str, Any]:
    with storage.read_only() as conn:
        business = _one(conn, business_id)
        if business is None:
            return {"ok": True, "claims": [], "sent": False}
        claims = [dict(row) for row in conn.execute(
            "SELECT * FROM dna_claims WHERE business_id=? ORDER BY created_at, id",
            (business["id"],),
        ).fetchall()]
        settings = storage.get_mail_settings(conn, business["id"]) or {}
        user_set, password_set = commands.secret_flags()
        return {
            "ok": True,
            "business_id": business["id"],
            "name": business["name"],
            "offer": business.get("offer") or "",
            "claims": [
                {"offer": item["offer"], "segment": item["segment"], "quote": item["quote"], "source_url": item["source_url"], "confidence": item["confidence"]}
                for item in claims
            ],
            "mail": {
                "configured": bool(settings),
                "host": settings.get("host") or "",
                "port": settings.get("port") or 0,
                "security": settings.get("security") or "",
                "from_address": settings.get("from_address") or "",
                "username_present": user_set,
                "password_present": password_set,
            },
            "sent": False,
        }


def pipeline_view(business_id: str = "", query: str = "", status: str = "", sort: str = "updated", include_archived: bool = False, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "migrated": False, "prospects": [], "sent": False, "sending_enabled": False}
        business = _one(conn, business_id)
        if business is None:
            return {"ok": True, "prospects": [], "count": 0, "sent": False, "sending_enabled": False}
        rows, total = pipeline.list_prospects(conn, business["id"], query, status, sort, include_archived, limit, offset)
        policy = followstate.policy_for(conn, business["id"])
        enriched = []
        for row in rows:
            lead = storage.get_lead(conn, row["id"]) or {}
            item = dict(row)
            item["followup"] = followstate.state_for(conn, business["id"], lead, policy) if lead else {}
            account = conn.execute(
                "SELECT address, display_name FROM accounts WHERE business_id=? AND id=?",
                (business["id"], lead.get("account_id") or ""),
            ).fetchone() if lead.get("account_id") else None
            item["sender"] = (dict(account) if account else {})
            item["introduced_at"] = lead.get("contacted_at") or ""
            item["last_reply_at"] = lead.get("replied_at") or ""
            item["last_reply_excerpt"] = lead.get("last_inbound_excerpt") or ""
            item["needs_human"] = bool(lead.get("needs_human"))
            enriched.append(item)
        events = [
            {"kind": item["kind"], "ref_id": item["ref_id"], "created_at": item["created_at"]}
            for item in storage.list_events(conn, business["id"])
            if item["kind"] in {"discovered", "status_changed", "smtp_accepted", "reply_observed", "archived", "deleted", "note_added"}
        ]
        prefs = (business.get("profile") or {})
        settings = storage.get_mail_settings(conn, business["id"]) or {}
        user_set, password_set = commands.secret_flags()
        return {
            "ok": True,
            "business_id": business["id"],
            "brand": {"id": business["id"], "display_name": business["name"]},
            "research_only": bool((prefs.get("mail") or {}).get("research_only")),
            "gmail_oauth_connected": False,
            "gmail_oauth": "unavailable",
            "token_stored": False,
            "mail": {
                "configured": bool(settings),
                "host": settings.get("host") or "",
                "from_address": settings.get("from_address") or "",
                "signature_present": bool(settings.get("signature_text")),
                "username_present": user_set,
                "password_present": password_set,
            },
            "prospects": enriched,
            "count": len(rows),
            "followup_counts": followstate.board(conn, business["id"], 500)["counts"],
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": events[-12:],
            "sent": False,
            "sending_enabled": False,
            "send_via_rest": False,
        }


def pipeline_change(body: dict[str, Any]) -> dict[str, Any]:
    body = body or {}
    if pipeline.SECRET_KEYS.intersection(body) or body.get("action") == "send":
        return {"ok": False, "code": "refused", "error": "This route cannot send or store a secret.", "sent": False}
    action = str(body.get("action") or "")
    if action not in {"status", "note", "archive", "delete"}:
        return {"ok": False, "code": "bad_action", "error": "UI can note, change status, archive, or delete. Discovery stays on the tool.", "sent": False}
    with storage.unit_of_work() as conn:
        business = _one(conn, str(body.get("business_id") or ""))
        if business is None:
            return {"ok": False, "code": "missing_business", "error": "No business in this profile.", "sent": False}
        lead_id = str(body.get("lead_id") or "")
        if action == "status":
            wanted = str(body.get("status") or "")
            return pipeline.set_status(conn, business["id"], lead_id, pipeline.LEGACY_STATUSES.get(wanted, wanted), "desktop")
        if action == "note":
            return pipeline.add_note(conn, business["id"], lead_id, str(body.get("note") or ""))
        if action == "archive":
            return pipeline.archive(conn, business["id"], lead_id)
        if body.get("confirm_delete") is not True:
            return {"ok": False, "code": "delete_not_confirmed", "error": "Delete requires confirm_delete.", "sent": False}
        return pipeline.delete(conn, business["id"], lead_id)


def hot_prospects(business_id: str = "", limit: int = 50) -> dict[str, Any]:
    """Warm prospects: a verified reply, or an operator-flagged need for a human."""
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "prospects": [], "sent": False}
        business = _one(conn, business_id)
        if business is None:
            return {"ok": True, "prospects": [], "count": 0, "sent": False}
        policy = followstate.policy_for(conn, business["id"])
        rows = conn.execute(
            """SELECT * FROM leads WHERE business_id=? AND deleted_at='' AND archived=0
               AND pipeline_status NOT IN ('do_not_contact','not_interested','archived')
               ORDER BY replied_at DESC, score DESC LIMIT ?""",
            (business["id"], limit * 4),
        ).fetchall()
        items = []
        for row in rows:
            lead = storage._lead_from_row(row)
            if not lead:
                continue
            state = followstate.state_for(conn, business["id"], lead, policy)
            messages = storage.list_messages(conn, business["id"], lead["id"], limit=20)
            human_intents = {"interested", "neutral", "not_interested", "unsubscribe"}
            inbound = [m for m in messages if m["direction"] == "inbound" and m.get("intent") in human_intents]
            interested = [m for m in inbound if m["intent"] == "interested"]
            if not interested and not (lead.get("needs_human") and inbound):
                continue
            messages = messages[:6]
            items.append({
                "lead_id": lead["id"],
                "company": lead.get("company") or "",
                "email": lead.get("email") or "",
                "status": lead.get("pipeline_status") or "",
                "score": lead.get("score") or 0,
                "reply_excerpt": lead.get("last_inbound_excerpt") or "",
                "replied_at": lead.get("replied_at") or "",
                "needs_human": bool(lead.get("needs_human")),
                "account_id": lead.get("account_id") or "",
                "followup": state,
                "interest_evidence": [
                    {"message_id": m["message_id"], "intent": m["intent"], "at": m["received_at"],
                     "excerpt": (m.get("body_excerpt") or "")[:240], "level": m["evidence_level"]}
                    for m in interested
                ],
                "evidence": [
                    {"direction": m["direction"], "at": m["sent_at"] or m["received_at"], "intent": m.get("intent", ""),
                     "level": m["evidence_level"], "excerpt": (m.get("body_excerpt") or "")[:160]}
                    for m in messages
                ],
            })
        return {"ok": True, "brand": {"id": business["id"], "display_name": business["name"]},
                "prospects": items, "count": len(items), "sent": False}


def customer_timeline(lead_id: str, business_id: str = "", limit: int = 100) -> dict[str, Any]:
    """Full message + follow-up + event history for one contact. Read-only."""
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "messages": [], "sent": False}
        lead = storage.get_lead(conn, lead_id)
        if lead is None or lead.get("deleted_at"):
            return {"ok": False, "code": "lead_not_found", "messages": [], "sent": False}
        brand_id = lead["business_id"]
        business = _one(conn, business_id) or storage.get_business(conn, brand_id)
        if business and business["id"] != brand_id:
            return {"ok": False, "code": "brand_mismatch", "messages": [], "sent": False}
        messages = storage.list_messages(conn, brand_id, lead_id, limit)
        followups = [dict(row) for row in conn.execute(
            "SELECT * FROM followups WHERE business_id=? AND lead_id=? ORDER BY due_on",
            (brand_id, lead_id),
        ).fetchall()]
        events = [dict(row) for row in conn.execute(
            "SELECT * FROM events WHERE business_id=? AND ref_id=? ORDER BY created_at DESC LIMIT 100",
            (brand_id, lead_id),
        ).fetchall()]
        policy = followstate.policy_for(conn, brand_id)
        state = followstate.state_for(conn, brand_id, lead, policy)
        return {
            "ok": True,
            "lead_id": lead_id,
            "company": lead.get("company") or "",
            "email": lead.get("email") or "",
            "status": lead.get("pipeline_status") or "",
            "followup": state,
            "messages": [
                {"id": m["id"], "direction": m["direction"], "at": m["sent_at"] or m["received_at"],
                 "subject": m["subject"], "sender": m["sender"], "recipient": m["recipient"],
                 "intent": m.get("intent", ""), "evidence_level": m["evidence_level"],
                 "delivery_state": m["delivery_state"], "message_id": m["message_id"],
                 "excerpt": (m.get("body_excerpt") or "")[:400]}
                for m in messages
            ],
            "followups": followups,
            "events": events,
            "sent": False,
        }
