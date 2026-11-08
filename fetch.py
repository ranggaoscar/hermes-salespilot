"""Public HTTP fetch with a fail-closed SSRF check. No credential reads."""

from __future__ import annotations

import http.client
import ipaddress
import os
import re
import socket
import ssl
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

MAX_BYTES = 400_000
TIMEOUT_S = 8
MAX_REDIRECTS = 2

_BLOCKED_HOSTS = frozenset({
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
})
_METADATA_V4 = (
    "169.254.169.254",
    "169.254.170.2",
    "169.254.169.253",
    "100.100.100.200",
)
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
_LINK_LOCAL = ipaddress.ip_network("169.254.0.0/16")
_IPV4_TRANSLATED = ipaddress.ip_network("::ffff:0:0:0/96")
_RESOLVER: Callable[[str], list[str]] | None = None
_DIAL: Callable[..., Any] | None = None
_LOOPBACK_TESTS = False
_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def set_resolver_for_tests(fn: Callable[[str], list[str]] | None) -> None:
    global _RESOLVER
    _RESOLVER = fn


def set_dial_for_tests(fn: Callable[..., Any] | None) -> None:
    """Replace the pinned TCP dial. Tests use this to prove which IP is connected."""
    global _DIAL
    _DIAL = fn


def allow_loopback_for_tests(enabled: bool) -> None:
    """Test harness only. Tool arguments cannot set this."""
    global _LOOPBACK_TESTS
    _LOOPBACK_TESTS = enabled


def _embedded_v4(ip: ipaddress._BaseAddress) -> ipaddress._BaseAddress:
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
        if ip in _IPV4_TRANSLATED:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip


def _blocked_ip(ip: ipaddress._BaseAddress) -> str:
    ip = _embedded_v4(ip)
    if str(ip) in _METADATA_V4 or ip in _LINK_LOCAL:
        return "cloud_metadata"
    if ip.is_loopback:
        return "" if _LOOPBACK_TESTS else "loopback"
    if ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        return "private_or_reserved"
    if ip in _CGNAT:
        return "cgnat"
    return ""


def _literal_ip(host: str) -> ipaddress._BaseAddress | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if host.isdigit():
        try:
            return ipaddress.ip_address(int(host))
        except ValueError:
            return None
    return None


def _ambiguous_v4(host: str) -> bool:
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host):
        return False
    return any(part.startswith("0") and part != "0" for part in host.split("."))


def resolve_host(host: str) -> list[str]:
    if _RESOLVER is not None:
        return list(_RESOLVER(host))
    infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    found = []
    for info in infos:
        found.append(info[4][0])
    return found


def assess_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return {"ok": False, "code": "bad_scheme", "error": "Only http and https are allowed."}
    if parsed.username or parsed.password:
        return {"ok": False, "code": "userinfo", "error": "URLs with userinfo are refused."}
    host = (parsed.hostname or "").strip().rstrip(".")
    if not host or host.lower() in _BLOCKED_HOSTS or host.lower().endswith(".localhost") or host.lower().endswith(".local"):
        return {"ok": False, "code": "blocked_host", "error": "That host is blocked."}
    try:
        host_ascii = host.encode("idna").decode("ascii")
    except UnicodeError:
        return {"ok": False, "code": "bad_host", "error": "Host name is not valid IDN."}
    host_ascii = host_ascii.lower()
    if _ambiguous_v4(host_ascii):
        return {"ok": False, "code": "ambiguous_ip", "error": "Ambiguous IP literal is refused."}
    literal = _literal_ip(host_ascii)
    ips = [str(literal)] if literal is not None else None
    if ips is None:
        try:
            ips = resolve_host(host_ascii)
        except socket.gaierror:
            return {"ok": False, "code": "dns_failed", "error": "DNS resolution failed. Refusing the fetch."}
    if not ips:
        return {"ok": False, "code": "dns_failed", "error": "DNS returned no addresses."}
    checked = []
    for raw in ips:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return {"ok": False, "code": "bad_dns", "error": "DNS returned an unparseable address."}
        reason = _blocked_ip(ip)
        if reason:
            return {"ok": False, "code": "ssrf_blocked", "error": f"Refusing {reason} address.", "ip": str(_embedded_v4(ip))}
        checked.append(str(ip))
    return {"ok": True, "host": host, "host_ascii": host_ascii, "ips": checked, "scheme": scheme, "port": parsed.port}


def html_to_text(body: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", body)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>|</div>|</li>|</h[1-6]>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _read_response(response: Any) -> tuple[int, str, str]:
    status = int(getattr(response, "status", 0) or 0)
    location = ""
    headers = getattr(response, "headers", None)
    if headers is not None:
        location = headers.get("Location") or headers.get("location") or ""
    raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("too_large")
    charset = "utf-8"
    content_type = ""
    if headers is not None:
        content_type = headers.get("Content-Type") or headers.get("content-type") or ""
        match = re.search(r"charset=([\w.-]+)", content_type, re.I)
        if match:
            charset = match.group(1)
    text = raw.decode(charset, errors="replace")
    if "html" in content_type.lower() or text.lstrip().lower().startswith("<!doctype") or text.lstrip().lower().startswith("<html"):
        text = html_to_text(text)
    return status, location, text


def _proxy_env() -> str:
    for key in _PROXY_KEYS:
        if os.environ.get(key):
            return key
    return ""


def _dial(ip: str, port: int, timeout: int, scheme: str, host_ascii: str) -> socket.socket:
    if _DIAL is not None:
        return _DIAL(ip, port, timeout, scheme, host_ascii)
    sock = socket.create_connection((ip, port), timeout)
    if scheme == "https":
        return ssl.create_default_context().wrap_socket(sock, server_hostname=host_ascii)
    return sock


def _exchange(host_ascii: str, ip: str, port: int, scheme: str, path: str, timeout: int) -> tuple[int, str, str]:
    sock = _dial(ip, port, timeout, scheme, host_ascii)
    conn = http.client.HTTPConnection(host_ascii, port, timeout=timeout)
    conn.sock = sock
    if ":" in host_ascii:
        host_header = f"[{host_ascii}]" if port in {80, 443} else f"[{host_ascii}]:{port}"
    else:
        host_header = host_ascii if port in {80, 443} else f"{host_ascii}:{port}"
    conn.request(
        "GET",
        path or "/",
        headers={
            "Host": host_header,
            "User-Agent": "SalesPilot/0.4",
            "Accept": "text/plain,text/html",
            "Connection": "close",
        },
    )
    response = conn.getresponse()
    status = int(response.status)
    location = response.getheader("Location") or ""
    content_type = response.getheader("Content-Type") or ""
    raw = response.read(MAX_BYTES + 1)
    conn.close()
    if len(raw) > MAX_BYTES:
        raise ValueError("too_large")
    charset = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, re.I)
    if match:
        charset = match.group(1)
    text = raw.decode(charset, errors="replace")
    if "html" in content_type.lower() or text.lstrip().lower().startswith("<!doctype") or text.lstrip().lower().startswith("<html"):
        text = html_to_text(text)
    return status, location, text


def fetch_public_url(url: str, *, timeout: int = TIMEOUT_S) -> dict[str, Any]:
    proxy = _proxy_env()
    if proxy:
        return {
            "ok": False,
            "code": "proxy_blocked",
            "error": "Proxy environment variables are refused so they cannot bypass the destination check.",
            "fetched": False,
        }
    current = url
    hops = []
    for _ in range(MAX_REDIRECTS + 1):
        verdict = assess_url(current)
        if not verdict.get("ok"):
            verdict["url"] = current
            verdict["fetched"] = False
            return verdict
        parsed = urlparse(current)
        port = parsed.port or (443 if verdict["scheme"] == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        ip = verdict["ips"][0]
        hops.append(current)
        try:
            status, location, text = _exchange(verdict["host_ascii"], ip, port, verdict["scheme"], path, timeout)
        except ValueError as exc:
            if str(exc) == "too_large":
                return {"ok": False, "code": "too_large", "error": "Page exceeded the fetch size limit.", "fetched": False}
            return {"ok": False, "code": "fetch_failed", "error": "Fetch failed.", "fetched": False, "pinned_ip": ip}
        except Exception:
            return {"ok": False, "code": "fetch_failed", "error": "Fetch failed or timed out.", "fetched": False, "pinned_ip": ip}
        if status in {301, 302, 303, 307, 308}:
            if not location:
                return {"ok": False, "code": "bad_redirect", "error": "Redirect had no location.", "fetched": False}
            current = urljoin(current, location)
            continue
        if status >= 400:
            return {"ok": False, "code": "http_error", "error": f"HTTP {status}", "fetched": False}
        return {
            "ok": True,
            "fetched": True,
            "url": hops[-1],
            "text": text,
            "redirects": hops[:-1],
            "pinned_ip": ip,
            "truncated": False,
        }
    return {"ok": False, "code": "too_many_redirects", "error": "Too many redirects.", "fetched": False}
