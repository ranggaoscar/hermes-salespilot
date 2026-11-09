"""Mail defaults from the plugin's native Hermes settings.

`plugin.yaml` declares ``config_schema``; the Desktop renders it under Settings → Plugins and
writes non-secret values to ``plugins.entries.hermes-salespilot.settings``. The SMTP username and
password are declared ``type: secret`` with an explicit ``env:`` name, so Hermes stores them only
through its credential route and this module reads them with ``agent.secret_scope.get_secret``.
There is no second credential store here: values never enter SQLite, logs or an API response.

Native Settings are authoritative. Only a newly confirmed Desktop wizard account can be used
when native transport settings are empty; legacy SQLite accounts require operator reconfirmation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

PLUGIN_ID = "hermes-salespilot"

_CTX = None


def bind(ctx) -> None:
    """Read settings through the host's public ``ctx.get_config`` surface."""
    global _CTX
    _CTX = ctx


SECRET_USERNAME = "SALESPILOT_SMTP_USERNAME"
SECRET_PASSWORD = "SALESPILOT_SMTP_PASSWORD"
SECRET_NAMES = (SECRET_USERNAME, SECRET_PASSWORD)

DEFAULTS: dict[str, Any] = {
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_security": "starttls",
    "from_address": "",
    "from_name": "",
    "signature_text": "",
}

# config_schema key -> account field the rest of the plugin already uses.
_FIELD_MAP = {
    "smtp_host": "host",
    "smtp_port": "port",
    "smtp_security": "security",
    "from_address": "from_address",
    "from_name": "from_name",
    "signature_text": "signature_text",
}


def settings() -> dict[str, Any]:
    """Non-secret settings with defaults applied, read through the public ``ctx.get_config``."""
    values = dict(DEFAULTS)
    get = getattr(_CTX, "get_config", None)
    if get is None:
        return values
    for key, default in DEFAULTS.items():
        try:
            value = get(key, default)
        except Exception:
            values["_read_error"] = True
            return values
        if value is not None:
            values[key] = value
    return values


def mail_defaults() -> dict[str, Any]:
    """Account-shaped defaults for fields the wizard has not saved yet."""
    values = settings()
    if values.get("_read_error"):
        return {"_read_error": True}
    return {field: values[key] for key, field in _FIELD_MAP.items()}


def secret_presence() -> dict[str, bool]:
    """Whether each declared secret name has a value. Never returns the value."""
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return {name: False for name in SECRET_NAMES}
    present = {}
    for name in SECRET_NAMES:
        try:
            present[name] = bool(get_secret(name, default=""))
        except Exception:
            present[name] = False
    return present


def credentials() -> tuple[str, str, str]:
    """``(username, password, error)`` from the active profile's secret scope."""
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return "", "", "secret_scope_unavailable"
    try:
        username = str(get_secret(SECRET_USERNAME, default="") or "")
        password = str(get_secret(SECRET_PASSWORD, default="") or "")
    except Exception:
        return "", "", "secret_read_failed"
    return username, password, ""


def effective_account(saved: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """Resolve operator-approved authority, never fall back from partial/invalid native settings."""
    try:
        from . import mail, storage
    except ImportError:
        import mail
        import storage
    defaults = mail_defaults()
    if defaults.get("_read_error"):
        return None, "settings_unavailable"
    source = "plugin_settings"
    candidate = dict(defaults)
    if not defaults.get("host") and not defaults.get("from_address"):
        if not saved:
            return None, "incomplete"
        # Old tool/wizard rows are indistinguishable. Preserve them but never authenticate to
        # their host until an explicit operator save records the new confirmation fingerprint.
        with storage.read_only() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (_approval_key(saved.get("business_id", "")),)).fetchone()
        if row is None or row["value"] != _fingerprint(saved):
            return None, "reconfirmation_required"
        candidate = dict(saved)
        source = "saved"
    if not candidate.get("host") or not candidate.get("from_address"):
        return None, "incomplete"
    try:
        return mail.validate_account(candidate), source
    except (ValueError, TypeError):
        return None, "invalid"


def _approval_key(business_id: str) -> str:
    return f"smtp_operator_confirmation_v1:{business_id}"


def _fingerprint(account: dict[str, Any]) -> str:
    fields = {key: account.get(key) for key in ("host", "port", "security", "from_address", "from_name")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()


def save_wizard_account(conn, business_id: str, account: dict[str, Any]) -> None:
    """Desktop-only caller: invoke after explicit operator confirmation, never from a model tool."""
    try:
        from . import mail, storage
    except ImportError:
        import mail
        import storage
    validated = mail.validate_account(account)
    storage.save_mail_settings(conn, business_id, validated)
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                 (_approval_key(business_id), _fingerprint(validated)))


def native_settings_path() -> list[str]:
    """Where the user finds the form, for the wizard's instruction text."""
    return ["Capabilities", "Plugins", "SalesPilot", "Settings"]
