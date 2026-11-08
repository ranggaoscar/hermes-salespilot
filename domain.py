"""Pure sales rules. No Hermes imports, no network, no secrets."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

TEMPLATE_VERSION = "phase2-v1"
QUALIFIED_SCORE = 70
SCHEMA_VERSION = 6

_NOW: Callable[[], datetime] | None = None


def use_clock(fn: Callable[[], datetime] | None) -> None:
    """Test hook. Production leaves this unset."""
    global _NOW
    _NOW = fn


def utcnow() -> datetime:
    if _NOW is not None:
        return _NOW()
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    value = dt or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day(dt: datetime | None = None) -> str:
    return iso(dt)[:10]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def norm_token(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def company_key(value: str | None) -> str:
    return norm_token(value)


def normalize_email(value: str | None) -> dict[str, Any]:
    raw = (value or "").strip().lower()
    if not raw:
        return {"value": "", "valid": False, "reason": "missing"}
    if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", raw):
        return {"value": raw, "valid": False, "reason": "invalid_format"}
    return {"value": raw, "valid": True, "reason": "format_only"}


def normalize_phone(value: str | None, country: str | None) -> dict[str, Any]:
    """Format check only. A valid digit string is not proof of WhatsApp registration."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return {"digits": "", "valid": False, "reason": "missing", "registered": False}
    code = (country or "").strip().upper()
    if code in {"ID", "IDN", "INDONESIA"}:
        if digits.startswith("0"):
            digits = "62" + digits[1:]
        if digits.startswith("620"):
            return {"digits": digits, "valid": False, "reason": "duplicated_trunk", "registered": False}
        valid = digits.startswith("62") and (
            11 <= len(digits) <= 13 or (len(digits) == 14 and digits.startswith(("62895", "62896")))
        )
        reason = "format_only" if valid else "invalid_id_length"
        return {"digits": digits, "valid": valid, "reason": reason, "registered": False}
    if not 8 <= len(digits) <= 15:
        return {"digits": digits, "valid": False, "reason": "invalid_e164_length", "registered": False}
    return {"digits": digits, "valid": True, "reason": "e164_length_only", "registered": False}


FREEMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.id", "ymail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "icloud.com", "me.com", "aol.com", "proton.me",
    "protonmail.com", "gmx.com", "mail.com", "zoho.com",
}

# Role mailboxes answer the phone, they do not buy. Finding one is not qualification.
ROLE_MAILBOX_PREFIXES = {
    "reservation": "reservation", "reservations": "reservation", "reservasi": "reservation",
    "booking": "reservation", "bookings": "reservation",
    "cs": "customer service", "customerservice": "customer service", "customercare": "customer service",
    "care": "customer service", "support": "support", "helpdesk": "support",
    "info": "general", "informasi": "general", "admin": "general", "administrasi": "general",
    "contact": "general", "kontak": "general", "hello": "general", "halo": "general",
    "office": "general", "sekretariat": "general", "secretariat": "general", "humas": "general",
    "sales": "sales", "marketing": "marketing", "promo": "marketing", "penjualan": "sales",
    "commercial": "commercial", "corporate": "commercial", "business": "commercial",
    "purchasing": "purchasing", "purchase": "purchasing", "procurement": "purchasing",
    "logistik": "operations", "logistics": "operations", "operation": "operations",
    "operations": "operations", "gudang": "operations", "warehouse": "operations",
}

# Official desks that a vendor may legitimately approach about procurement or partnership.
BUSINESS_CONTACT_PREFIXES = {
    "procurement": "procurement", "purchasing": "procurement", "purchase": "procurement",
    "pengadaan": "procurement", "vendor": "procurement", "vendors": "procurement",
    "supplier": "procurement", "partnership": "partnership", "partners": "partnership",
    "kemitraan": "partnership", "b2b": "partnership", "corporate": "partnership",
    "commercial": "commercial", "business": "commercial", "fleet": "fleet",
    "logistik": "operations", "logistics": "operations", "operations": "operations",
    "operasional": "operations", "transport": "operations", "warehouse": "operations",
    "gudang": "operations",
}

# Titles that actually sit on a fleet or procurement decision.
BUYER_ROLE_TOKENS = {
    "owner", "founder", "director", "direktur", "dirut", "ceo", "cto", "coo", "cfo", "cmo",
    "gm", "general manager", "manager", "manajer", "head", "kepala", "vp", "vice president",
    "president", "principal", "partner", "chief", "purchasing", "procurement", "pengadaan",
    "fleet", "transport", "transportation", "logistics", "logistik", "operations", "operasional",
    "ga", "general affairs", "facility", "facilities", "engineering", "project", "proyek",
}


def _list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def recipient_profile(value: str | None) -> dict[str, Any]:
    """Classify the mailbox, not just the syntax.

    A syntactically valid address is not a deliverable one, and a role mailbox is not a buyer.
    """
    email = normalize_email(value)
    if not email["valid"]:
        return {
            "value": email["value"], "kind": "missing" if email["reason"] == "missing" else "invalid",
            "role": "", "local_part": "", "domain": "", "freemail": False,
            "deliverability": "unverified", "deliverability_reason": email["reason"],
        }
    local, _, domain = email["value"].partition("@")
    tokens = [part for part in re.split(r"[^a-z0-9]+", local) if part]
    role = ""
    for token in tokens:
        if token in ROLE_MAILBOX_PREFIXES:
            role = ROLE_MAILBOX_PREFIXES[token]
            break
    freemail = domain in FREEMAIL_DOMAINS
    if role:
        kind = "role"
    elif freemail:
        kind = "freemail"
    elif len(tokens) >= 2 or re.search(r"[._\-+]", local):
        kind = "person"
    else:
        kind = "unknown"
    return {
        "value": email["value"], "kind": kind, "role": role, "local_part": local, "domain": domain,
        "freemail": freemail, "deliverability": "unverified",
        "deliverability_reason": "syntax_only_no_domain_or_mailbox_check",
    }


READINESS_DECISION_MAKER = "decision_maker"
READINESS_BUSINESS_CONTACT = "business_contact"
READINESS_ROLE_GENERIC = "role_generic"
READINESS_PERSON_UNKNOWN_ROLE = "person_unknown_role"
READINESS_MISSING = "missing"


def recipient_readiness(value: str | None, role: str | None = None) -> dict[str, Any]:
    """Readiness is about who reads the mail, not whether the address parses."""
    recipient = recipient_profile(value)
    kind = recipient["kind"]
    local = recipient.get("local_part") or ""
    tokens = [part for part in re.split(r"[^a-z0-9]+", local) if part]
    desk = next((BUSINESS_CONTACT_PREFIXES[token] for token in tokens if token in BUSINESS_CONTACT_PREFIXES), "")
    buyer = role_is_buyer(role)
    if kind == "missing" or kind == "invalid":
        status, reason = READINESS_MISSING, "no_mailbox"
    elif kind == "freemail":
        status, reason = READINESS_ROLE_GENERIC, "freemail_not_corporate_mailbox"
    elif kind == "person" and buyer:
        status, reason = READINESS_DECISION_MAKER, "named_person_with_buyer_role"
    elif desk:
        status, reason = READINESS_BUSINESS_CONTACT, f"official_{desk}_desk"
    elif kind == "role":
        status, reason = READINESS_ROLE_GENERIC, f"generic_{recipient.get('role') or 'role'}_desk"
    elif kind == "person":
        status, reason = READINESS_PERSON_UNKNOWN_ROLE, "named_person_without_buyer_role"
    else:
        status, reason = READINESS_ROLE_GENERIC, "unidentified_recipient"
    return {
        "status": status,
        "reason": reason,
        "desk": desk,
        "buyer_role": buyer,
        "kind": kind,
        "role_label": recipient.get("role") or "",
        "deliverability": recipient["deliverability"],
        "deliverability_reason": recipient["deliverability_reason"],
        "requires_review": status in {READINESS_BUSINESS_CONTACT, READINESS_PERSON_UNKNOWN_ROLE},
    }


def company_fit(rules: dict[str, Any], lead: dict[str, Any], *, blocked: str | None,
                has_evidence: bool, source_ok: bool) -> dict[str, Any]:
    """Company-level decision, independent of which mailbox was found."""
    if blocked:
        return {"status": "excluded", "reason": f"excluded:{blocked}"}
    if not company_key(lead.get("company")):
        return {"status": "rejected", "reason": "missing_company"}
    if not has_evidence or not source_ok:
        return {"status": "unproven", "reason": "missing_evidence_or_source"}
    if rules["status"] == "needs_configuration":
        return {"status": "unproven", "reason": "icp_needs_configuration"}
    if not rules["defined"]:
        return {"status": "unproven", "reason": "icp_not_defined"}
    hay = " ".join([str(lead.get("segment") or ""), str(lead.get("company") or ""),
                    str(lead.get("evidence") or "")])
    industries = rules["industries"]
    geos = rules["geos"]
    if industries and not any(_contains(item, hay) for item in industries):
        return {"status": "outside_icp", "reason": "industry_outside_icp"}
    country = str(lead.get("country") or "")
    if geos and not any(_contains(item, country) or _contains(country, item) for item in geos):
        return {"status": "outside_icp", "reason": "geo_outside_icp"}
    return {"status": "fit", "reason": ""}


ICP_ROLE_WORDS = ("manager", "manajer", "director", "direktur", "owner", "founder", "head",
                  "chief", "procurement", "purchasing", "buyer", "gm", "ceo", "cfo", "coo")


def normalize_icp(icp: dict[str, Any] | None) -> dict[str, Any]:
    """Split the ICP into industries, locations and buyer roles, and flag what cannot be used.

    Legacy ICPs stored one sentence ("Corporate fleet managers in Jakarta and Bali") that mixed a
    buyer role, an industry and a place. That is not usable as a match rule: it is reported as
    needs_configuration instead of silently rejecting every company.
    """
    icp = icp if isinstance(icp, dict) else {}
    industries = _list(icp.get("industries") or icp.get("segments"))
    locations = _list(icp.get("locations") or icp.get("geos"))
    buyer_roles = _list(icp.get("buyer_roles") or icp.get("roles"))
    exclude = _list(icp.get("exclude"))
    structured = any(key in icp for key in ("industries", "locations", "buyer_roles"))
    issues: list[str] = []
    for item in industries:
        token = norm_token(item)
        if not token:
            continue
        if any(_contains(word, token) for word in ICP_ROLE_WORDS):
            issues.append(f"industry_contains_buyer_role:{item}")
        if " in " in f" {token} ":
            issues.append(f"industry_contains_location_phrase:{item}")
        if any(_contains(place, token) for place in locations):
            issues.append(f"industry_contains_location:{item}")
    if not industries and not locations and not buyer_roles:
        status = "missing"
    elif issues:
        status = "needs_configuration"
    else:
        status = "configured"
    return {
        "industries": industries,
        "locations": locations,
        "buyer_roles": buyer_roles,
        "exclude": exclude,
        "structured": structured,
        "issues": issues[:6],
        "status": status,
    }


def icp_rules(profile: dict[str, Any]) -> dict[str, Any]:
    """Business DNA: which industries, places and buyer roles this brand actually sells to."""
    icp = profile.get("icp") or {}
    dna = profile.get("business_dna") or profile.get("dna") or {}
    if not isinstance(dna, dict):
        dna = {"summary": str(dna)}
    normalized = normalize_icp(icp)
    industries = normalized["industries"] or _list(dna.get("industries"))
    geos = normalized["locations"] or _list(dna.get("locations"))
    roles = normalized["buyer_roles"] or _list(dna.get("buyer_roles"))
    status = normalized["status"]
    if status == "missing" and (industries or geos or roles):
        status = "configured"
    return {
        "industries": industries,
        "geos": geos,
        "roles": roles,
        "exclude": normalized["exclude"],
        "defined": status == "configured",
        "status": status,
        "issues": normalized["issues"],
        "structured": normalized["structured"],
        "source": "icp" if (icp.get("industries") or icp.get("segments") or icp.get("geos")
                            or icp.get("roles") or icp.get("buyer_roles")) else ("dna" if dna else "none"),
        "summary": str(dna.get("summary") or "")[:400],
    }


def role_is_buyer(value: str | None, wanted: list[str] | None = None) -> bool:
    role = norm_token(value)
    if not role:
        return False
    if wanted:
        return any(_contains(item, role) or _contains(role, item) for item in wanted)
    return any(_contains(token, role) for token in BUYER_ROLE_TOKENS)


def _stage_for(fit: dict[str, Any], readiness: dict[str, Any]) -> str:
    """Company fit and recipient readiness are separate axes.

    A hotel with only reservation@ is still a matching company; it is simply not addressable yet.
    """
    if fit["status"] in {"rejected", "excluded"}:
        return "rejected"
    if fit["status"] != "fit":
        return "discovered"
    if readiness["status"] in {READINESS_DECISION_MAKER, READINESS_BUSINESS_CONTACT}:
        return "qualified_company"
    return "qualified_company"


def stage_label(
    stage: str,
    status: str,
    readiness_status: str = "",
    *,
    suppressed: bool = False,
    approved_contact: bool = False,
) -> str:
    """Operator view. Ready for outreach needs a relevant contact, a clean record and approval."""
    status = status or "discovered"
    if status == "do_not_contact" or suppressed:
        return "suppressed"
    if status == "archived":
        return "archived"
    if stage == "rejected":
        return "rejected"
    if stage != "qualified_company":
        return "discovered"
    relevant = readiness_status in {READINESS_DECISION_MAKER, READINESS_BUSINESS_CONTACT}
    reviewed = (readiness_status == READINESS_DECISION_MAKER or approved_contact
                or status == "draft_ready")
    if status in {"qualified", "draft_ready"} and relevant and reviewed and not suppressed:
        return "ready_for_outreach"
    return "qualified_company"


def excluded(profile: dict[str, Any], lead: dict[str, Any]) -> str | None:
    hay = norm_token(f"{lead.get('company', '')} {lead.get('segment', '')}")
    for raw in _list((profile.get("icp") or {}).get("exclude")):
        token = norm_token(raw)
        if len(token) >= 4 and token in hay:
            return token
    return None


def _contains(needle: str, hay: str) -> bool:
    left, right = norm_token(needle), norm_token(hay)
    return bool(left) and left in right


def _recommendation(stage: str, fit: dict[str, Any], readiness: dict[str, Any],
                    rules: dict[str, Any]) -> dict[str, Any]:
    """What Hermes should do next. Never a send."""
    if stage == "rejected":
        return {"action": "skip", "why": fit["reason"] or "blocked", "targets": []}
    if stage == "discovered":
        return {"action": "research_company", "why": fit["reason"] or "icp_not_satisfied", "targets": []}
    if readiness["status"] == READINESS_DECISION_MAKER:
        return {"action": "await_approval", "why": "named buyer on a verified source", "targets": []}
    if readiness["status"] == READINESS_BUSINESS_CONTACT:
        return {"action": "review_business_contact", "why": readiness["reason"], "targets": [],
                "note": "Official procurement/partnership desk. Keep it, review before any draft."}
    targets = rules["roles"] or ["Fleet Manager", "Procurement", "General Manager", "Director"]
    return {"action": "find_decision_maker", "why": readiness["reason"], "targets": targets[:5],
            "note": "Company fits the ICP; the mailbox on file is not a buyer."}


def qualify(profile: dict[str, Any], lead: dict[str, Any]) -> dict[str, Any]:
    """Score a prospect from supplied facts. Never invents contact, price, or reply state."""
    icp = profile.get("icp") or {}
    rules = icp_rules(profile)
    country = lead.get("country") or profile.get("default_country") or ""
    phone = normalize_phone(lead.get("phone"), profile.get("default_country"))
    email = normalize_email(lead.get("email"))
    recipient = recipient_profile(lead.get("email"))
    readiness = recipient_readiness(lead.get("email"), lead.get("role"))
    evidence = " ".join(str(lead.get("evidence") or "").split())
    source = str(lead.get("source_url") or "").strip()
    source_ok = source.startswith(("https://", "http://"))
    contact_ok = bool(email["valid"] or phone["valid"])
    segments = rules["industries"]
    geos = rules["geos"]
    industry_hay = " ".join([
        str(lead.get("segment") or ""), str(lead.get("company") or ""), str(lead.get("evidence") or "")
    ])
    segment_ok = True if not segments else any(_contains(item, industry_hay) for item in segments)
    geo_ok = True if not geos else any(
        _contains(item, str(lead.get("country") or "")) or _contains(str(lead.get("country") or ""), item)
        for item in geos
    )
    role_ok = role_is_buyer(lead.get("role"), rules["roles"])
    recipient_ok = recipient["kind"] == "person"
    gates = {
        "company": bool(company_key(lead.get("company"))),
        "evidence": bool(evidence),
        "source": source_ok,
        "contact": contact_ok,
        "segment": segment_ok,
        "geo": geo_ok,
        "industry": segment_ok,
        "role": role_ok,
        "recipient": recipient_ok,
        "icp": rules["defined"],
    }
    reasons: list[str] = []
    blocker = excluded(profile, lead)
    if blocker:
        reasons.append(f"excluded:{blocker}")
    if not gates["company"]:
        reasons.append("missing_company")
    if not gates["evidence"]:
        reasons.append("missing_evidence")
    if not gates["source"]:
        reasons.append("missing_or_non_http_source")
    if not gates["contact"]:
        reasons.append("missing_valid_public_contact")
    elif lead.get("phone") and not phone["valid"]:
        reasons.append(f"phone_invalid:{phone['reason']}")
    if email["valid"]:
        reasons.append("email_format_only")
    if phone["valid"]:
        reasons.append("phone_format_only_not_registration")
    if rules["status"] == "needs_configuration":
        reasons.append("icp_needs_configuration")
    elif rules["status"] == "missing":
        reasons.append("icp_not_defined")
    elif segments and not segment_ok:
        reasons.append("industry_outside_icp")
    if rules["status"] == "configured" and geos and not geo_ok:
        reasons.append("geo_outside_icp")
    if not str(lead.get("role") or "").strip():
        reasons.append("missing_contact_role")
    elif not role_ok:
        reasons.append("role_not_a_buyer")
    if recipient["kind"] == "role":
        reasons.append(f"recipient_role_mailbox:{recipient['role'] or recipient['local_part']}")
    elif recipient["kind"] == "freemail":
        reasons.append("recipient_freemail_not_corporate")
    elif recipient["kind"] in {"unknown", "invalid", "missing"} and email["valid"]:
        reasons.append("recipient_unidentified_person")
    unknowns = _list(lead.get("unknowns"))
    if unknowns:
        reasons.append("unknowns:" + ", ".join(unknowns[:6]))

    fit = company_fit(rules, lead, blocked=blocker, has_evidence=bool(evidence), source_ok=source_ok)
    if fit["reason"] and fit["reason"] not in reasons:
        reasons.append(fit["reason"])
    if readiness["status"] != READINESS_DECISION_MAKER and readiness["reason"] not in reasons:
        reasons.append(readiness["reason"])

    score = 0
    if gates["evidence"]:
        score += 25
    if gates["source"]:
        score += 20
    if gates["contact"]:
        score += 20
    if gates["segment"]:
        score += 15
    if gates["geo"]:
        score += 10
    if str(lead.get("role") or "").strip():
        score += 10
    if lead.get("phone") and not phone["valid"]:
        score -= 30
    if not gates["source"]:
        score -= 10
    score = max(0, min(100, score))

    required = ["company", "evidence", "source", "contact", "segment", "geo"]
    if blocker or not gates["company"]:
        decision = "reject"
    elif all(gates[name] for name in required) and score >= QUALIFIED_SCORE:
        decision = "qualified"
    else:
        decision = "hold"
    stage = _stage_for(fit, readiness)
    recommendation = _recommendation(stage, fit, readiness, rules)
    return {
        "decision": decision,
        "stage": stage,
        "company_fit": fit,
        "readiness": readiness,
        "recommendation": recommendation,
        "outreach_ready": False,
        "score": 0 if decision == "reject" and blocker else score,
        "reasons": reasons,
        "gates": gates,
        "phone": phone,
        "email": email,
        "recipient": recipient,
        "rules": {
            "industries": rules["industries"],
            "geos": rules["geos"],
            "roles": rules["roles"],
            "defined": rules["defined"],
            "status": rules["status"],
            "issues": rules["issues"],
            "source": rules["source"],
        },
        "unknowns": unknowns,
        "country": country,
        "send_allowed": False,
    }


def draft_revision(draft: dict[str, Any]) -> str:
    blob = "|".join([
        str(draft.get("channel") or ""),
        str(draft.get("subject") or ""),
        str(draft.get("body") or ""),
        str(draft.get("recipient") or ""),
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def idempotency_key(*parts: str) -> str:
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:24]


def clip(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def render_draft(profile: dict[str, Any], lead: dict[str, Any], channel: str, cta: str | None = None) -> dict[str, Any]:
    if lead.get("decision") != "qualified":
        return {
            "ok": False,
            "code": "not_qualified",
            "error": "Drafts are only built for qualified leads. Fill the hold reasons first.",
        }
    channel = (channel or "").strip().lower()
    if channel not in {"email", "whatsapp"}:
        return {"ok": False, "code": "bad_channel", "error": "channel must be email or whatsapp"}
    if channel == "email" and not (lead.get("email_valid") or normalize_email(lead.get("email"))["valid"]):
        return {"ok": False, "code": "missing_email", "error": "Qualified lead has no format-valid email for this channel."}
    if channel == "whatsapp" and not (lead.get("phone_valid") or normalize_phone(lead.get("phone"), profile.get("default_country"))["valid"]):
        return {"ok": False, "code": "missing_phone", "error": "Qualified lead has no format-valid phone for this channel."}
    action = clip(cta or profile.get("default_cta") or "", 180)
    if not action:
        return {"ok": False, "code": "missing_cta", "error": "A single CTA is required."}
    company = str(lead.get("company") or "the company")
    name = str(lead.get("contact_name") or "").strip() or "there"
    evidence = clip(str(lead.get("evidence") or ""), 220)
    offer = clip(str(profile.get("offer") or ""), 180)
    business = str(profile.get("name") or "the team")
    source_url = str(lead.get("source_url") or "").strip()
    citation = f"\nSource: {source_url}" if source_url else ""
    if channel == "email":
        pitch = str(profile.get("offer_short") or offer or "").strip()
        # "…for Indonesian businesses for PT X" is a doubled preposition; when the short offer already
        # names its audience, the company stays in the body instead of the subject.
        subject = clip(f"{business}: {pitch}" if " for " in pitch.lower() else f"{business}: {pitch} for {company}", 110)
        body = (
            f"Hi {name},\n\n"
            f"Note on file for {company}: {evidence}{citation}\n\n"
            f"{offer}\n\n"
            f"{action}\n\n"
            f"{business}"
        )
        signature = str((profile.get("profile") or {}).get("signature") or profile.get("signature") or "").strip()
        sender = str((profile.get("profile") or {}).get("sender_name") or profile.get("sender_name") or "").strip()
        if sender or signature:
            body += "\n\n" + "\n".join(part for part in (sender, signature) if part)
        recipient = normalize_email(lead.get("email"))["value"]
    else:
        subject = ""
        body = (
            f"Hi {name} — {business}. Note on {company}: {evidence} "
            f"{offer} {action}"
        )
        recipient = normalize_phone(lead.get("phone"), profile.get("default_country"))["digits"]
    key = idempotency_key(
        str(profile.get("id") or profile.get("name") or ""),
        str(lead.get("id") or company_key(company)),
        channel,
        TEMPLATE_VERSION,
        action,
    )
    return {
        "ok": True,
        "channel": channel,
        "subject": subject,
        "body": body,
        "cta": action,
        "recipient": recipient,
        "idempotency_key": key,
        "template_version": TEMPLATE_VERSION,
        "status": "draft",
        "sent": False,
        "send_blocked": True,
    }


def plan_one(
    lead: dict[str, Any],
    drafts: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    *,
    now: datetime,
    cadence_days: int,
) -> dict[str, Any]:
    """Recommend the next human step. Never recommends a send."""
    due_now = day(now)
    due_later = day(now + timedelta(days=max(1, cadence_days)))
    scheduled_now = iso(now)
    scheduled_later = iso(now + timedelta(days=max(1, cadence_days)))
    base = {"lead_id": lead.get("id"), "company": lead.get("company"), "send": False}
    if lead.get("decision") == "reject":
        return {**base, "action": "no_action", "reason": "Lead is rejected.", "due_on": due_now, "scheduled_for": scheduled_now}
    if lead.get("decision") != "qualified":
        return {
            **base,
            "action": "fill_gap",
            "reason": "Hold until evidence, source, ICP fit, and a format-valid public contact are present.",
            "due_on": due_now,
            "scheduled_for": scheduled_now,
        }
    own = [item for item in drafts if item.get("lead_id") == lead.get("id")]
    draft = max(own, key=lambda item: item.get("created_at") or "", default=None)
    if draft is None:
        return {**base, "action": "draft_outreach", "reason": "Qualified lead has no draft.", "due_on": due_now, "scheduled_for": scheduled_now}
    own_approvals = [item for item in approvals if item.get("draft_id") == draft.get("id")]
    approval = max(own_approvals, key=lambda item: item.get("updated_at") or item.get("created_at") or "", default=None)
    stale = (draft.get("created_at") or "") < (lead.get("updated_at") or "")
    if approval is None:
        return {
            **base,
            "action": "request_approval",
            "reason": "Draft exists and has not been submitted for approval.",
            "due_on": due_now,
            "scheduled_for": scheduled_now,
            "draft_id": draft.get("id"),
            "stale": stale,
        }
    status = approval.get("status")
    if status == "pending":
        return {
            **base,
            "action": "wait_for_decision",
            "reason": "Approval is pending. Do not send while waiting.",
            "due_on": due_later,
            "scheduled_for": scheduled_later,
            "draft_id": draft.get("id"),
            "stale": stale,
        }
    if status == "rejected":
        return {
            **base,
            "action": "revise_draft",
            "reason": "Approval was rejected. Revise or stop. Do not send.",
            "due_on": due_now,
            "scheduled_for": scheduled_now,
            "draft_id": draft.get("id"),
            "stale": stale,
        }
    return {
        **base,
        "action": "hold_approved_unsent",
        "reason": "Approved in the ledger, but sending is disabled.",
        "due_on": due_later,
        "scheduled_for": scheduled_later,
        "draft_id": draft.get("id"),
        "stale": stale,
    }


def summarize(snapshot: dict[str, Any]) -> dict[str, Any]:
    leads = snapshot.get("leads") or []
    drafts = snapshot.get("drafts") or []
    approvals = snapshot.get("approvals") or []
    followups = snapshot.get("followups") or []
    by_decision: dict[str, int] = {}
    for lead in leads:
        key = str(lead.get("decision") or "unknown")
        by_decision[key] = by_decision.get(key, 0) + 1
    by_approval: dict[str, int] = {}
    for item in approvals:
        key = str(item.get("status") or "unknown")
        by_approval[key] = by_approval.get(key, 0) + 1
    due = [item for item in followups if item.get("status") == "recommended"]
    return {
        "customers": len(snapshot.get("customers") or []),
        "leads": len(leads),
        "by_decision": by_decision,
        "drafts": len(drafts),
        "approvals": by_approval,
        "recommended_followups": len(due),
        "sending_enabled": False,
        "phase": 2,
    }
