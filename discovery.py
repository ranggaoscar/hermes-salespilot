"""Extract prospect cards that are literally present in a fetched directory page."""

from __future__ import annotations

from typing import Any

try:
    from . import extract
except ImportError:
    import extract


def discover_companies(text: str, page_url: str) -> dict[str, Any]:
    cards = []
    current: dict[str, str] = {}
    ignored = []
    for raw in text.splitlines():
        line = " ".join(raw.replace("\x00", " ").split())
        if not line:
            if current.get("company"):
                cards.append(current)
            current = {}
            continue
        if extract.is_instruction(line):
            ignored.append(line[:180])
            continue
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = label.strip().lower()
        value = value.strip()
        mapped = {
            "company": "company",
            "segment": "segment",
            "country": "country",
            "page": "page",
            "url": "page",
            "why": "why",
            "email": "email",
            "phone": "phone",
            "role": "role",
        }.get(key)
        if mapped and value and extract.quote_in_text(value, text):
            current[mapped] = value
    if current.get("company"):
        cards.append(current)
    prospects = []
    for card in cards:
        if "*" in card.get("phone", ""):
            card = {**card, "phone": ""}
            card["unknown"] = "masked digits were not completed"
        if not card.get("why"):
            continue
        prospects.append({
            "company": card["company"],
            "segment": card.get("segment") or "",
            "country": card.get("country") or "",
            "email": card.get("email") or "",
            "phone": card.get("phone") or "",
            "role": card.get("role") or "",
            "evidence": card["why"],
            "source_url": card.get("page") or page_url,
            "citations": [{"url": page_url, "quote": card["why"]}, {"url": page_url, "quote": card["company"]}],
        })
    return {"ok": True, "prospects": prospects, "ignored_instructions": ignored, "fetched": True}
