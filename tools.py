"""Tool handlers. Always return a JSON string. No network, no sends, no secret reads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from . import csv_import, discovery, domain, extract, fetch, followstate, inbox, pipeline, storage
    from .adapters import adapter_for
    from .adapters.smtp import smtp_readiness
except ImportError:  # unittest loads this file as a top-level module
    import csv_import
    import discovery
    import domain
    import extract
    import fetch
    import followstate
    import inbox
    import pipeline
    import storage
    from adapters import adapter_for
    from adapters.smtp import smtp_readiness

_BUNDLE = Path(__file__).resolve().parent / "data" / "demo_bundle.json"
_CTX = None


def bind(ctx) -> None:
    global _CTX
    _CTX = ctx


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fail(code: str, error: str, **extra: Any) -> str:
    return _dump({"ok": False, "code": code, "error": error, "sent": False, **extra})


def _as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
        raise ValueError("expected a list")
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    raise ValueError("expected a list")


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _ref(args: dict[str, Any]) -> str:
    """Brand reference: an explicit brand wins over the active/default brand."""
    return str(args.get("brand") or args.get("business_id") or "").strip()


def _require_business(conn, business_id: str = "") -> dict[str, Any] | None:
    """Resolve a brand id, slug, or name to its business row. Unknown names resolve to None."""
    brand, _reason = storage.resolve_brand(conn, business_id)
    if brand is None:
        return None
    return storage.get_business(conn, brand["business_id"])


def _profile_from_args(args: dict[str, Any]) -> dict[str, Any]:
    days = args.get("followup_days")
    if days in (None, ""):
        days = 3
        if _CTX is not None:
            try:
                days = int(_CTX.get_config("followup_days", 3))
            except (TypeError, ValueError):
                days = 3
    constraints = _strings(args.get("constraints"))
    if "approval_required" not in constraints:
        constraints.append("approval_required")
    if "no_send_phase_1" not in constraints:
        constraints.append("no_send_phase_1")
    return {
        "name": str(args.get("name") or "").strip(),
        "offer": str(args.get("offer") or "").strip(),
        "offer_short": str(args.get("offer_short") or "").strip(),
        "default_cta": str(args.get("default_cta") or "").strip(),
        "icp": {
            "segments": _strings(args.get("segments")),
            "geos": _strings(args.get("geos")),
            "exclude": _strings(args.get("exclude")),
            "must_have": ["evidence", "source", "public_contact"],
        },
        "channels": _strings(args.get("channels")) or ["email", "whatsapp"],
        "constraints": constraints,
        "currency": str(args.get("currency") or "USD").strip() or "USD",
        "locale": str(args.get("locale") or "en").strip() or "en",
        "default_country": str(args.get("default_country") or "").strip(),
        "followup_days": int(days),
        "sender_name": str(args.get("sender_name") or "").strip(),
        "sender_role": str(args.get("sender_role") or "").strip(),
        "signature": str(args.get("signature") or "").strip(),
        "profile": pipeline.preferences(args),
    }


def onboard_business(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    if args.get("url"):
        return _onboard_from_url(args)
    if args.get("sources"):
        return _onboard_from_sources(args)
    profile = _profile_from_args(args)
    if not profile["name"] or not profile["offer"] or not profile["offer_short"] or not profile["default_cta"]:
        return _fail("missing_fields", "name, offer, offer_short, and default_cta are required.")
    with storage.unit_of_work() as conn:
        saved = storage.save_business(conn, profile)
    return _dump({"ok": True, "business": saved, "sending_enabled": False, "extracted": False})


def _onboard_from_url(args: dict) -> str:
    if args.get("authorized") is not True:
        return _fail("not_authorized", "Fetching a business URL requires authorized=true.")
    url = str(args.get("url") or "").strip()
    fetched = fetch.fetch_public_url(url)
    if not fetched.get("ok"):
        return _dump({**fetched, "sent": False, "sending_enabled": False})
    args = {
        **args,
        "sources": [{"url": fetched["url"], "text": fetched["text"], "permitted": True}],
    }
    result = json.loads(_onboard_from_sources(args))
    result["fetched"] = True
    result["fetch_url"] = fetched["url"]
    return _dump(result)


def _onboard_from_sources(args: dict) -> str:
    if args.get("authorized") is not True:
        return _fail("not_authorized", "Website onboarding requires authorized=true from the operator.")
    note = str(args.get("authorization_note") or "").strip()
    if not note:
        return _fail("missing_authorization_note", "Say who authorized this website text.")
    cta = str(args.get("default_cta") or "").strip()
    if not cta:
        return _fail("missing_cta", "default_cta is an operator instruction, not a website claim.")
    try:
        sources = _as_list(args.get("sources"))
    except (ValueError, json.JSONDecodeError) as exc:
        return _fail("bad_sources", str(exc))
    extracted = extract.extract_business(sources)
    if not extracted.get("ok"):
        return _dump({**extracted, "sent": False, "sending_enabled": False})
    profile = _profile_from_args({
        **args,
        "name": extracted["name"],
        "offer": extracted["offer"],
        "offer_short": extracted["offer_short"],
        "default_cta": cta,
        "segments": extracted["segments"],
        "geos": extracted["geos"],
        "exclude": extracted["exclude"],
    })
    profile["profile"] = {
        "products": extracted["products"],
        "services": extracted["services"],
        "positioning": extracted["positioning"],
        "authorization_note": note,
        "fetched": False,
        "sender_name": profile.get("sender_name") or "",
        "sender_role": profile.get("sender_role") or "",
        "signature": profile.get("signature") or "",
    }
    profile["citations"] = extracted["citations"]
    with storage.unit_of_work() as conn:
        saved = storage.save_business(conn, profile)
        storage.save_sources(conn, saved["id"], sources, "website")
    return _dump({
        "ok": True,
        "business": saved,
        "extracted": True,
        "fetched": False,
        "ignored_instructions": extracted["ignored_instructions"],
        "sending_enabled": False,
    })


def _prepare_customer(raw: dict[str, Any], source: str, country: str) -> dict[str, Any]:
    company = str(raw.get("company") or "").strip()
    if not company:
        raise ValueError("customer company is required")
    email = domain.normalize_email(raw.get("email"))
    phone = domain.normalize_phone(raw.get("phone"), country)
    return {
        "company": company,
        "company_key": domain.company_key(company),
        "contact_name": str(raw.get("contact_name") or "").strip(),
        "email": email["value"],
        "email_key": email["value"],
        "email_valid": email["valid"],
        "phone": phone["digits"],
        "phone_key": phone["digits"],
        "phone_valid": phone["valid"],
        "segment": str(raw.get("segment") or "").strip(),
        "source": str(raw.get("source") or source or "unspecified"),
        "notes": str(raw.get("notes") or "").strip(),
        "synthetic": bool(raw.get("synthetic")),
        "phone_reason": phone["reason"],
        "row_number": raw.get("row_number") or 0,
        "batch_id": raw.get("batch_id") or "",
        "provenance": raw.get("provenance") or {},
    }


def _import_records(conn, business: dict[str, Any], records: list[dict[str, Any]], source: str, *, require_synthetic: bool) -> dict[str, Any]:
    inserted = []
    skipped = []
    warnings = []
    for raw in records:
        if not isinstance(raw, dict):
            warnings.append({"error": "record_not_object"})
            continue
        if require_synthetic and raw.get("synthetic") is not True:
            return {
                "ok": False,
                "code": "not_authorized",
                "error": "Import requires authorized=true, or synthetic=true for a fixture.",
                "sent": False,
            }
        try:
            prepared = _prepare_customer(raw, source, business.get("default_country") or "")
        except ValueError as exc:
            warnings.append({"error": str(exc), "company": raw.get("company")})
            continue
        if prepared["phone"] and not prepared["phone_valid"]:
            warnings.append({"company": prepared["company"], "phone_reason": prepared["phone_reason"]})
        if prepared["email"] and not prepared["email_valid"]:
            warnings.append({"company": prepared["company"], "email_reason": "invalid_format"})
        duplicate = storage.find_customer_duplicate(conn, business["id"], prepared)
        if duplicate:
            skipped.append({"id": duplicate, "company": prepared["company"]})
            continue
        inserted.append(storage.insert_customer(conn, business["id"], prepared))
    return {
        "ok": True,
        "inserted": inserted,
        "skipped": skipped,
        "warnings": warnings,
        "inserted_count": len(inserted),
        "skipped_count": len(skipped),
        "sent": False,
    }


def import_customers(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    with storage.unit_of_work() as conn:
        if args.get("seed_demo") is True:
            return _seed_demo(conn, _ref(args))
        if args.get("csv_text"):
            return _import_csv(conn, args)
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business or pass seed_demo=true.")
        source = str(args.get("source") or "").strip()
        if not source:
            return _fail("missing_source", "Manual import requires a source label.")
        try:
            records = _as_list(args.get("records"))
        except (ValueError, json.JSONDecodeError) as exc:
            return _fail("bad_records", str(exc))
        if not records:
            return _fail("empty_import", "Pass records or seed_demo=true.")
        result = _import_records(conn, business, records, source, require_synthetic=True)
        result["business_id"] = business["id"]
        return _dump(result)


def _import_csv(conn, args: dict) -> str:
    if args.get("authorized") is not True:
        return _fail("not_authorized", "CSV import requires authorized=true. Refusing to read an unapproved file.")
    note = str(args.get("authorization_note") or "").strip()
    if not note:
        return _fail("missing_authorization_note", "authorization_note is required.")
    business = _require_business(conn, _ref(args))
    if business is None:
        return _fail("missing_business", "Onboard a business before importing customers.")
    mapping = args.get("mapping") or {}
    if isinstance(mapping, str):
        try:
            mapping = json.loads(mapping)
        except json.JSONDecodeError as exc:
            return _fail("bad_mapping", str(exc))
    parsed = csv_import.parse_csv(str(args.get("csv_text") or ""), mapping)
    if not parsed.get("ok"):
        return _dump({**parsed, "sent": False})
    source = str(args.get("source") or "csv").strip() or "csv"
    batch_id = storage.save_batch(conn, business["id"], source, note, mapping)
    synthetic = bool(args.get("synthetic"))
    records = []
    for row in parsed["rows"]:
        records.append({
            **row,
            "synthetic": synthetic,
            "source": source,
            "batch_id": batch_id,
            "provenance": {
                "source": source,
                "row_number": row["row_number"],
                "batch_id": batch_id,
                "authorization_note": note,
                "synthetic": synthetic,
            },
        })
    result = _import_records(conn, business, records, source, require_synthetic=False)
    result["business_id"] = business["id"]
    result["batch_id"] = batch_id
    result["row_errors"] = parsed["errors"]
    result["authorized"] = True
    return _dump(result)


def _seed_demo(conn, business_id: str) -> str:
    bundle = json.loads(_BUNDLE.read_text(encoding="utf-8"))
    profile = bundle["business"]
    if business_id:
        existing = storage.get_business(conn, business_id)
        if existing is None:
            return _fail("missing_business", "business_id was not found.")
    saved = storage.save_business(conn, profile)
    customer_records = []
    for item in bundle["customers"]:
        customer_records.append({**item, "synthetic": True})
    imported = _import_records(conn, saved, customer_records, "bundled-synthetic-demo", require_synthetic=True)
    qualified = []
    for prospect in bundle["prospects"]:
        result = domain.qualify(saved, prospect)
        lead = storage.save_lead(conn, saved["id"], prospect, result)
        qualified.append({"id": lead["id"], "company": lead["company"], "decision": lead["decision"], "score": lead["score"]})
    return _dump({
        "ok": True,
        "seeded": True,
        "synthetic": True,
        "business_id": saved["id"],
        "customers": imported,
        "prospects": qualified,
        "sending_enabled": False,
    })


def qualify_lead(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    lead_id = str(args.get("lead_id") or "").strip()
    company = str(args.get("company") or "").strip()
    evidence = str(args.get("evidence") or "").strip()
    if lead_id and not company:
        return _qualify_stored(args, lead_id)
    if not company or not evidence:
        return _fail("missing_fields", "company and evidence are required, or pass a researched lead_id.")
    source_text = str(args.get("source_text") or "")
    if source_text and not extract.quote_in_text(evidence, source_text):
        return _fail("evidence_not_in_source", "Evidence is not a quote from the supplied source text.")
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        try:
            unknowns = _strings(args.get("unknowns"))
        except (ValueError, json.JSONDecodeError) as exc:
            return _fail("bad_unknowns", str(exc))
        lead_in = {
            "company": company,
            "contact_name": args.get("contact_name"),
            "role": args.get("role"),
            "email": args.get("email"),
            "phone": args.get("phone"),
            "segment": args.get("segment"),
            "country": args.get("country"),
            "source_url": args.get("source_url"),
            "evidence": evidence,
            "unknowns": unknowns,
            "citations": [{"url": args.get("source_url"), "quote": evidence}] if args.get("source_url") else [],
        }
        result = domain.qualify(business, lead_in)
        result["citations"] = lead_in["citations"]
        saved = storage.save_lead(conn, business["id"], lead_in, result)
    return _dump({"ok": True, "lead": saved, "qualification": result, "sent": False, "sending_enabled": False})


def _qualify_stored(args: dict, lead_id: str) -> str:
    with storage.unit_of_work() as conn:
        lead = storage.get_lead(conn, lead_id)
        if lead is None:
            return _fail("lead_not_found", "lead_id was not found.")
        requested = _ref(args)
        if requested:
            scoped, _reason = storage.resolve_brand(conn, requested)
            if scoped is None or scoped["business_id"] != lead["business_id"]:
                return _fail("scope_mismatch", "lead_id belongs to a different business.")
        business = storage.get_business(conn, lead["business_id"])
        if business is None:
            return _fail("missing_business", "Lead has no business profile.")
        extra = str(args.get("evidence") or "").strip()
        blob = storage.list_source_text(conn, business["id"]) + "\n" + str(lead.get("evidence") or "")
        if extra and not extract.quote_in_text(extra, blob):
            return _fail("evidence_not_in_source", "That evidence is not in the stored source text.")
        lead_in = {
            "company": lead["company"],
            "contact_name": lead.get("contact_name"),
            "role": lead.get("role"),
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "segment": lead.get("segment"),
            "country": lead.get("country"),
            "source_url": lead.get("source_url"),
            "evidence": extra or lead.get("evidence") or "",
            "unknowns": lead.get("unknowns") or [],
            "citations": lead.get("citations") or [],
        }
        if not lead_in["evidence"]:
            return _fail("missing_evidence", "Stored lead has no cited evidence to qualify.")
        result = domain.qualify(business, lead_in)
        result["citations"] = lead_in["citations"]
        result["confidence"] = lead.get("confidence_detail") or {}
        saved = storage.save_lead(conn, business["id"], lead_in, result)
    return _dump({"ok": True, "lead": saved, "qualification": result, "sent": False, "sending_enabled": False})


def _search_urls(payload: Any) -> list[str]:
    found = []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    web = []
    if isinstance(payload, dict):
        web = ((payload.get("data") or {}).get("web") or payload.get("results") or [])
    if not isinstance(web, list):
        return []
    for item in web:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if url.startswith(("https://", "http://")) and url not in found:
            found.append(url)
    return found[:3]


def _hermes_search(query: str) -> dict[str, Any]:
    dispatch = getattr(_CTX, "dispatch_tool", None) if _CTX is not None else None
    if dispatch is None:
        return {"ok": False, "code": "search_unavailable", "results": [], "urls": [], "fabricated": False}
    try:
        raw = dispatch("web_search", {"query": query, "limit": 5})
    except Exception:
        return {"ok": False, "code": "search_failed", "results": [], "urls": [], "fabricated": False}
    urls = _search_urls(raw)
    return {"ok": True, "code": "search_returned", "urls": urls, "results": urls, "fabricated": False}


def _discover(args: dict) -> str:
    if args.get("authorized") is not True:
        return _fail("not_authorized", "Prospect discovery requires authorized=true.")
    search = {"ok": False, "code": "not_requested", "results": [], "fabricated": False}
    if args.get("use_hermes_search") is True:
        search = _hermes_search(str(args.get("query") or ""))
        if not search.get("ok"):
            search["prospects"] = []
    url = str(args.get("discovery_url") or "").strip()
    if not url:
        urls = search.get("urls") or []
        url = urls[0] if urls else ""
    if not url:
        return _dump({
            "ok": search.get("ok", False),
            "code": search.get("code") or "missing_discovery_url",
            "error": "No permitted discovery URL, and Hermes search did not return usable pages.",
            "search": {k: v for k, v in search.items() if k != "text"},
            "prospects": [],
            "fabricated": False,
            "fetched": False,
            "sent": False,
        })
    fetched = fetch.fetch_public_url(url)
    if not fetched.get("ok"):
        fetched["prospects"] = []
        fetched["fabricated"] = False
        fetched["search"] = {k: v for k, v in search.items() if k != "text"}
        return _dump({**fetched, "sent": False})
    found = discovery.discover_companies(fetched["text"], fetched["url"])
    saved = []
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business before discovery.")
        storage.save_sources(conn, business["id"], [{"url": fetched["url"], "text": fetched["text"], "permitted": True}], "discovery")
        for prospect in found["prospects"]:
            lead_in = {**prospect, "unknowns": [prospect["unknown"]] if prospect.get("unknown") else []}
            result = domain.qualify(business, lead_in)
            result["citations"] = prospect["citations"]
            result["confidence"] = {"score": result["score"], "label": "cited", "breakdown": [{"signal": "directory_quote", "points": result["score"]}]}
            saved_lead = storage.save_lead(conn, business["id"], lead_in, result)
            status = "qualified" if result["decision"] == "qualified" else "new"
            storage.set_pipeline_fields(conn, saved_lead["id"], pipeline_status=status, email_key=(lead_in.get("email") or "").lower())
            if not saved_lead.get("updated"):
                storage.add_event(conn, "discovered", business["id"], saved_lead["id"], {"source_url": lead_in.get("source_url") or fetched["url"], "offer_match": result["decision"]})
            saved.append(saved_lead)
    return _dump({
        "ok": True,
        "fetched": True,
        "fabricated": False,
        "url": fetched["url"],
        "prospects": [{"id": item["id"], "company": item["company"], "decision": item["decision"], "score": item["score"], "evidence": item["evidence"]} for item in saved],
        "ignored_instructions": found["ignored_instructions"],
        "search": {k: v for k, v in search.items() if k != "text"},
        "sent": False,
        "sending_enabled": False,
    })


def research_opportunity(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    if args.get("discovery_url") or args.get("use_hermes_search"):
        return _discover(args)
    if args.get("sources"):
        return _research_from_sources(args)
    title = str(args.get("title") or "").strip()
    if not title:
        return _fail("missing_title", "title is required.")
    try:
        verified = _as_list(args.get("verified"))
        assumptions = _strings(args.get("assumptions"))
        unknowns = _strings(args.get("unknowns"))
    except (ValueError, json.JSONDecodeError) as exc:
        return _fail("bad_research", str(exc))
    clean_verified = []
    for item in verified:
        if not isinstance(item, dict):
            return _fail("bad_research", "Each verified item needs claim and source.")
        claim = str(item.get("claim") or "").strip()
        source = str(item.get("source") or "").strip()
        if not claim or not source:
            return _fail("bad_research", "Verified claims require both claim and source.")
        clean_verified.append({"claim": claim, "source": source})
    if not clean_verified and not unknowns:
        return _fail("empty_research", "Pass at least one sourced claim or an explicit unknown.")
    fit = str(args.get("fit") or "unknown").strip().lower()
    if fit not in {"fit", "weak", "unknown"}:
        return _fail("bad_fit", "fit must be fit, weak, or unknown.")
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        lead_id = str(args.get("lead_id") or "")
        if lead_id and storage.get_lead(conn, lead_id) is None:
            return _fail("lead_not_found", "lead_id was not found.")
        saved = storage.save_opportunity(conn, business["id"], {
            "lead_id": lead_id,
            "title": title,
            "verified": clean_verified,
            "assumptions": assumptions,
            "unknowns": unknowns,
            "fit": fit,
            "next_question": str(args.get("next_question") or "").strip(),
            "grounded": False,
            "citations": [],
        })
    return _dump({"ok": True, "opportunity": saved, "fetched": False, "grounded": False, "sent": False})


def _research_from_sources(args: dict) -> str:
    try:
        sources = _as_list(args.get("sources"))
    except (ValueError, json.JSONDecodeError) as exc:
        return _fail("bad_sources", str(exc))
    extracted = extract.extract_prospect(str(args.get("company") or ""), sources)
    if not extracted.get("ok"):
        return _dump({**extracted, "sent": False, "fetched": False})
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        storage.save_sources(conn, business["id"], sources, "prospect")
        lead_in = {
            "company": extracted["company"],
            "contact_name": extracted["contact_name"],
            "role": extracted["role"],
            "email": extracted["email"],
            "phone": extracted["phone"],
            "segment": extracted["segment"],
            "country": extracted["country"],
            "source_url": extracted["source_url"],
            "evidence": extracted["evidence"] or "No fact line in the permitted source.",
            "unknowns": extracted["unknowns"],
            "citations": extracted["citations"],
        }
        result = domain.qualify(business, lead_in)
        result["citations"] = extracted["citations"]
        result["confidence"] = extracted["confidence"]
        if not extracted["evidence"]:
            result["decision"] = "hold"
            result["reasons"] = list(result["reasons"]) + ["no_fact_in_source"]
        saved_lead = storage.save_lead(conn, business["id"], lead_in, result)
        saved = storage.save_opportunity(conn, business["id"], {
            "lead_id": saved_lead["id"],
            "title": str(args.get("title") or extracted["company"]),
            "verified": [{"claim": item["quote"], "source": item["url"]} for item in extracted["citations"]],
            "assumptions": [],
            "unknowns": extracted["unknowns"],
            "fit": "fit" if result["decision"] == "qualified" else "weak" if result["decision"] == "hold" else "unknown",
            "next_question": extracted["unknowns"][0] if extracted["unknowns"] else "",
            "grounded": True,
            "citations": extracted["citations"],
            "confidence": extracted["confidence"],
        })
    return _dump({
        "ok": True,
        "fetched": False,
        "grounded": True,
        "lead": saved_lead,
        "opportunity": saved,
        "confidence": extracted["confidence"],
        "unknowns": extracted["unknowns"],
        "ignored_instructions": extracted["ignored_instructions"],
        "sent": False,
        "sending_enabled": False,
    })


def draft_outreach(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    lead_id = str(args.get("lead_id") or "").strip()
    channel = str(args.get("channel") or "").strip().lower()
    if not lead_id or not channel:
        return _fail("missing_fields", "lead_id and channel are required.")
    with storage.unit_of_work() as conn:
        lead = storage.get_lead(conn, lead_id)
        if lead is None:
            return _fail("lead_not_found", "lead_id was not found.")
        business = storage.get_business(conn, lead["business_id"])
        if business is None:
            return _fail("missing_business", "Lead has no business profile.")
        blocked_status = lead.get("pipeline_status") in {"do_not_contact", "not_interested"}
        if lead.get("deleted_at") or lead.get("archived") or blocked_status or storage.is_suppressed(conn, business["id"], lead.get("email") or ""):
            return _fail("outreach_blocked", "This prospect is archived, deleted, or suppressed. No draft was created.", sent=False)
        rendered = domain.render_draft(business, lead, channel, args.get("cta"))
        if not rendered.get("ok"):
            return _dump({**rendered, "sent": False})
        rendered["lead_id"] = lead_id
        saved, reused = storage.save_draft(conn, business["id"], rendered)
        storage.set_pipeline_fields(conn, lead_id, pipeline_status="drafted")
        storage.add_event(conn, "draft_ready", business["id"], lead_id, {"draft_id": saved["id"]})
        blocked = adapter_for(channel).send(saved)
    payload = {
        "ok": True,
        "draft": saved,
        "reused": reused,
        "delivery": blocked,
        "sent": False,
        "sending_enabled": False,
    }
    if args.get("check_smtp") is True:
        payload["smtp"] = smtp_readiness()
    return _dump(payload)


def plan_followups(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        leads = storage.list_leads(conn, business["id"])
        drafts = storage.list_drafts(conn, business["id"])
        approvals = storage.list_approvals(conn, business["id"])
        now = domain.utcnow()
        planned = [
            domain.plan_one(
                lead,
                drafts,
                approvals,
                now=now,
                cadence_days=int(business.get("followup_days") or 3),
            )
            for lead in leads
        ]
        if any(item.get("send") for item in planned):
            return _fail("send_recommended", "Planner refused to persist a send recommendation.")
        today = domain.day(now)
        for customer in storage.list_customers(conn, business["id"]):
            if customer.get("email_valid") or customer.get("phone_valid"):
                continue
            planned.append({
                "lead_id": "",
                "action": "fix_contact",
                "reason": f"Imported customer {customer['company']} has no format-valid contact.",
                "due_on": today,
                "scheduled_for": domain.iso(now),
                "send": False,
            })
        saved = storage.replace_followups(conn, business["id"], planned)
    return _dump({"ok": True, "followups": saved, "count": len(saved), "sending_enabled": False})


def report(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    section = str(args.get("section") or "summary").strip().lower()
    with storage.unit_of_work() as conn:
        business = _require_business(conn, _ref(args))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        snap = storage.snapshot(conn, business["id"])
    summary = domain.summarize(snap)
    leads = snap["leads"]
    followups = snap["followups"]
    next_actions = []
    by_lead = {item.get("lead_id"): item for item in followups}
    for lead in leads:
        step = by_lead.get(lead["id"]) or {}
        next_actions.append({
            "lead_id": lead["id"],
            "company": lead["company"],
            "status": lead["decision"],
            "evidence": lead.get("evidence") or "",
            "citations": lead.get("citations") or [],
            "action": step.get("action") or "plan_followups",
            "due_on": step.get("due_on") or "",
            "scheduled_for": step.get("scheduled_for") or "",
            "reason": step.get("reason") or "",
            "send": False,
        })
    body: dict[str, Any] = {
        "ok": True,
        "business_id": business["id"],
        "business_name": business["name"],
        "summary": summary,
        "next_actions": next_actions,
        "sending_enabled": False,
    }
    if section in {"summary", "pipeline"}:
        body["leads"] = [
            {
                "id": lead["id"],
                "company": lead["company"],
                "decision": lead["decision"],
                "score": lead["score"],
                "stage": lead["stage"],
                "evidence": lead.get("evidence") or "",
                "source_url": lead.get("source_url") or "",
                "citations": lead.get("citations") or [],
                "confidence": lead.get("confidence") or 0,
                "unknowns": lead.get("unknowns") or [],
            }
            for lead in leads
        ]
        body["followups"] = followups
        body["recommendations"] = [item for item in followups if item.get("status") == "recommended"]
    if section in {"summary", "drafts"}:
        body["drafts"] = [
            {"id": item["id"], "lead_id": item["lead_id"], "channel": item["channel"], "status": item["status"], "sent": False}
            for item in snap["drafts"]
        ]
    if section in {"summary", "approvals"}:
        body["approvals"] = [
            {"id": item["id"], "draft_id": item["draft_id"], "lead_id": item.get("lead_id") or "", "status": item["status"], "actor": item.get("actor") or "", "sent": False}
            for item in snap["approvals"]
        ]
    if section not in {"summary", "pipeline", "drafts", "approvals"}:
        return _fail("bad_section", "section must be summary, pipeline, drafts, or approvals.")
    body["sending_enabled"] = False
    return _dump(body)


def _host_decision(action: str, draft: dict) -> tuple[str | None, str]:
    """Ask Hermes. An LLM boolean is not authorization. Unattended surfaces fail closed."""
    ctx = _CTX
    ask = getattr(ctx, "ask_choice", None) if ctx is not None else None
    surface_fn = getattr(ctx, "session_surface", None) if ctx is not None else None
    if ask is None or surface_fn is None:
        return None, "host_approval_unavailable"
    try:
        surface = str(surface_fn() or "")
    except Exception:
        return None, "surface_unknown"
    if surface not in {"cli", "tui", "desktop"}:
        return None, "unattended_surface"
    try:
        choice = ask(
            f"Record {action} for draft {draft.get('id')}? This does not send a message.",
            [action, "cancel"],
        )
    except Exception:
        return None, "host_approval_failed"
    if choice != action:
        return None, "host_declined"
    return str(choice), ""


def request_approval(args: dict, **kwargs) -> str:
    args = args or {}
    draft_id = str(args.get("draft_id") or "").strip()
    decision = str(args.get("decision") or "").strip().lower()
    if decision == "request":
        decision = "pending"
    if not draft_id or decision not in {"pending", "approve", "reject"}:
        return _fail("bad_decision", "draft_id and decision (request, approve, reject) are required.")
    status = {"pending": "pending", "approve": "approved", "reject": "rejected"}[decision]
    with storage.unit_of_work() as conn:
        draft = storage.get_draft(conn, draft_id)
        if draft is None:
            return _fail("draft_not_found", "draft_id was not found.")
        requested_business = _ref(args)
        if requested_business:
            scoped, _reason = storage.resolve_brand(conn, requested_business)
            if scoped is None or scoped["business_id"] != draft["business_id"]:
                return _fail("scope_mismatch", "draft_id belongs to a different business.")
        requested_lead = str(args.get("lead_id") or "")
        if requested_lead and requested_lead != draft["lead_id"]:
            return _fail("scope_mismatch", "draft_id belongs to a different lead.")
        revision = domain.draft_revision(draft)
        existing = storage.get_approval_for_draft(conn, draft_id)
        if decision == "approve" and existing and existing.get("status") == "approved":
            stored = json.loads(existing.get("scope_json") or "{}")
            if stored.get("revision") != revision or stored.get("action") != "approve":
                return _fail("stale_approval", "Stored approval does not match this draft revision.", sent=False)
            existing["reused"] = True
            existing["sent"] = False
            return _dump({"ok": True, "approval": existing, "delivery": adapter_for(draft["channel"]).send(draft), "sent": False, "sending_enabled": False})
        if decision in {"approve", "reject"}:
            choice, reason = _host_decision(decision, draft)
            if choice != decision:
                return _fail(reason or "host_approval_required", "Host approval was not granted. Model-supplied flags are ignored.", sent=False, sending_enabled=False)
        scope = {
            "business_id": draft["business_id"],
            "draft_id": draft_id,
            "lead_id": draft["lead_id"],
            "action": decision,
            "revision": revision,
            "actor": "host" if decision in {"approve", "reject"} else (str(args.get("actor") or "operator").strip() or "operator"),
        }
        saved = storage.save_approval(
            conn,
            draft["business_id"],
            draft_id,
            status,
            scope["actor"],
            str(args.get("note") or "").strip(),
            lead_id=draft["lead_id"],
            scope=scope,
        )
        blocked = adapter_for(draft["channel"]).send(draft)
    return _dump({
        "ok": True,
        "approval": saved,
        "delivery": blocked,
        "sent": False,
        "sending_enabled": False,
    })


def pipeline_action(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    if pipeline.SECRET_KEYS.intersection(args):
        return _fail("secret_in_args", "Pipeline actions do not accept credentials.")
    action = str(args.get("action") or "list").strip().lower()
    business_id = _ref(args)
    with storage.unit_of_work() as conn:
        business = _require_business(conn, business_id)
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        business_id = business["id"]
        if action == "list":
            rows, total = pipeline.list_prospects(
                conn,
                business_id,
                str(args.get("query") or ""),
                str(args.get("status") or ""),
                str(args.get("sort") or "updated"),
                bool(args.get("include_archived")),
                int(args.get("limit") or 50),
                int(args.get("offset") or 0),
            )
            return _dump({"ok": True, "prospects": rows, "count": len(rows), "total": total, "sent": False})
        if action == "discover":
            try:
                sources = _as_list(args.get("sources"))
            except (ValueError, json.JSONDecodeError) as exc:
                return _fail("bad_sources", str(exc))
            return _dump(pipeline.discover(conn, business, sources))
        if action == "followups":
            return _dump(followstate.board(conn, business_id, int(args.get("limit") or 200)))
        if action == "inbox":
            return _dump(inbox.run(conn, business_id, args))
        lead_id = str(args.get("lead_id") or "")
        if action == "status":
            return _dump(pipeline.set_status(conn, business_id, lead_id, str(args.get("status") or ""), "operator"))
        if action == "note":
            return _dump(pipeline.add_note(conn, business_id, lead_id, str(args.get("note") or "")))
        if action == "archive":
            return _dump(pipeline.archive(conn, business_id, lead_id))
        if action == "delete":
            if args.get("confirm_delete") is not True:
                return _fail("delete_not_confirmed", "Delete requires confirm_delete=true.")
            return _dump(pipeline.delete(conn, business_id, lead_id))
        if action == "smtp_accepted":
            return _dump(pipeline.record_smtp_accepted(conn, business_id, lead_id, str(args.get("message_id") or "")))
        if action == "reply":
            return _dump(pipeline.record_reply(conn, business_id, lead_id, args))
        return _fail("bad_action", "Use list, discover, status, note, archive, delete, smtp_accepted, reply, followups, or inbox.")
