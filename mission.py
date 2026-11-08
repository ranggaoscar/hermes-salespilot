"""Persistent mission graph. Quotes only. Does not send."""

from __future__ import annotations

import json
from typing import Any

try:
    from . import graph, storage
except ImportError:
    import graph
    import storage


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _fail(code: str, error: str) -> str:
    return _dump({"ok": False, "code": code, "error": error, "sent": False, "sending_enabled": False, "cards": []})


def _sources(args: dict[str, Any]) -> list[dict[str, Any]] | str:
    sources = args.get("sources")
    if isinstance(sources, list) and sources:
        return sources
    text = str(args.get("text") or "")
    url = str(args.get("url") or "")
    if text and url:
        return [{"url": url, "text": text, "permitted": args.get("permitted", True)}]
    return "missing_sources"


def mission(args: dict, **kwargs) -> str:
    del kwargs
    args = args or {}
    action = str(args.get("action") or "resume").strip().lower()
    name = str(args.get("name") or "").strip()
    if not name:
        return _fail("missing_name", "A mission name is required.")
    with storage.unit_of_work() as conn:
        business = storage.get_business(conn, str(args.get("business_id") or ""))
        if business is None:
            return _fail("missing_business", "Onboard a business first.")
        if action == "resume":
            found = storage.get_mission(conn, business["id"], name)
            if found is None:
                return _fail("mission_not_found", "No saved mission with that name.")
            return _dump(_view(conn, found))
        if action not in {"save_dna", "scan"}:
            return _fail("bad_action", "action must be save_dna, scan, or resume.")
        sources = _sources(args)
        if isinstance(sources, str):
            return _fail(sources, "Permitted text and an http(s) URL are required.")
        for source in sources:
            if source.get("permitted") is not True:
                return _fail("source_not_permitted", "Every source must set permitted=true.")
            url = str(source.get("url") or "")
            if not url.startswith(("https://", "http://")):
                return _fail("bad_source_url", "Source URL must be http(s).")
        saved = storage.save_mission(conn, business["id"], name)
        if action == "save_dna":
            claims = []
            for source in sources:
                for claim in graph.read_dna(str(source.get("text") or ""), str(source["url"])):
                    claims.append(storage.save_dna_claim(conn, saved["id"], business["id"], claim))
            if not claims:
                return _fail("no_quoted_dna", "No differentiator and offer were quoted in the text.")
        else:
            offers = storage.list_dna(conn, saved["id"])
            if not offers:
                return _fail("missing_dna", "Save quoted business DNA before scanning signals.")
            found = []
            for source in sources:
                for signal in graph.read_signals(str(source.get("text") or ""), str(source["url"]), offers):
                    found.append(storage.save_signal(conn, saved["id"], business["id"], signal))
            if not found:
                view = _view(conn, storage.get_mission(conn, business["id"], name) or saved)
                view["new_signals"] = 0
                return _dump(view)
            view = _view(conn, storage.get_mission(conn, business["id"], name) or saved)
            reused = {item["id"]: bool(item.get("reused")) for item in found}
            for signal in view["signals"]:
                if signal["id"] in reused:
                    signal["reused"] = reused[signal["id"]]
            return _dump(view)
        return _dump(_view(conn, storage.get_mission(conn, business["id"], name) or saved))


def _view(conn, mission_row: dict[str, Any]) -> dict[str, Any]:
    dna = storage.list_dna(conn, mission_row["id"])
    signals = storage.list_signals(conn, mission_row["id"])
    cards = [graph.card_for(item) for item in signals]
    return {
        "ok": True,
        "mission_id": mission_row["id"],
        "name": mission_row.get("name") or "",
        "reused": bool(mission_row.get("reused")),
        "dna": [
            {"offer": item["offer"], "segment": item["segment"], "quote": item["quote"], "source_url": item["source_url"], "confidence": item["confidence"]}
            for item in dna
        ],
        "signals": [
            {"id": item["id"], "company": item["company"], "observed_on": item["observed_on"], "offer_fit": item["offer_fit"], "intent": item["intent"], "reused": bool(item.get("reused"))}
            for item in signals
        ],
        "cards": cards,
        "invented": False,
        "sent": False,
        "sending_enabled": False,
        "auto_send": False,
    }
