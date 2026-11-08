"""Quoted business DNA and dated signals. No network and no invented intent."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

try:
    from . import domain, extract
except ImportError:
    import domain
    import extract

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUEST = re.compile(r"(?i)\b(requested a quote|asked for a proposal|wants a bid)\b")


def _clean(value: str) -> str:
    return " ".join((value or "").replace("\x00", " ").split())


def _blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            if current:
                blocks.append(current)
            current = {}
            continue
        if extract.is_instruction(line) or ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = label.strip().lower()
        value = value.strip()
        mapped = {
            "differentiator": "differentiator",
            "offer": "offer",
            "segment": "segment",
            "company": "company",
            "date": "date",
            "signal": "signal",
            "email": "email",
        }.get(key)
        if mapped and value and extract.quote_in_text(value, text):
            current[mapped] = value
    if current:
        blocks.append(current)
    return blocks


def read_dna(text: str, url: str) -> list[dict[str, Any]]:
    rows = []
    for block in _blocks(text):
        claim = block.get("differentiator") or ""
        offer = block.get("offer") or ""
        segment = block.get("segment") or ""
        if not claim or not offer:
            continue
        rows.append({
            "claim": claim,
            "offer": offer,
            "segment": segment,
            "source_url": url,
            "quote": claim,
            "confidence": "sourced",
            "intent": "not_inferred",
        })
    return rows


def read_signals(text: str, url: str, offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {_clean(item.get("offer") or "").lower(): item for item in offers if item.get("offer")}
    rows = []
    for block in _blocks(text):
        company = block.get("company") or ""
        signal = block.get("signal") or ""
        observed = block.get("date") or ""
        if not company or not signal or not _DATE.fullmatch(observed):
            continue
        try:
            datetime.strptime(observed, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        offer_name = block.get("offer") or ""
        offer = known.get(_clean(offer_name).lower()) if offer_name else None
        email = block.get("email") or ""
        email_ok = bool(email) and domain.normalize_email(email)["valid"] and extract.quote_in_text(email, text)
        stated = bool(_REQUEST.search(signal))
        rows.append({
            "company": company,
            "company_key": domain.company_key(company),
            "signal": signal,
            "observed_on": observed,
            "source_url": url,
            "quote": signal,
            "offer": offer["offer"] if offer else "",
            "segment": (offer or {}).get("segment") or "",
            "offer_fit": "mapped" if offer else "none",
            "email": email if email_ok else "",
            "intent": "stated_in_source" if stated else "not_inferred",
            "confidence": "sourced",
            "dedupe_key": hashlib.sha256(f"{domain.company_key(company)}|{observed}|{signal}|{url}".encode()).hexdigest()[:20],
        })
    return rows


def card_for(signal: dict[str, Any]) -> dict[str, Any]:
    why = signal["quote"]
    offer = signal.get("offer") or ""
    fit = signal.get("offer_fit") or "none"
    contact = signal.get("email") or ""
    return {
        "company": signal["company"],
        "why": why,
        "offer": offer or None,
        "offer_fit": fit,
        "evidence": {"quote": why, "url": signal["source_url"], "observed_on": signal["observed_on"]},
        "intent": signal["intent"],
        "contact": contact or None,
        "next_action": "draft_for_authorized_recipient" if contact else "hold_missing_contact",
        "send": False,
        "auto_send": False,
    }
