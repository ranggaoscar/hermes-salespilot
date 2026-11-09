"""SQLite state under the Hermes plugin data dir. Never writes into the install tree."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any

try:
    from . import domain
except ImportError:  # unittest loads this file as a top-level module
    import domain

PLUGIN_NAME = "hermes-salespilot"
_LOCK = threading.RLock()  # reentrant: a view may open a read connection inside another view
_DATA_DIR: Path | None = None


def set_data_dir(path: Path | None) -> None:
    """Tests inject a temp directory. Production uses plugin_data_dir."""
    global _DATA_DIR
    _DATA_DIR = path


def resolve_data_dir() -> Path:
    if _DATA_DIR is not None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        return _DATA_DIR
    from plugins.plugin_storage import plugin_data_dir

    return plugin_data_dir(PLUGIN_NAME)


def _connect(*, migrate: bool = False) -> sqlite3.Connection:
    path = resolve_data_dir() / "salespilot.db"
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    if migrate:
        migrate_schema(conn)
    return conn


def _exec_sql(conn: sqlite3.Connection, script: str) -> None:
    pending = ""
    for line in script.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            conn.execute(pending)
            pending = ""
    if pending.strip():
        conn.execute(pending)


def schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    except sqlite3.OperationalError:
        return 0
    if row is None:
        return 0
    try:
        return int(row["value"])
    except (TypeError, ValueError):
        return 0


def schema_ready(conn: sqlite3.Connection) -> bool:
    if schema_version(conn) < domain.SCHEMA_VERSION:
        return False
    try:
        present = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        brands = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brands'").fetchone()
    except sqlite3.OperationalError:
        return False
    accounts = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
    messages = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'").fetchone()
    if brands is None or accounts is None or messages is None:
        return False
    return {"pipeline_status", "owner_note", "archived", "deleted_at", "email_key"}.issubset(present)


def migrate_schema(conn: sqlite3.Connection) -> bool:
    """Apply pending DDL once. A current database is not written."""
    if schema_ready(conn):
        return False
    conn.execute("BEGIN IMMEDIATE")
    try:
        _migrate(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def _migrate(conn: sqlite3.Connection) -> None:
    _exec_sql(conn,
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_key TEXT NOT NULL,
            offer TEXT NOT NULL,
            offer_short TEXT NOT NULL,
            default_cta TEXT NOT NULL,
            icp_json TEXT NOT NULL,
            channels_json TEXT NOT NULL,
            constraints_json TEXT NOT NULL,
            currency TEXT NOT NULL,
            locale TEXT NOT NULL,
            default_country TEXT NOT NULL,
            followup_days INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            company TEXT NOT NULL,
            company_key TEXT NOT NULL,
            contact_name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            email_key TEXT NOT NULL DEFAULT '',
            email_valid INTEGER NOT NULL DEFAULT 0,
            phone TEXT NOT NULL DEFAULT '',
            phone_key TEXT NOT NULL DEFAULT '',
            phone_valid INTEGER NOT NULL DEFAULT 0,
            segment TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            synthetic INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            company TEXT NOT NULL,
            company_key TEXT NOT NULL,
            contact_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            email_valid INTEGER NOT NULL DEFAULT 0,
            phone TEXT NOT NULL DEFAULT '',
            phone_key TEXT NOT NULL DEFAULT '',
            phone_valid INTEGER NOT NULL DEFAULT 0,
            segment TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            evidence TEXT NOT NULL,
            unknowns_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            decision TEXT NOT NULL,
            reasons_json TEXT NOT NULL,
            gates_json TEXT NOT NULL,
            stage TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS opportunities (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            lead_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            verified_json TEXT NOT NULL,
            assumptions_json TEXT NOT NULL,
            unknowns_json TEXT NOT NULL,
            fit TEXT NOT NULL,
            next_question TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            lead_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            cta TEXT NOT NULL,
            recipient TEXT NOT NULL DEFAULT '',
            idempotency_key TEXT NOT NULL,
            template_version TEXT NOT NULL,
            status TEXT NOT NULL,
            send_blocked INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            UNIQUE(business_id, idempotency_key)
        );
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            draft_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            status TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(business_id, idempotency_key)
        );
        CREATE TABLE IF NOT EXISTS followups (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            lead_id TEXT NOT NULL,
            draft_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            reason TEXT NOT NULL,
            due_on TEXT NOT NULL,
            status TEXT NOT NULL,
            send_recommended INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            ref_id TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            url TEXT NOT NULL,
            kind TEXT NOT NULL,
            permitted INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_batches (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source_label TEXT NOT NULL,
            authorized INTEGER NOT NULL,
            authorization_note TEXT NOT NULL,
            mapping_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _add_columns(conn)
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(domain.SCHEMA_VERSION),),
    )
    _exec_sql(conn,
        """
        CREATE TABLE IF NOT EXISTS mail_settings (
            business_id TEXT PRIMARY KEY,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            security TEXT NOT NULL,
            from_address TEXT NOT NULL,
            from_name TEXT NOT NULL DEFAULT '',
            position TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            contact TEXT NOT NULL DEFAULT '',
            signature_text TEXT NOT NULL DEFAULT '',
            signature_html TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS suppressions (
            business_id TEXT NOT NULL,
            email_key TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (business_id, email_key)
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            draft_id TEXT NOT NULL,
            lead_id TEXT NOT NULL,
            revision TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            state TEXT NOT NULL,
            smtp_code INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (business_id, draft_id, revision, recipient)
        );
        CREATE TABLE IF NOT EXISTS missions (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            name_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (business_id, name_key)
        );
        CREATE TABLE IF NOT EXISTS dna_claims (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            mission_id TEXT NOT NULL,
            claim TEXT NOT NULL,
            offer TEXT NOT NULL,
            segment TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL,
            quote TEXT NOT NULL,
            confidence TEXT NOT NULL,
            dedupe_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (mission_id, dedupe_key)
        );
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            mission_id TEXT NOT NULL,
            company TEXT NOT NULL,
            company_key TEXT NOT NULL,
            signal TEXT NOT NULL,
            observed_on TEXT NOT NULL,
            source_url TEXT NOT NULL,
            quote TEXT NOT NULL,
            offer TEXT NOT NULL DEFAULT '',
            segment TEXT NOT NULL DEFAULT '',
            offer_fit TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            intent TEXT NOT NULL,
            confidence TEXT NOT NULL,
            dedupe_key TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (mission_id, dedupe_key)
        );
        CREATE TABLE IF NOT EXISTS brands (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            name_key TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_brands_name ON brands(name_key);
        CREATE INDEX IF NOT EXISTS idx_leads_brand_updated ON leads(business_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_leads_brand_status ON leads(business_id, pipeline_status);
        CREATE INDEX IF NOT EXISTS idx_leads_brand_company ON leads(business_id, company_key);
        CREATE INDEX IF NOT EXISTS idx_customers_brand_company ON customers(business_id, company_key);
        CREATE INDEX IF NOT EXISTS idx_customers_brand_email ON customers(business_id, email_key);
        CREATE INDEX IF NOT EXISTS idx_events_brand_created ON events(business_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_deliveries_brand_created ON deliveries(business_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'email',
            address TEXT NOT NULL,
            address_key TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            credential_slot TEXT NOT NULL DEFAULT 'default',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_brand_address ON accounts(business_id, address_key);
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT NOT NULL DEFAULT '',
            lead_id TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL DEFAULT 'email',
            direction TEXT NOT NULL,
            message_id TEXT NOT NULL DEFAULT '',
            in_reply_to TEXT NOT NULL DEFAULT '',
            references_json TEXT NOT NULL DEFAULT '[]',
            subject TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            recipient TEXT NOT NULL DEFAULT '',
            sent_at TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL DEFAULT '',
            delivery_state TEXT NOT NULL DEFAULT 'unknown',
            evidence_level TEXT NOT NULL DEFAULT 'imported',
            intent TEXT NOT NULL DEFAULT '',
            body_excerpt TEXT NOT NULL DEFAULT '',
            body_sha256 TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_brand_lead ON messages(business_id, lead_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(business_id, message_id);
        CREATE INDEX IF NOT EXISTS idx_messages_inreply ON messages(business_id, in_reply_to);
        CREATE TABLE IF NOT EXISTS mailbox_cursors (
            business_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            uidvalidity TEXT NOT NULL DEFAULT '',
            last_uid INTEGER NOT NULL DEFAULT 0,
            last_sync_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (business_id, account_id)
        );
        CREATE TABLE IF NOT EXISTS inbox_review (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_review_brand ON inbox_review(business_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS imap_settings (
            business_id TEXT PRIMARY KEY,
            host TEXT NOT NULL DEFAULT '',
            port INTEGER NOT NULL DEFAULT 993,
            username TEXT NOT NULL DEFAULT '',
            use_ssl INTEGER NOT NULL DEFAULT 1,
            last_sync_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        """
    )
    _backfill_brands(conn)


def _brand_slug(name: str, taken: set[str]) -> str:
    base = domain.company_key(name).replace(" ", "-") or "brand"
    slug = base
    suffix = 2
    while slug in taken:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _backfill_brands(conn: sqlite3.Connection) -> None:
    """One brand per business, id == business id. Idempotent; never rewrites a live brand row."""
    now = domain.iso()
    known = {row["business_id"] for row in conn.execute("SELECT business_id FROM brands")}
    taken = {row["slug"] for row in conn.execute("SELECT slug FROM brands")}
    rows = conn.execute("SELECT id, name, created_at FROM businesses ORDER BY created_at").fetchall()
    active = None
    for row in rows:
        if row["id"] in known:
            continue
        slug = _brand_slug(row["name"], taken)
        taken.add(slug)
        conn.execute(
            "INSERT INTO brands(id, business_id, slug, display_name, name_key, is_default, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (row["id"], row["id"], slug, row["name"], domain.company_key(row["name"]), 0, row["created_at"] or now, now),
        )
        active = active or row["id"]
    if conn.execute("SELECT COUNT(*) FROM brands WHERE is_default=1").fetchone()[0] == 0:
        first = conn.execute("SELECT id FROM brands ORDER BY created_at LIMIT 1").fetchone()
        if first is not None:
            conn.execute("UPDATE brands SET is_default=1 WHERE id=?", (first["id"],))
            conn.execute(
                "INSERT INTO meta(key, value) VALUES('active_brand', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (first["id"],),
            )


def _add_columns(conn: sqlite3.Connection) -> None:
    additions = {
        "businesses": {
            "profile_json": "TEXT NOT NULL DEFAULT '{}'",
            "citations_json": "TEXT NOT NULL DEFAULT '[]'",
            "followup_max_attempts": "INTEGER NOT NULL DEFAULT 3",
            "followup_cold_days": "INTEGER NOT NULL DEFAULT 21",
        },
        "customers": {
            "batch_id": "TEXT NOT NULL DEFAULT ''",
            "row_number": "INTEGER NOT NULL DEFAULT 0",
            "provenance_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "leads": {
            "confidence": "INTEGER NOT NULL DEFAULT 0",
            "citations_json": "TEXT NOT NULL DEFAULT '[]'",
            "confidence_json": "TEXT NOT NULL DEFAULT '{}'",
            "pipeline_status": "TEXT NOT NULL DEFAULT 'new'",
            "owner_note": "TEXT NOT NULL DEFAULT ''",
            "archived": "INTEGER NOT NULL DEFAULT 0",
            "deleted_at": "TEXT NOT NULL DEFAULT ''",
            "email_key": "TEXT NOT NULL DEFAULT ''",
            "contacted_at": "TEXT NOT NULL DEFAULT ''",
            "replied_at": "TEXT NOT NULL DEFAULT ''",
            "last_inbound_excerpt": "TEXT NOT NULL DEFAULT ''",
            "needs_human": "INTEGER NOT NULL DEFAULT 0",
            "account_id": "TEXT NOT NULL DEFAULT ''",
        },
        "opportunities": {
            "confidence": "INTEGER NOT NULL DEFAULT 0",
            "citations_json": "TEXT NOT NULL DEFAULT '[]'",
            "grounded": "INTEGER NOT NULL DEFAULT 0",
        },
        "approvals": {
            "lead_id": "TEXT NOT NULL DEFAULT ''",
            "scope_json": "TEXT NOT NULL DEFAULT '{}'",
        },
        "followups": {
            "scheduled_for": "TEXT NOT NULL DEFAULT ''",
        },
    }
    for table, columns in additions.items():
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _business_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    item = _row(row)
    if item is None:
        return None
    item["icp"] = _loads(item.pop("icp_json"), {})
    item["channels"] = _loads(item.pop("channels_json"), [])
    item["constraints"] = _loads(item.pop("constraints_json"), [])
    item["profile"] = _loads(item.pop("profile_json", None), {})
    item["citations"] = _loads(item.pop("citations_json", None), [])
    return item


def _lead_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    item = _row(row)
    if item is None:
        return None
    item["unknowns"] = _loads(item.pop("unknowns_json"), [])
    item["reasons"] = _loads(item.pop("reasons_json"), [])
    item["gates"] = _loads(item.pop("gates_json"), {})
    item["citations"] = _loads(item.pop("citations_json", None), [])
    item["confidence_detail"] = _loads(item.pop("confidence_json", None), {})
    item["email_valid"] = bool(item.get("email_valid"))
    item["phone_valid"] = bool(item.get("phone_valid"))
    return item


def add_event(conn: sqlite3.Connection, kind: str, business_id: str = "", ref_id: str = "", payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO events(id, business_id, kind, ref_id, payload_json, created_at) VALUES(?,?,?,?,?,?)",
        (domain.new_id("evt"), business_id, kind, ref_id, json.dumps(payload or {}, ensure_ascii=False), domain.iso()),
    )


def active_business_id(conn: sqlite3.Connection) -> str:
    """The active brand decides the active business; the meta row is only a fallback."""
    row = conn.execute("SELECT business_id FROM brands WHERE is_default=1 LIMIT 1").fetchone()
    if row is not None:
        return str(row["business_id"])
    row = conn.execute("SELECT value FROM meta WHERE key='active_business'").fetchone()
    return "" if row is None else str(row["value"])


def get_business(conn: sqlite3.Connection, business_id: str = "") -> dict[str, Any] | None:
    bid = business_id or active_business_id(conn)
    if not bid:
        return None
    return _business_from_row(conn.execute("SELECT * FROM businesses WHERE id=?", (bid,)).fetchone())


# --- brands -----------------------------------------------------------------------------------
# A brand IS its business row: brands.business_id is UNIQUE, so brand id == business id and every
# existing table already carries that key. No second tenant column exists, so nothing can drift.


def list_brands(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM brands ORDER BY is_default DESC, display_name").fetchall()
    return [dict(row) for row in rows]


def get_brand(conn: sqlite3.Connection, brand_id: str = "") -> dict[str, Any] | None:
    if not brand_id:
        return active_brand(conn)
    row = conn.execute("SELECT * FROM brands WHERE id=?", (brand_id,)).fetchone()
    return None if row is None else dict(row)


def active_brand(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM brands WHERE is_default=1 LIMIT 1").fetchone()
    if row is not None:
        return dict(row)
    row = conn.execute("SELECT * FROM brands ORDER BY created_at LIMIT 1").fetchone()
    return None if row is None else dict(row)


def resolve_brand(conn: sqlite3.Connection, ref: str = "") -> tuple[dict[str, Any] | None, str]:
    """Resolve an explicit brand reference (id, slug, or name) or fall back to the active brand.

    Returns ``(brand, reason)``; ``reason`` names the failure so callers can fail closed instead of
    guessing when a name is ambiguous.
    """
    text = str(ref or "").strip()
    if not text:
        brand = active_brand(conn)
        return (brand, "" if brand else "no_active_brand")
    row = conn.execute("SELECT * FROM brands WHERE id=? OR slug=?", (text, text.lower())).fetchone()
    if row is not None:
        return dict(row), ""
    key = domain.company_key(text)
    rows = conn.execute("SELECT * FROM brands WHERE name_key=?", (key,)).fetchall()
    if len(rows) == 1:
        return dict(rows[0]), ""
    if len(rows) > 1:
        return None, "ambiguous_brand"
    return None, "unknown_brand"


def set_active_brand(conn: sqlite3.Connection, brand_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM brands WHERE id=?", (brand_id,)).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE brands SET is_default=0 WHERE is_default=1")
    conn.execute("UPDATE brands SET is_default=1, updated_at=? WHERE id=?", (domain.iso(), brand_id))
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('active_brand', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (brand_id,),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('active_business', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (brand_id,),
    )
    return get_brand(conn, brand_id)


def ensure_brand(conn: sqlite3.Connection, business_id: str, name: str) -> dict[str, Any]:
    """Create the brand row for a business that has none. Idempotent."""
    existing = conn.execute("SELECT * FROM brands WHERE business_id=?", (business_id,)).fetchone()
    if existing is not None:
        if name and existing["display_name"] != name:
            conn.execute(
                "UPDATE brands SET display_name=?, name_key=?, updated_at=? WHERE id=?",
                (name, domain.company_key(name), domain.iso(), existing["id"]),
            )
            existing = conn.execute("SELECT * FROM brands WHERE business_id=?", (business_id,)).fetchone()
        return dict(existing)
    taken = {row["slug"] for row in conn.execute("SELECT slug FROM brands")}
    now = domain.iso()
    conn.execute(
        "INSERT INTO brands(id, business_id, slug, display_name, name_key, is_default, created_at, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (business_id, business_id, _brand_slug(name, taken), name, domain.company_key(name), 0, now, now),
    )
    return dict(conn.execute("SELECT * FROM brands WHERE business_id=?", (business_id,)).fetchone())


def save_business(conn: sqlite3.Connection, profile: dict[str, Any]) -> dict[str, Any]:
    now = domain.iso()
    name_key = domain.company_key(profile["name"])
    existing = conn.execute(
        "SELECT * FROM businesses WHERE name_key=? ORDER BY updated_at DESC LIMIT 1",
        (name_key,),
    ).fetchone()
    if existing:
        bid = existing["id"]
        created = existing["created_at"]
    else:
        bid = domain.new_id("biz")
        created = now
    conn.execute(
        """
        INSERT INTO businesses(
            id, name, name_key, offer, offer_short, default_cta, icp_json, channels_json,
            constraints_json, currency, locale, default_country, followup_days, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, name_key=excluded.name_key, offer=excluded.offer,
            offer_short=excluded.offer_short, default_cta=excluded.default_cta,
            icp_json=excluded.icp_json, channels_json=excluded.channels_json,
            constraints_json=excluded.constraints_json, currency=excluded.currency,
            locale=excluded.locale, default_country=excluded.default_country,
            followup_days=excluded.followup_days, updated_at=excluded.updated_at
        """,
        (
            bid,
            profile["name"].strip(),
            name_key,
            profile["offer"].strip(),
            profile["offer_short"].strip(),
            profile["default_cta"].strip(),
            json.dumps(profile.get("icp") or {}, ensure_ascii=False),
            json.dumps(profile.get("channels") or [], ensure_ascii=False),
            json.dumps(profile.get("constraints") or [], ensure_ascii=False),
            profile.get("currency") or "USD",
            profile.get("locale") or "en",
            (profile.get("default_country") or "").upper(),
            int(profile.get("followup_days") or 3),
            created,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES('active_business', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (bid,),
    )
    add_event(conn, "business_saved", bid, bid, {"name": profile["name"]})
    conn.execute(
        "UPDATE businesses SET profile_json=?, citations_json=? WHERE id=?",
        (
            json.dumps(profile.get("profile") or {}, ensure_ascii=False),
            json.dumps(profile.get("citations") or [], ensure_ascii=False),
            bid,
        ),
    )
    saved = get_business(conn, bid)
    assert saved is not None
    ensure_brand(conn, bid, saved["name"])
    return saved


def find_customer_duplicate(conn: sqlite3.Connection, business_id: str, record: dict[str, Any]) -> str:
    company = domain.company_key(record.get("company"))
    email = record.get("email_key") or ""
    phone = record.get("phone_key") or ""
    row = conn.execute(
        """
        SELECT id FROM customers
        WHERE business_id=? AND (
            company_key=?
            OR (? != '' AND email_key=?)
            OR (? != '' AND phone_key=?)
        )
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (business_id, company, email, email, phone, phone),
    ).fetchone()
    return "" if row is None else str(row["id"])


def insert_customer(conn: sqlite3.Connection, business_id: str, record: dict[str, Any]) -> str:
    cid = domain.new_id("cus")
    conn.execute(
        """
        INSERT INTO customers(
            id, business_id, company, company_key, contact_name, email, email_key, email_valid,
            phone, phone_key, phone_valid, segment, source, notes, synthetic, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            cid,
            business_id,
            record["company"],
            record["company_key"],
            record.get("contact_name") or "",
            record.get("email") or "",
            record.get("email_key") or "",
            1 if record.get("email_valid") else 0,
            record.get("phone") or "",
            record.get("phone_key") or "",
            1 if record.get("phone_valid") else 0,
            record.get("segment") or "",
            record.get("source") or "unspecified",
            record.get("notes") or "",
            1 if record.get("synthetic", True) else 0,
            domain.iso(),
        ),
    )
    add_event(conn, "customer_imported", business_id, cid, {
        "company": record["company"],
        "row_number": record.get("row_number") or 0,
        "batch_id": record.get("batch_id") or "",
    })
    conn.execute(
        "UPDATE customers SET batch_id=?, row_number=?, provenance_json=? WHERE id=?",
        (
            record.get("batch_id") or "",
            int(record.get("row_number") or 0),
            json.dumps(record.get("provenance") or {}, ensure_ascii=False),
            cid,
        ),
    )
    return cid


def save_lead(conn: sqlite3.Connection, business_id: str, lead: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    now = domain.iso()
    key = domain.company_key(lead.get("company"))
    email_identity = domain.normalize_email(lead.get("email"))["value"]
    # One row per mailbox, not per company: a hotel may have a reservation desk *and* a fleet manager.
    if email_identity:
        existing = conn.execute(
            "SELECT * FROM leads WHERE business_id=? AND email_key=?",
            (business_id, email_identity),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT * FROM leads WHERE business_id=? AND company_key=? AND email_key=''",
            (business_id, key),
        ).fetchone()
    if existing:
        lid = existing["id"]
        created = existing["created_at"]
    else:
        lid = domain.new_id("led")
        created = now
    phone = result["phone"]
    email = result["email"]
    stage = result.get("stage") or {
        "qualified": "qualified", "hold": "discovered", "reject": "rejected"
    }.get(result["decision"], "discovered")
    conn.execute(
        """
        INSERT INTO leads(
            id, business_id, company, company_key, contact_name, role, email, email_valid,
            email_key, phone, phone_key, phone_valid, segment, country, source_url, evidence,
            unknowns_json, score, decision, reasons_json, gates_json, stage, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            company=excluded.company, contact_name=excluded.contact_name, role=excluded.role,
            email=excluded.email, email_valid=excluded.email_valid, email_key=excluded.email_key,
            phone=excluded.phone,
            phone_key=excluded.phone_key, phone_valid=excluded.phone_valid, segment=excluded.segment,
            country=excluded.country, source_url=excluded.source_url, evidence=excluded.evidence,
            unknowns_json=excluded.unknowns_json, score=excluded.score, decision=excluded.decision,
            reasons_json=excluded.reasons_json, gates_json=excluded.gates_json, stage=excluded.stage,
            updated_at=excluded.updated_at
        """,
        (
            lid,
            business_id,
            str(lead.get("company") or "").strip(),
            key,
            str(lead.get("contact_name") or "").strip(),
            str(lead.get("role") or "").strip(),
            email["value"],
            1 if email["valid"] else 0,
            email["value"],
            phone["digits"],
            phone["digits"],
            1 if phone["valid"] else 0,
            str(lead.get("segment") or "").strip(),
            str(lead.get("country") or "").strip(),
            str(lead.get("source_url") or "").strip(),
            str(lead.get("evidence") or "").strip(),
            json.dumps(result["unknowns"], ensure_ascii=False),
            int(result["score"]),
            result["decision"],
            json.dumps(result["reasons"], ensure_ascii=False),
            json.dumps(result["gates"], ensure_ascii=False),
            stage,
            created,
            now,
        ),
    )
    add_event(conn, "lead_qualified", business_id, lid, {"decision": result["decision"], "score": result["score"]})
    confidence = result.get("confidence") or {}
    conn.execute(
        "UPDATE leads SET confidence=?, citations_json=?, confidence_json=? WHERE id=?",
        (
            int(confidence.get("score") or result.get("confidence_score") or 0),
            json.dumps(result.get("citations") or lead.get("citations") or [], ensure_ascii=False),
            json.dumps(confidence, ensure_ascii=False),
            lid,
        ),
    )
    saved = _lead_from_row(conn.execute("SELECT * FROM leads WHERE id=?", (lid,)).fetchone())
    assert saved is not None
    saved["updated"] = existing is not None
    return saved


def set_pipeline_fields(conn: sqlite3.Connection, lead_id: str, **fields: Any) -> None:
    allowed = {
        "pipeline_status", "owner_note", "archived", "deleted_at", "email_key",
        "contacted_at", "replied_at", "last_inbound_excerpt", "needs_human", "account_id",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown pipeline field: {sorted(unknown)}")
    assignments = ", ".join(f"{name}=?" for name in fields)
    conn.execute(
        f"UPDATE leads SET {assignments}, updated_at=? WHERE id=?",
        (*fields.values(), domain.iso(), lead_id),
    )


def get_lead(conn: sqlite3.Connection, lead_id: str) -> dict[str, Any] | None:
    return _lead_from_row(conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())


def list_leads(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM leads WHERE business_id=? ORDER BY updated_at DESC",
        (business_id,),
    ).fetchall()
    return [item for item in (_lead_from_row(row) for row in rows) if item]


def list_leads_page(
    conn: sqlite3.Connection,
    business_id: str,
    *,
    query: str = "",
    status: str = "",
    sort: str = "updated",
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """One page of prospects, filtered and counted in SQLite. Never loads the whole table."""
    where = ["business_id=?"]
    params: list[Any] = [business_id]
    if status == "archived":
        where.append("archived=1")
    elif status == "deleted":
        where.append("deleted_at != ''")
    else:
        where.append("deleted_at = ''")
        if not include_archived:
            where.append("archived=0")
        if status:
            where.append("pipeline_status=?")
            params.append(status)
    needle = query.strip().lower()
    if needle:
        where.append(
            "(lower(company) LIKE ? OR lower(email) LIKE ? OR lower(evidence) LIKE ? OR lower(owner_note) LIKE ?)"
        )
        blob = f"%{needle}%"
        params.extend([blob, blob, blob, blob])
    clause = " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM leads WHERE {clause}", params).fetchone()[0]
    order = {"company": "lower(company) ASC", "status": "pipeline_status ASC"}.get(sort, "updated_at DESC")
    rows = conn.execute(
        f"SELECT * FROM leads WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, max(1, min(int(limit), 500)), max(0, int(offset))],
    ).fetchall()
    return [item for item in (_lead_from_row(row) for row in rows) if item], int(total)


def save_opportunity(conn: sqlite3.Connection, business_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    oid = domain.new_id("opp")
    now = domain.iso()
    conn.execute(
        """
        INSERT INTO opportunities(
            id, business_id, lead_id, title, verified_json, assumptions_json, unknowns_json,
            fit, next_question, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        (
            oid,
            business_id,
            payload.get("lead_id") or "",
            payload["title"],
            json.dumps(payload.get("verified") or [], ensure_ascii=False),
            json.dumps(payload.get("assumptions") or [], ensure_ascii=False),
            json.dumps(payload.get("unknowns") or [], ensure_ascii=False),
            payload.get("fit") or "unknown",
            payload.get("next_question") or "",
            now,
        ),
    )
    add_event(conn, "opportunity_recorded", business_id, oid, {"title": payload["title"], "grounded": bool(payload.get("grounded"))})
    conn.execute(
        "UPDATE opportunities SET confidence=?, citations_json=?, grounded=? WHERE id=?",
        (
            int((payload.get("confidence") or {}).get("score") or 0),
            json.dumps(payload.get("citations") or [], ensure_ascii=False),
            1 if payload.get("grounded") else 0,
            oid,
        ),
    )
    return {"id": oid, "created_at": now, **payload, "fetched": False}


def save_draft(conn: sqlite3.Connection, business_id: str, draft: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    existing = conn.execute(
        "SELECT * FROM drafts WHERE business_id=? AND idempotency_key=?",
        (business_id, draft["idempotency_key"]),
    ).fetchone()
    if existing:
        item = dict(existing)
        item["send_blocked"] = True
        item["sent"] = False
        item["reused"] = True
        return item, True
    did = domain.new_id("dft")
    now = domain.iso()
    conn.execute(
        """
        INSERT INTO drafts(
            id, business_id, lead_id, channel, subject, body, cta, recipient,
            idempotency_key, template_version, status, send_blocked, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            did,
            business_id,
            draft["lead_id"],
            draft["channel"],
            draft.get("subject") or "",
            draft["body"],
            draft["cta"],
            draft.get("recipient") or "",
            draft["idempotency_key"],
            draft["template_version"],
            "draft",
            1,
            now,
        ),
    )
    add_event(conn, "draft_created", business_id, did, {"channel": draft["channel"], "sent": False})
    item = dict(conn.execute("SELECT * FROM drafts WHERE id=?", (did,)).fetchone())
    item["sent"] = False
    item["reused"] = False
    item["send_blocked"] = True
    return item, False


def get_draft(conn: sqlite3.Connection, draft_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    return None if row is None else dict(row)


def list_drafts(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM drafts WHERE business_id=? ORDER BY created_at DESC",
        (business_id,),
    ).fetchall()]


def get_approval_for_draft(conn: sqlite3.Connection, draft_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM approvals WHERE draft_id=? ORDER BY updated_at DESC LIMIT 1",
        (draft_id,),
    ).fetchone()
    return None if row is None else dict(row)


def save_approval(
    conn: sqlite3.Connection,
    business_id: str,
    draft_id: str,
    status: str,
    actor: str,
    note: str,
    lead_id: str = "",
    scope: dict | None = None,
) -> dict[str, Any]:
    key = domain.idempotency_key("approval", business_id, draft_id)
    now = domain.iso()
    existing = conn.execute(
        "SELECT * FROM approvals WHERE business_id=? AND idempotency_key=?",
        (business_id, key),
    ).fetchone()
    if existing and existing["status"] == status:
        item = dict(existing)
        item["reused"] = True
        item["sent"] = False
        return item
    if existing:
        conn.execute(
            "UPDATE approvals SET status=?, actor=?, note=?, updated_at=? WHERE id=?",
            (status, actor, note, now, existing["id"]),
        )
        aid = existing["id"]
    else:
        aid = domain.new_id("apr")
        conn.execute(
            """
            INSERT INTO approvals(
                id, business_id, draft_id, idempotency_key, status, actor, note, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (aid, business_id, draft_id, key, status, actor, note, now, now),
        )
    add_event(conn, "approval_recorded", business_id, aid, {
        "status": status,
        "sent": False,
        "draft_id": draft_id,
        "lead_id": lead_id,
        "actor": actor,
    })
    conn.execute(
        "UPDATE approvals SET lead_id=?, scope_json=? WHERE id=?",
        (lead_id, json.dumps(scope or {}, ensure_ascii=False), aid),
    )
    item = dict(conn.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone())
    item["reused"] = False
    item["sent"] = False
    return item


def list_approvals(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM approvals WHERE business_id=? ORDER BY updated_at DESC",
        (business_id,),
    ).fetchall()]


def replace_followups(conn: sqlite3.Connection, business_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conn.execute(
        "DELETE FROM followups WHERE business_id=? AND status='recommended'",
        (business_id,),
    )
    now = domain.iso()
    saved = []
    for row in rows:
        fid = domain.new_id("fup")
        conn.execute(
            """
            INSERT INTO followups(
                id, business_id, lead_id, draft_id,                action, reason, due_on, status,
                send_recommended, created_at, scheduled_for
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                fid,
                business_id,
                row.get("lead_id") or "",
                row.get("draft_id") or "",
                row["action"],
                row["reason"],
                row["due_on"],
                "recommended",
                0,
                now,
                row.get("scheduled_for") or "",
            ),
        )
        saved.append({"id": fid, **row, "status": "recommended", "send": False})
    add_event(conn, "followups_planned", business_id, business_id, {"count": len(saved)})
    return saved


def list_followups(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM followups WHERE business_id=? ORDER BY due_on ASC",
        (business_id,),
    ).fetchall()]


def list_customers(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM customers WHERE business_id=? ORDER BY created_at DESC",
        (business_id,),
    ).fetchall()]


def snapshot(conn: sqlite3.Connection, business_id: str) -> dict[str, Any]:
    return {
        "business": get_business(conn, business_id),
        "customers": list_customers(conn, business_id),
        "leads": list_leads(conn, business_id),
        "drafts": list_drafts(conn, business_id),
        "approvals": list_approvals(conn, business_id),
        "followups": list_followups(conn, business_id),
    }


def save_sources(conn: sqlite3.Connection, business_id: str, sources: list[dict[str, Any]], kind: str) -> list[str]:
    ids = []
    now = domain.iso()
    for source in sources:
        sid = domain.new_id("src")
        conn.execute(
            "INSERT INTO sources(id, business_id, url, kind, permitted, text, created_at) VALUES(?,?,?,?,?,?,?)",
            (sid, business_id, source.get("url") or "", kind, 1 if source.get("permitted") else 0, source.get("text") or "", now),
        )
        ids.append(sid)
    return ids


def list_source_text(conn: sqlite3.Connection, business_id: str) -> str:
    rows = conn.execute(
        "SELECT text FROM sources WHERE business_id=? ORDER BY created_at ASC, id ASC",
        (business_id,),
    ).fetchall()
    return "\n".join(row["text"] for row in rows)


def save_batch(conn: sqlite3.Connection, business_id: str, source_label: str, note: str, mapping: dict) -> str:
    bid = domain.new_id("bat")
    conn.execute(
        """
        INSERT INTO import_batches(id, business_id, source_label, authorized, authorization_note, mapping_json, created_at)
        VALUES(?,?,?,?,?,?,?)
        """,
        (bid, business_id, source_label, 1, note, json.dumps(mapping, ensure_ascii=False), domain.iso()),
    )
    add_event(conn, "import_batch", business_id, bid, {"source": source_label})
    return bid


def list_events(conn: sqlite3.Connection, business_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM events WHERE business_id=? ORDER BY created_at ASC",
        (business_id,),
    ).fetchall()]


def save_mail_settings(conn: sqlite3.Connection, business_id: str, account: dict[str, Any]) -> None:
    # A raw/legacy write must never inherit the operator's confirmation of a previous host.
    conn.execute("DELETE FROM meta WHERE key=?", (f"smtp_operator_confirmation_v1:{business_id}",))
    now = domain.iso()
    conn.execute(
        """
        INSERT INTO mail_settings(
            business_id, host, port, security, from_address, from_name, position, company,
            contact, signature_text, signature_html, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(business_id) DO UPDATE SET
            host=excluded.host, port=excluded.port, security=excluded.security,
            from_address=excluded.from_address, from_name=excluded.from_name,
            position=excluded.position, company=excluded.company, contact=excluded.contact,
            signature_text=excluded.signature_text, signature_html=excluded.signature_html,
            updated_at=excluded.updated_at
        """,
        (
            business_id, account["host"], account["port"], account["security"], account["from_address"],
            account["from_name"], account["position"], account["company"], account["contact"],
            account["signature_text"], account["signature_html"], now,
        ),
    )


def get_mail_settings(conn: sqlite3.Connection, business_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM mail_settings WHERE business_id=?", (business_id,)).fetchone()
    return dict(row) if row else None


def add_suppression(conn: sqlite3.Connection, business_id: str, email: str, reason: str) -> None:
    conn.execute(
        """
        INSERT INTO suppressions(business_id, email_key, reason, created_at) VALUES(?,?,?,?)
        ON CONFLICT(business_id, email_key) DO UPDATE SET reason=excluded.reason
        """,
        (business_id, email.strip().lower(), reason[:200], domain.iso()),
    )


def suppressed_emails(conn: sqlite3.Connection, business_id: str) -> set[str]:
    """Brand-scoped suppression set, so list views cannot offer a blocked address."""
    rows = conn.execute("SELECT email_key FROM suppressions WHERE business_id=?", (business_id,)).fetchall()
    out: set[str] = set()
    for row in rows:
        out.add(str(row["email_key"] if hasattr(row, "keys") else row[0]).lower())
    return out


def is_suppressed(conn: sqlite3.Connection, business_id: str, email: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM suppressions WHERE business_id=? AND email_key=?",
        (business_id, email.strip().lower()),
    ).fetchone()
    return row is not None


def bounced_recipient(conn: sqlite3.Connection, business_id: str, email: str) -> bool:
    """True when a bounce was recorded for this address, so the send path can fail closed."""
    row = conn.execute(
        "SELECT 1 FROM messages WHERE business_id=? AND direction='outbound' "
        "AND delivery_state='bounced' AND lower(recipient)=? LIMIT 1",
        (business_id, email.strip().lower()),
    ).fetchone()
    return row is not None


def recent_delivery_count(conn: sqlite3.Connection, business_id: str) -> int:
    cutoff = domain.iso(domain.utcnow() - timedelta(days=1))
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM deliveries
        WHERE business_id=? AND state IN ('accepted', 'unknown', 'intent') AND created_at>=?
        """,
        (business_id, cutoff),
    ).fetchone()
    return int(row["n"])


def recent_recipient(conn: sqlite3.Connection, business_id: str, email: str, days: int) -> bool:
    cutoff = domain.iso(domain.utcnow() - timedelta(days=days))
    row = conn.execute(
        """
        SELECT 1 FROM deliveries
        WHERE business_id=? AND lower(recipient)=? AND state='accepted' AND created_at>=?
        """,
        (business_id, email.strip().lower(), cutoff),
    ).fetchone()
    return row is not None


def get_delivery(conn: sqlite3.Connection, business_id: str, draft_id: str, revision: str, recipient: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM deliveries
        WHERE business_id=? AND draft_id=? AND revision=? AND lower(recipient)=?
        """,
        (business_id, draft_id, revision, recipient.strip().lower()),
    ).fetchone()
    return dict(row) if row else None


def begin_delivery(conn: sqlite3.Connection, fields: dict[str, Any]) -> str:
    existing = get_delivery(conn, fields["business_id"], fields["draft_id"], fields["revision"], fields["recipient"])
    now = domain.iso()
    if existing and existing["state"] == "failed":
        conn.execute(
            "UPDATE deliveries SET state='intent', message_id=?, smtp_code=0, updated_at=? WHERE id=?",
            (fields["message_id"], now, existing["id"]),
        )
        return existing["id"]
    delivery_id = domain.new_id("dlv")
    conn.execute(
        """
        INSERT INTO deliveries(
            id, business_id, draft_id, lead_id, revision, recipient, message_id, subject,
            state, smtp_code, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?, 'intent', 0, ?, ?)
        """,
        (
            delivery_id, fields["business_id"], fields["draft_id"], fields["lead_id"], fields["revision"],
            fields["recipient"], fields["message_id"], fields["subject"], now, now,
        ),
    )
    return delivery_id


def finish_delivery(conn: sqlite3.Connection, delivery_id: str, state: str, smtp_code: int) -> None:
    conn.execute(
        "UPDATE deliveries SET state=?, smtp_code=?, updated_at=? WHERE id=?",
        (state, smtp_code, domain.iso(), delivery_id),
    )


def save_mission(conn: sqlite3.Connection, business_id: str, name: str) -> dict[str, Any]:
    key = domain.company_key(name)
    row = conn.execute(
        "SELECT * FROM missions WHERE business_id=? AND name_key=?",
        (business_id, key),
    ).fetchone()
    now = domain.iso()
    if row:
        conn.execute("UPDATE missions SET updated_at=? WHERE id=?", (now, row["id"]))
        saved = dict(row)
        saved["updated_at"] = now
        saved["reused"] = True
        return saved
    mission_id = domain.new_id("msn")
    conn.execute(
        "INSERT INTO missions(id, business_id, name, name_key, created_at, updated_at) VALUES(?,?,?,?,?,?)",
        (mission_id, business_id, name.strip(), key, now, now),
    )
    return {"id": mission_id, "business_id": business_id, "name": name.strip(), "reused": False, "updated_at": now}


def get_mission(conn: sqlite3.Connection, business_id: str, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM missions WHERE business_id=? AND name_key=?",
        (business_id, domain.company_key(name)),
    ).fetchone()
    return dict(row) if row else None


def save_dna_claim(conn: sqlite3.Connection, mission_id: str, business_id: str, claim: dict[str, Any]) -> dict[str, Any]:
    import hashlib
    key = hashlib.sha256(f"{claim['offer']}|{claim['claim']}|{claim['source_url']}".encode()).hexdigest()[:20]
    row = conn.execute(
        "SELECT * FROM dna_claims WHERE mission_id=? AND dedupe_key=?",
        (mission_id, key),
    ).fetchone()
    if row:
        saved = dict(row)
        saved["reused"] = True
        return saved
    item_id = domain.new_id("dna")
    now = domain.iso()
    conn.execute(
        """
        INSERT INTO dna_claims(
            id, business_id, mission_id, claim, offer, segment, source_url, quote,
            confidence, dedupe_key, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            item_id, business_id, mission_id, claim["claim"], claim["offer"], claim.get("segment") or "",
            claim["source_url"], claim["quote"], claim["confidence"], key, now,
        ),
    )
    claim = {**claim, "id": item_id, "reused": False}
    return claim


def list_dna(conn: sqlite3.Connection, mission_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM dna_claims WHERE mission_id=? ORDER BY created_at, id",
        (mission_id,),
    ).fetchall()]


def save_signal(conn: sqlite3.Connection, mission_id: str, business_id: str, signal: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM signals WHERE mission_id=? AND dedupe_key=?",
        (mission_id, signal["dedupe_key"]),
    ).fetchone()
    if row:
        saved = dict(row)
        saved["reused"] = True
        return saved
    item_id = domain.new_id("sig")
    now = domain.iso()
    conn.execute(
        """
        INSERT INTO signals(
            id, business_id, mission_id, company, company_key, signal, observed_on, source_url,
            quote, offer, segment, offer_fit, email, intent, confidence, dedupe_key, created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            item_id, business_id, mission_id, signal["company"], signal["company_key"], signal["signal"],
            signal["observed_on"], signal["source_url"], signal["quote"], signal.get("offer") or "",
            signal.get("segment") or "", signal["offer_fit"], signal.get("email") or "", signal["intent"],
            signal["confidence"], signal["dedupe_key"], now,
        ),
    )
    return {**signal, "id": item_id, "reused": False}


def list_signals(conn: sqlite3.Connection, mission_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM signals WHERE mission_id=? ORDER BY observed_on DESC, id",
        (mission_id,),
    ).fetchall()]


class read_only:
    """A read connection. It does not migrate and cannot write."""

    def __enter__(self) -> sqlite3.Connection:
        _LOCK.acquire()
        self.conn = _connect(migrate=False)
        self.conn.execute("PRAGMA query_only=ON")
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.conn.close()
        finally:
            _LOCK.release()


class unit_of_work:
    def __enter__(self) -> sqlite3.Connection:
        _LOCK.acquire()
        self.conn = _connect(migrate=True)
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            _LOCK.release()


IMAP_COLUMNS = ("business_id", "host", "port", "username", "use_ssl", "last_sync_at", "updated_at")


def _plain_row(row, columns: tuple[str, ...]) -> dict[str, Any]:
    """Row-factory agnostic: works with sqlite3.Row and with a bare connection."""
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return {name: value for name, value in zip(columns, row)}


def get_imap_settings(conn: sqlite3.Connection, business_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT business_id, host, port, username, use_ssl, last_sync_at, updated_at"
                       " FROM imap_settings WHERE business_id=?", (business_id,)).fetchone()
    saved = _plain_row(row, IMAP_COLUMNS)
    return saved or {"business_id": business_id, "host": "", "port": 993, "username": "",
                     "use_ssl": 1, "last_sync_at": "", "updated_at": ""}


def save_imap_settings(conn: sqlite3.Connection, business_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    host = str(fields.get("host") or "").strip()
    port = int(fields.get("port") or 993)
    username = str(fields.get("username") or "").strip()
    use_ssl = 1 if fields.get("use_ssl", True) else 0
    now = domain.iso()
    conn.execute(
        """INSERT INTO imap_settings(business_id, host, port, username, use_ssl, last_sync_at, updated_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(business_id) DO UPDATE SET host=excluded.host, port=excluded.port,
             username=excluded.username, use_ssl=excluded.use_ssl, updated_at=excluded.updated_at""",
        (business_id, host, port, username, use_ssl, "", now),
    )
    return get_imap_settings(conn, business_id)


def mark_imap_sync(conn: sqlite3.Connection, business_id: str) -> None:
    conn.execute(
        "UPDATE imap_settings SET last_sync_at=?, updated_at=? WHERE business_id=?",
        (domain.iso(), domain.iso(), business_id),
    )


def list_messages(conn: sqlite3.Connection, business_id: str, lead_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
    if lead_id:
        rows = conn.execute(
            "SELECT * FROM messages WHERE business_id=? AND lead_id=? ORDER BY created_at DESC LIMIT ?",
            (business_id, lead_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM messages WHERE business_id=? ORDER BY created_at DESC LIMIT ?",
            (business_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_cursor(conn: sqlite3.Connection, business_id: str, account_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT business_id, account_id, uidvalidity, last_uid, last_sync_at"
        " FROM mailbox_cursors WHERE business_id=? AND account_id=?",
        (business_id, account_id),
    ).fetchone()
    saved = _plain_row(row, ("business_id", "account_id", "uidvalidity", "last_uid", "last_sync_at"))
    return saved or {"business_id": business_id, "account_id": account_id,
                     "uidvalidity": "", "last_uid": 0, "last_sync_at": ""}


def save_cursor(conn: sqlite3.Connection, business_id: str, account_id: str, uidvalidity: str, last_uid: int) -> None:
    now = domain.iso()
    conn.execute(
        """INSERT INTO mailbox_cursors(business_id, account_id, uidvalidity, last_uid, last_sync_at, updated_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(business_id, account_id) DO UPDATE SET uidvalidity=excluded.uidvalidity,
             last_uid=excluded.last_uid, last_sync_at=excluded.last_sync_at, updated_at=excluded.updated_at""",
        (business_id, account_id, str(uidvalidity or ""), int(last_uid or 0), now, now),
    )


def add_review(conn: sqlite3.Connection, business_id: str, reason: str, payload: dict[str, Any], account_id: str = "") -> str:
    message_id = str(payload.get("message_id") or "")
    if message_id:
        existing = conn.execute(
            "SELECT id FROM inbox_review WHERE business_id=? AND message_id=? LIMIT 1",
            (business_id, message_id),
        ).fetchone()
        if existing is not None:
            return str(existing["id"])
    review_id = domain.new_id("rev")
    conn.execute(
        """INSERT INTO inbox_review(id, business_id, account_id, message_id, sender, subject, reason, payload_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (review_id, business_id, account_id, str(payload.get("message_id") or ""),
         str(payload.get("sender") or ""), str(payload.get("subject") or "")[:200], reason,
         json.dumps(payload)[:8000], domain.iso()),
    )
    return review_id


def list_review(conn: sqlite3.Connection, business_id: str, limit: int = 100) -> list[dict[str, Any]]:
    columns = ("id", "business_id", "account_id", "message_id", "sender", "subject", "reason",
               "payload_json", "created_at")
    rows = conn.execute(
        "SELECT id, business_id, account_id, message_id, sender, subject, reason, payload_json, created_at"
        " FROM inbox_review WHERE business_id=? ORDER BY created_at DESC LIMIT ?",
        (business_id, limit),
    ).fetchall()
    return [_plain_row(row, columns) for row in rows]
