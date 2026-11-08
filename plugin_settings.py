"""Mail defaults from the plugin's native Hermes settings.

`plugin.yaml` declares ``config_schema``; the Desktop renders it under Settings → Plugins and
writes non-secret values to ``plugins.entries.hermes-salespilot.settings``. The SMTP username and
password are declared ``type: secret`` with an explicit ``env:`` name, so Hermes stores them only
through its credential route and this module reads them with ``agent.secret_scope.get_secret``.
There is no second credential store here: values never enter SQLite, logs or an API response.

Precedence, highest first: the account saved by the setup wizard (SQLite), then these settings,
then the defaults below.
"""

from __future__ import annotations

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
            continue
        if value is not None:
            values[key] = value
    return values


def mail_defaults() -> dict[str, Any]:
    """Account-shaped defaults for fields the wizard has not saved yet."""
    values = settings()
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
    """Merge the saved account over the native settings.

    Returns ``(account, source)`` where source is ``saved``, ``plugin_settings``, ``incomplete`` or
    ``invalid``. A saved field always wins, so editing Settings cannot silently redirect an account
    the operator already confirmed inside the wizard.
    """
    try:
        import mail
    except ImportError:
        from . import mail
    defaults = mail_defaults()
    if saved:
        merged = dict(saved)
        for key, fallback in defaults.items():
            if not merged.get(key):
                merged[key] = fallback
        return merged, "saved"
    candidate = {**defaults, "position": "", "company": "", "contact": ""}
    if not candidate.get("host") or not candidate.get("from_address"):
        return None, "incomplete"
    try:
        return mail.validate_account(candidate), "plugin_settings"
    except (ValueError, TypeError):
        return None, "invalid"


def native_settings_path() -> list[str]:
    """Where the user finds the form, for the wizard's instruction text."""
    return ["Capabilities", "Plugins", "SalesPilot", "Settings"]
