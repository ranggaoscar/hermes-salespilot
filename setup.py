"""First-run setup. No secrets, no invented prospects, no send."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

try:
    from . import commands, domain, pipeline, plugin_settings, storage, tools, views
except ImportError:
    import commands
    import domain
    import pipeline
    import plugin_settings
    import storage
    import tools
    import views


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

SECRET_KEYS = pipeline.SECRET_KEYS | {
    "username",
    "smtp_username",
    "smtp_password",
    "api_key",
    "authorization",
}


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SECRET_KEYS or "password" in lowered or "token" in lowered or "secret" in lowered:
                continue
            out[key] = _clean(item)
        return out
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, str) and len(value) > 240 and "@" in value and " " not in value:
        return ""
    return value


def _refuse(body: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False, "sending_enabled": False}
    if SECRET_KEYS.intersection(body) or body.get("action") == "send":
        return {
            "ok": False,
            "code": "secret_refused",
            "error": "This form cannot accept a password, token, or send request.",
            "sent": False,
            "sending_enabled": False,
        }
    return None


def _suggestions(business: dict[str, Any] | None) -> list[dict[str, str]]:
    if not business:
        return []
    found = []
    for claim in business.get("citations") or []:
        if not isinstance(claim, dict):
            continue
        text = str(claim.get("segment") or claim.get("quote") or "").strip()
        if text:
            found.append({"label": text[:160], "source": "business_dna", "review": True})
    market = str((business.get("profile") or {}).get("target_market") or "").strip()
    if market and not found:
        found.append({"label": market[:160], "source": "operator_target_market", "review": True})
    return found[:6]


def _step(business: dict[str, Any] | None, mail: dict[str, Any] | None) -> int:
    if business is None:
        return 1
    profile = business.get("profile") or {}
    if not profile.get("mail_choice"):
        return 2
    if not (business.get("icp") or {}).get("segments"):
        return 3
    if not profile.get("discovery_ran"):
        return 4
    return 5


def _connection(account: dict[str, Any] | None, username: bool, password: bool, last: dict[str, Any]) -> str:
    if account is None:
        return "not_configured"
    if not (username and password):
        return "missing_credentials"
    if last.get("ran"):
        return "connected" if last.get("ok") else "failed"
    return "unverified"


def status() -> dict[str, Any]:
    with storage.read_only() as conn:
        if not storage.schema_ready(conn):
            return {"ok": False, "code": "schema_pending", "migrated": False, "sent": False, "sending_enabled": False}
        business = storage.get_business(conn)
        mail = storage.get_mail_settings(conn, business["id"]) if business else None
        accounts_list = [
            {"id": row["id"], "address": row["address"], "display_name": row["display_name"],
             "credential_slot": row["credential_slot"], "status": row["status"]}
            for row in conn.execute(
                "SELECT id, address, display_name, credential_slot, status FROM accounts WHERE business_id=? ORDER BY address",
                ((business or {}).get("id") or "",),
            ).fetchall()
        ]
        imap = storage.get_imap_settings(conn, business["id"]) if business else {}
        review_count = conn.execute(
            "SELECT COUNT(*) FROM inbox_review WHERE business_id=?", ((business or {}).get("id") or "",)
        ).fetchone()[0]
    user_set, password_set = commands.secret_flags()
    step = _step(business, mail)
    profile = (business or {}).get("profile") or {}
    account, source = plugin_settings.effective_account(mail)
    last_check = profile.get("last_mail_check") or {"ran": False, "ok": False, "at": ""}
    defaults = plugin_settings.mail_defaults()
    return {
        "ok": True,
        "step": step,
        "complete": step == 5,
        "business_id": "" if business is None else business["id"],
        "business": {
            "name": "" if business is None else business.get("name") or "",
            "website": profile.get("website") or "",
            "products": profile.get("products") or ("" if business is None else business.get("offer") or ""),
            "target_market": profile.get("target_market") or "",
        },
        "mail": {
            "configured": account is not None,
            "source": source,
            "connection": _connection(account, user_set, password_set, last_check),
            "host": "" if account is None else account.get("host") or "",
            "port": 0 if account is None else account.get("port") or 0,
            "security": "" if account is None else account.get("security") or "",
            "from_address": "" if account is None else account.get("from_address") or "",
            "from_name": "" if account is None else account.get("from_name") or "",
            "signature_present": bool(account and account.get("signature_text")),
            "username_present": user_set,
            "password_present": password_set,
            "research_only": bool(profile.get("research_only")),
            "settings_defaults": defaults,
            "native_path": plugin_settings.native_settings_path(),
            "secret_env": list(plugin_settings.SECRET_NAMES),
            "last_check": last_check,
        },
        "accounts": accounts_list,
        "imap": {
            "configured": bool(imap.get("host") and imap.get("username")),
            "host": imap.get("host", ""),
            "port": int(imap.get("port") or 993),
            "username": imap.get("username", ""),
            "last_sync_at": imap.get("last_sync_at", ""),
            "review_count": review_count,
            "one_mailbox_per_secret_slot": True,
        },
        "followup_policy": {
            "days": int((business or {}).get("followup_days") or 3),
            "max_attempts": int((business or {}).get("followup_max_attempts") or 3),
            "cold_days": int((business or {}).get("followup_cold_days") or 21),
        },
        "gmail_oauth": {
            "available": False,
            "connected": False,
            "reason": "Gmail OAuth is not implemented. No token is stored.",
        },
        "suggestions": _suggestions(business),
        "icp": {
            **domain.normalize_icp(((business or {}).get("icp") or {})),
            "legacy_segments": list(((business or {}).get("icp") or {}).get("segments") or []),
        },
        "accepted_segments": list(((business or {}).get("icp") or {}).get("segments") or []),
        "last_discovery": profile.get("last_discovery") or {"ran": False, "prospects": 0, "error": ""},
        "sent": False,
        "sending_enabled": False,
        "send_via_rest": False,
        "password_accepted": False,
    }


def _save_profile(conn, business: dict[str, Any], extra: dict[str, Any]) -> None:
    profile = dict(business.get("profile") or {})
    profile.update(extra)
    icp = dict(business.get("icp") or {})
    storage.save_business(conn, {
        "name": business["name"],
        "offer": business.get("offer") or profile.get("products") or business["name"],
        "offer_short": (business.get("offer_short") or business.get("offer") or business["name"])[:80],
        "default_cta": business.get("default_cta") or "Reply if this matches a current project.",
        # Keep every ICP key the brand already had (segments/geos too) and only normalise the three
        # structured lists; rebuilding the dict from scratch dropped keys on every Settings save.
        "icp": {
            **icp,
            "industries": icp.get("industries") or icp.get("segments") or [],
            "locations": icp.get("locations") or icp.get("geos") or [],
            "buyer_roles": icp.get("buyer_roles") or icp.get("roles") or [],
            "exclude": icp.get("exclude") or [],
            "must_have": ["evidence", "source", "public_contact"],
        },
        # save_business writes every column, so carry the brand's own values instead of letting
        # them fall back to defaults (USD, 3 days, no country) on each save.
        "channels": business.get("channels") or ["email", "whatsapp"],
        "constraints": business.get("constraints") or [],
        "currency": business.get("currency") or "USD",
        "locale": business.get("locale") or "en",
        "default_country": business.get("default_country") or "",
        "followup_days": business.get("followup_days") or 3,
        "profile": profile,
        "citations": business.get("citations") or [],
    })


def _existing_business(conn, business_id: str, name: str) -> dict[str, Any] | None:
    """The saved brand this edit targets: by id when given, else an exact name match."""
    if business_id:
        found = storage.get_business(conn, business_id)
        if found is not None and domain.company_key(found["name"]) == domain.company_key(name):
            return found
    row = conn.execute(
        "SELECT id FROM businesses WHERE name_key=? ORDER BY updated_at DESC LIMIT 1",
        (domain.company_key(name),),
    ).fetchone()
    return None if row is None else storage.get_business(conn, row["id"])


def save(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body)
    if refused:
        return refused
    action = str(body.get("action") or "business")
    if action == "business":
        name = str(body.get("name") or "").strip()
        products = str(body.get("products") or "").strip()
        market = str(body.get("target_market") or "").strip()
        website = str(body.get("website") or "").strip()
        if not name or not products or not market:
            return {"ok": False, "code": "missing_fields", "error": "Name, products, and target market are required.", "sent": False}
        with storage.unit_of_work() as conn:
            existing = _existing_business(conn, str(body.get("business_id") or ""), name)
            if existing is not None:
                # Editing a saved brand must not re-run onboarding: that rebuilt the ICP from empty
                # lists and reset mail preferences to research-only. Update the profile in place.
                existing["offer"] = products[:500]
                existing["offer_short"] = products[:80]
                step = int((existing.get("profile") or {}).get("setup_step") or 2)
                _save_profile(conn, existing, {"website": website[:300], "products": products[:500],
                                               "target_market": market[:240], "setup_step": max(step, 2)})
        if existing is not None:
            return status()
        raw = tools.onboard_business({
            "name": name,
            "offer": products,
            "offer_short": products[:80],
            "default_cta": "Reply if this matches a current project.",
            "target_market": market,
            "research_only": True,
        })
        parsed = json.loads(raw)
        if not parsed.get("ok"):
            return _clean(parsed)
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, parsed["business"]["id"])
            _save_profile(conn, business, {"website": website[:300], "products": products[:500], "target_market": market[:240], "setup_step": 2})
        return status()
    if action == "skip_mail":
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, str(body.get("business_id") or ""))
            if business is None:
                return {"ok": False, "code": "missing_business", "error": "Save the business first.", "sent": False}
            _save_profile(conn, business, {"mail_choice": "research_only", "research_only": True, "setup_step": 3})
        return status()
    if action == "mail":
        if body.get("confirm_transport") is not True:
            return {"ok": False, "code": "transport_confirmation_required",
                    "error": "Review the SMTP host, port, security and sender, then explicitly confirm Save sender.", "sent": False}
        try:
            from . import mail as mail_module
        except ImportError:
            import mail as mail_module
        try:
            account = mail_module.validate_account({
                "host": body.get("host") or "",
                "port": body.get("port") or "",
                "security": body.get("security") or "starttls",
                "from_address": body.get("from_address") or "",
                "from_name": body.get("from_name") or "",
                "signature_text": body.get("signature") or "",
                "company": body.get("company") or "",
            })
        except (ValueError, TypeError) as exc:
            return {"ok": False, "code": "bad_mail_settings", "error": str(exc), "sent": False}
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, str(body.get("business_id") or ""))
            if business is None:
                return {"ok": False, "code": "missing_business", "sent": False}
            plugin_settings.save_wizard_account(conn, business["id"], account)
            _save_profile(conn, business, {"mail_choice": "smtp", "research_only": False, "setup_step": 3})
        return status()
    if action == "check":
        result = json.loads(commands.configure_mail({"action": "check", "business_id": str(body.get("business_id") or "")}))
        business_id = str(body.get("business_id") or "")
        record = {"ran": True, "ok": bool(result.get("ok")), "at": _now(), "code": result.get("code") or "", "source": result.get("source") or ""}
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, business_id)
            if business is not None:
                _save_profile(conn, business, {"last_mail_check": record})
        state = status()
        state["check"] = _clean(result)
        return {**state, "sent": False, "sending_enabled": False, "password_returned": False}
    if action == "icp":
        def _items(key: str) -> list[str]:
            raw = body.get(key) or []
            if isinstance(raw, str):
                raw = raw.split(",")
            return [str(item).strip()[:80] for item in raw if str(item).strip()][:20]

        industries, locations, roles = _items("industries"), _items("locations"), _items("buyer_roles")
        if not (industries or locations or roles):
            return {"ok": False, "code": "missing_icp",
                    "error": "Fill at least industries, locations or buyer roles.", "sent": False}
        candidate = {"industries": industries, "locations": locations, "buyer_roles": roles}
        normalized = domain.normalize_icp(candidate)
        if normalized["status"] != "configured":
            return {"ok": False, "code": "icp_ambiguous", "issues": normalized["issues"],
                    "error": "Keep industries, locations and buyer roles in separate fields.", "sent": False}
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, str(body.get("business_id") or ""))
            if business is None:
                return {"ok": False, "code": "missing_business", "error": "Save the business first.",
                        "sent": False}
            merged = {**(business.get("icp") or {}), **candidate,
                      "segments": industries, "geos": locations}
            business["icp"] = merged
            _save_profile(conn, business, {"icp_configured_at": _now()})
        return status()
    if action == "segments":
        chosen = [str(item).strip()[:160] for item in body.get("segments") or [] if str(item).strip()]
        if not chosen:
            return {"ok": False, "code": "missing_segments", "error": "Review at least one segment before discovery.", "sent": False}
        with storage.unit_of_work() as conn:
            business = storage.get_business(conn, str(body.get("business_id") or ""))
            if business is None:
                return {"ok": False, "code": "missing_business", "error": "Save the business first.", "sent": False}
            business["icp"] = {**(business.get("icp") or {}), "segments": chosen}
            _save_profile(conn, business, {"setup_step": 4, "segments_reviewed": True})
        return status()
    return {"ok": False, "code": "bad_action", "error": "Unknown setup action.", "sent": False}


def discover(body: dict[str, Any]) -> dict[str, Any]:
    refused = _refuse(body or {})
    if refused:
        return refused
    current = status()
    if not current.get("ok"):
        return current
    if not current.get("business_id"):
        return {"ok": False, "code": "missing_business", "error": "Save the business before discovery.", "sent": False, "prospects": []}
    market = current["business"]["target_market"] or current["business"]["products"]
    raw = tools._discover({
        "authorized": True,
        "use_hermes_search": True,
        "query": market,
        "business_id": current["business_id"],
    })
    parsed = json.loads(raw)
    prospects = parsed.get("prospects") or []
    summary = {
        "ran": True,
        "ok": bool(parsed.get("ok")),
        "code": parsed.get("code") or "",
        "error": parsed.get("error") or "",
        "prospects": len(prospects),
        "url": parsed.get("url") or "",
        "fabricated": False,
    }
    with storage.unit_of_work() as conn:
        business = storage.get_business(conn, current["business_id"])
        if business is not None:
            _save_profile(conn, business, {"discovery_ran": True, "last_discovery": summary, "setup_step": 5 if summary["ok"] else 4})
    state = status()
    state["discovery"] = _clean(parsed)
    state["fabricated"] = False
    return state
