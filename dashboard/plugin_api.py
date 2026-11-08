"""Routes for the desktop plugin. There is no send endpoint: email leaves only via /salespilot-send."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Query, Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import views
import setup

router = APIRouter()


@router.get("/overview")
def overview(business_id: str = Query(default="")) -> dict:
    return views.overview(business_id)


@router.get("/radar")
def radar(business_id: str = Query(default=""), mission_id: str = Query(default="")) -> dict:
    return views.radar(business_id, mission_id)


@router.get("/outreach")
def outreach(business_id: str = Query(default="")) -> dict:
    return views.outreach(business_id)


@router.get("/timeline")
def timeline(lead_id: str = Query(...), business_id: str = Query(default=""),
             limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return views.customer_timeline(lead_id, business_id, limit)


@router.get("/review")
def review_queue(business_id: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200)) -> dict:
    import storage
    with storage.read_only() as conn:
        business = storage.get_business(conn, business_id) if business_id else storage.get_business(conn)
        if business is None:
            return {"ok": True, "items": [], "count": 0, "sent": False}
        items = storage.list_review(conn, business["id"], limit)
    return {"ok": True, "items": items, "count": len(items), "sent": False}


@router.post("/policy")
async def save_policy(request: Request) -> dict:
    import followstate
    import storage
    body = await request.json()
    with storage.unit_of_work() as conn:
        business = storage.get_business(conn, str(body.get("business_id") or "")) if body.get("business_id") else storage.get_business(conn)
        if business is None:
            return {"ok": False, "code": "missing_business", "sent": False}
        policy = followstate.set_policy(
            conn, business["id"],
            int(body.get("days") or 3), int(body.get("max_attempts") or 3), int(body.get("cold_days") or 21),
        )
    return {"ok": True, "policy": policy, "sent": False}


@router.post("/imap")
async def save_imap(request: Request) -> dict:
    import re
    import storage
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False}
    leaked = [key for key in body if re.search(r"pass|secret|token|credential", str(key), re.I)]
    if leaked:
        return {"ok": False, "code": "secret_in_body",
                "error": "Mailbox passwords belong in Hermes secrets, not this endpoint.",
                "rejected_fields": leaked, "sent": False}
    host = str(body.get("host") or "").strip()
    if host and ("://" in host or "@" in host or " " in host):
        return {"ok": False, "code": "bad_host", "error": "Host must be a bare hostname.", "sent": False}
    with storage.unit_of_work() as conn:
        business = storage.get_business(conn, str(body.get("business_id") or "")) if body.get("business_id") else storage.get_business(conn)
        if business is None:
            return {"ok": False, "code": "missing_business", "sent": False}
        saved = storage.save_imap_settings(conn, business["id"], body)
    return {"ok": True, "imap": {"host": saved["host"], "port": saved["port"], "username": saved["username"]}, "sent": False}


@router.get("/accounts")
def accounts_view(business_id: str = Query(default="")) -> dict:
    import accounts
    import storage
    with storage.read_only() as conn:
        business = storage.get_business(conn, business_id) if business_id else storage.get_business(conn)
        if business is None:
            return {"ok": True, "accounts": [], "capacity": {}, "sent": False}
        rows = accounts.list_accounts(conn, business["id"])
        capacity = accounts.credential_capacity(conn, business["id"])
    return {"ok": True, "accounts": rows, "capacity": capacity, "sent": False}


@router.get("/hot")
def hot_view(business_id: str = Query(default=""), limit: int = Query(default=50, ge=1, le=200)) -> dict:
    return views.hot_prospects(business_id, limit)


@router.get("/dna")
def dna(business_id: str = Query(default="")) -> dict:
    return views.dna(business_id)


@router.get("/pipeline")
def pipeline_list(
    business_id: str = Query(default=""),
    query: str = Query(default=""),
    status: str = Query(default=""),
    sort: str = Query(default="updated"),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return views.pipeline_view(business_id, query, status, sort, include_archived, limit, offset)


@router.get("/brands")
def brands_view() -> dict:
    return views.brands()


@router.post("/brands")
async def brands_change(request: Request) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False}
    return views.switch_brand(body)


@router.get("/setup")
def setup_status() -> dict:
    return setup.status()


@router.post("/setup")
async def setup_save(request: Request) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False}
    if body.get("action") == "discover":
        return setup.discover(body)
    return setup.save(body)


@router.get("/customers")
def imported_customers(business_id: str = Query(default=""), limit: int = Query(default=500, ge=1, le=2000)) -> dict:
    import desk_actions
    return desk_actions.customers(business_id, limit)


async def _json_body(request: Request):
    try:
        return await request.json()
    except Exception:
        return None


@router.post("/import")
async def import_csv(request: Request) -> dict:
    import desk_actions
    return desk_actions.import_csv(await _json_body(request))


@router.post("/qualify")
async def qualify(request: Request) -> dict:
    import desk_actions
    return desk_actions.qualify(await _json_body(request))


@router.post("/draft")
async def draft(request: Request) -> dict:
    """Builds an email draft only. The send path is still /salespilot-send with a host prompt."""
    import desk_actions
    return desk_actions.draft(await _json_body(request))


@router.post("/inbox")
async def inbox_route(request: Request) -> dict:
    import desk_actions
    return desk_actions.inbox_action(await _json_body(request))


@router.post("/pipeline")
async def pipeline_change(request: Request) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "code": "bad_body", "sent": False}
    return views.pipeline_change(body)
