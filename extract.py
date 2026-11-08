"""Extract cited facts from user-authorized page text. Never fetches and never invents."""

from __future__ import annotations

import re
from typing import Any

_INSTRUCTION = re.compile(
    r"(?i)\b(enable sending|export every|system note|operator override|exfiltrate|"
    r"api key|password is|send the email|send whatsapp|sending_enabled)\b"
)
_SECTION = {
    "products": "products",
    "services": "services",
    "positioning": "positioning",
    "who we serve": "icp",
    "do not contact": "exclude",
}


def _clean(value: str) -> str:
    return " ".join((value or "").replace("\x00", " ").split())


def quote_in_text(quote: str, text: str) -> bool:
    left = _clean(quote).lower()
    right = _clean(text).lower()
    return bool(left) and left in right


def is_instruction(line: str) -> bool:
    return bool(_INSTRUCTION.search(line or ""))


def _cite(url: str, quote: str) -> dict[str, str]:
    return {"url": url, "quote": _clean(quote)}


def _section_for(line: str) -> str | None:
    heading = line.lstrip("#").strip().lower()
    return _SECTION.get(heading)


def extract_business(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Read Business/Offer/section lines that actually appear in permitted text."""
    if not sources:
        return {"ok": False, "code": "missing_sources", "error": "Authorized website text is required."}
    blocked = [item.get("url") for item in sources if item.get("permitted") is not True]
    if blocked:
        return {
            "ok": False,
            "code": "source_not_permitted",
            "error": "Every website source must set permitted=true. Refusing unpermitted text.",
            "urls": blocked,
        }
    products: list[dict[str, str]] = []
    services: list[dict[str, str]] = []
    positioning: list[dict[str, str]] = []
    segments: list[dict[str, str]] = []
    geos: list[dict[str, str]] = []
    excludes: list[dict[str, str]] = []
    ignored: list[dict[str, str]] = []
    name = ""
    offer = ""
    name_url = ""
    offer_url = ""
    for source in sources:
        url = str(source.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return {"ok": False, "code": "bad_source_url", "error": "Source URL must be http(s).", "url": url}
        text = str(source.get("text") or "")
        if not text.strip():
            return {"ok": False, "code": "empty_source", "error": "Permitted source has no text.", "url": url}
        section = ""
        for raw in text.splitlines():
            line = _clean(raw)
            if not line:
                continue
            if is_instruction(line):
                ignored.append({"url": url, "line": line[:180], "reason": "untrusted_instruction"})
                continue
            found = _section_for(line)
            if found:
                section = found
                continue
            if line.lower().startswith("business:"):
                name = line.split(":", 1)[1].strip()
                name_url = url
                continue
            if line.lower().startswith("offer:"):
                offer = line.split(":", 1)[1].strip()
                offer_url = url
                continue
            if line.lower().startswith("icp segment:"):
                segments.append(_cite(url, line.split(":", 1)[1]))
                continue
            if line.lower().startswith("icp geo:"):
                geos.append(_cite(url, line.split(":", 1)[1]))
                continue
            if line.lower().startswith("exclude:"):
                excludes.append(_cite(url, line.split(":", 1)[1]))
                continue
            if line.startswith(("- ", "* ")) and section in {"products", "services"}:
                quote = line[2:].strip()
                if quote:
                    (products if section == "products" else services).append(_cite(url, quote))
                continue
            if section == "positioning" and not line.startswith("#"):
                positioning.append(_cite(url, line))
    missing = []
    if not name:
        missing.append("business name")
    if not offer and not services:
        missing.append("offer or services")
    if missing:
        return {
            "ok": False,
            "code": "uncited_profile",
            "error": "Refusing to invent: " + ", ".join(missing) + " was not in the authorized text.",
            "ignored_instructions": ignored,
        }
    if not offer:
        offer = services[0]["quote"]
        offer_url = services[0]["url"]
    citations = [{"field": "name", "url": name_url, "quote": name}]
    citations.append({"field": "offer", "url": offer_url, "quote": offer})
    citations.extend({"field": "product", **item} for item in products)
    citations.extend({"field": "service", **item} for item in services)
    citations.extend({"field": "positioning", **item} for item in positioning)
    return {
        "ok": True,
        "fetched": False,
        "name": name,
        "offer": offer,
        "offer_short": " ".join(offer.split()[:12]),
        "products": products,
        "services": services,
        "positioning": positioning,
        "segments": [item["quote"] for item in segments],
        "geos": [item["quote"] for item in geos],
        "exclude": [item["quote"] for item in excludes],
        "citations": citations,
        "ignored_instructions": ignored,
        "sending_enabled": False,
    }


def extract_prospect(company_hint: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Pull only labeled facts that occur in permitted public text."""
    if not sources:
        return {"ok": False, "code": "missing_sources", "error": "Permitted public source text is required."}
    blocked = [item.get("url") for item in sources if item.get("permitted") is not True]
    if blocked:
        return {
            "ok": False,
            "code": "source_not_permitted",
            "error": "Research sources must set permitted=true.",
            "urls": blocked,
        }
    fields = {
        "company": "",
        "contact_name": "",
        "role": "",
        "segment": "",
        "country": "",
        "email": "",
        "phone": "",
        "fact": "",
    }
    unknowns: list[str] = []
    citations: list[dict[str, str]] = []
    ignored: list[dict[str, str]] = []
    masked = False
    primary_url = ""
    combined = []
    labels = {
        "company": "company",
        "contact": "contact_name",
        "role": "role",
        "segment": "segment",
        "country": "country",
        "email": "email",
        "phone": "phone",
        "fact": "fact",
        "unknown": "unknown",
    }
    for source in sources:
        url = str(source.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            return {"ok": False, "code": "bad_source_url", "error": "Source URL must be http(s).", "url": url}
        text = str(source.get("text") or "")
        if not text.strip():
            return {"ok": False, "code": "empty_source", "error": "Permitted source has no text.", "url": url}
        if not primary_url:
            primary_url = url
        combined.append(text)
        for raw in text.splitlines():
            line = _clean(raw)
            if not line:
                continue
            if is_instruction(line):
                ignored.append({"url": url, "line": line[:180], "reason": "untrusted_instruction"})
                continue
            if "*" in line and re.search(r"\d\*", line):
                masked = True
                unknowns.append("masked contact digits were not completed")
                continue
            if ":" not in line:
                continue
            label, value = line.split(":", 1)
            key = labels.get(label.strip().lower())
            value = value.strip()
            if not key or not value:
                continue
            if key == "unknown":
                unknowns.append(value)
                continue
            if not fields[key]:
                fields[key] = value
                citations.append({"field": key, "url": url, "quote": value})
    blob = "\n".join(combined)
    for item in citations:
        if not quote_in_text(item["quote"], blob):
            return {"ok": False, "code": "quote_not_in_source", "error": "Extractor emitted a quote that is not in the source."}
    company = fields["company"] or _clean(company_hint)
    if company and not quote_in_text(company, blob):
        return {
            "ok": False,
            "code": "company_not_in_source",
            "error": "Company name is not in the permitted source text.",
        }
    if not fields["fact"]:
        unknowns.append("no fact line in the permitted source")
    if not fields["email"] and not fields["phone"]:
        unknowns.append("no public email or phone in the permitted source")
    if not fields["role"]:
        unknowns.append("role not stated")
    score = 0
    breakdown = []
    if company:
        score += 25
        breakdown.append({"signal": "company_in_source", "points": 25})
    if fields["fact"]:
        score += 25
        breakdown.append({"signal": "fact_quote", "points": 25})
    if primary_url:
        score += 15
        breakdown.append({"signal": "http_source_recorded_not_fetched", "points": 15})
    if fields["email"] or fields["phone"]:
        score += 20
        breakdown.append({"signal": "public_contact_in_source", "points": 20})
    if fields["role"]:
        score += 10
        breakdown.append({"signal": "role_in_source", "points": 10})
    if masked:
        breakdown.append({"signal": "masked_digits_rejected", "points": 0})
    label = "high" if score >= 70 else "medium" if score >= 40 else "low"
    return {
        "ok": True,
        "fetched": False,
        "company": company,
        "contact_name": fields["contact_name"],
        "role": fields["role"],
        "segment": fields["segment"],
        "country": fields["country"],
        "email": fields["email"],
        "phone": "" if masked else fields["phone"],
        "evidence": fields["fact"],
        "source_url": primary_url,
        "unknowns": list(dict.fromkeys(unknowns)),
        "citations": citations,
        "ignored_instructions": ignored,
        "confidence": {"score": score, "label": label, "breakdown": breakdown, "registered": False},
        "masked_contact": masked,
    }
