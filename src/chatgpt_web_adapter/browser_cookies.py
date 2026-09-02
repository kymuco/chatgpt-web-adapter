from __future__ import annotations

from typing import Any

from .auth import CHAT_URL

_COOKIE_FIELDS = (
    "name",
    "value",
    "domain",
    "path",
    "secure",
    "http_only",
    "same_site",
    "expires",
    "priority",
    "same_party",
    "source_scheme",
    "source_port",
)


def _is_chatgpt_cookie_domain(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    domain = value.strip().lstrip(".").lower()
    return domain == "chatgpt.com" or domain.endswith(".chatgpt.com")


def serialize_browser_cookies(browser_cookies: Any) -> list[dict[str, Any]]:
    """Keep portable CDP cookie attributes without persisting runtime objects."""

    records: list[dict[str, Any]] = []
    if not isinstance(browser_cookies, list):
        return records
    for cookie in browser_cookies:
        domain = getattr(cookie, "domain", "")
        name = getattr(cookie, "name", None)
        value = getattr(cookie, "value", None)
        if not (
            _is_chatgpt_cookie_domain(domain)
            and isinstance(name, str)
            and isinstance(value, str)
        ):
            continue
        record: dict[str, Any] = {}
        for field in _COOKIE_FIELDS:
            item = getattr(cookie, field, None)
            if item is None:
                continue
            if hasattr(item, "value"):
                item = item.value
            if isinstance(item, (str, int, float, bool)):
                record[field] = item
        record.setdefault("path", "/")
        records.append(record)
    dotted_session_names = {
        str(record.get("name"))
        for record in records
        if "session-token" in str(record.get("name", ""))
        and str(record.get("domain", "")).startswith(".")
    }
    if dotted_session_names:
        records = [
            record
            for record in records
            if not (
                str(record.get("name")) in dotted_session_names
                and not str(record.get("domain", "")).startswith(".")
            )
        ]
    return records


def flatten_browser_cookies(records: Any) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if not isinstance(records, list):
        return cookies
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("name")
        value = record.get("value")
        domain = record.get("domain", "")
        if (
            isinstance(name, str)
            and isinstance(value, str)
            and _is_chatgpt_cookie_domain(domain)
        ):
            cookies[name] = value
    return cookies


def browser_cookie_params(
    cdp: Any,
    records: Any,
    fallback_cookies: dict[str, str],
    *,
    fallback_expires: float | None = None,
) -> list[Any]:
    """Build CDP cookie parameters, preferring domain-aware saved records."""

    params: list[Any] = []
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            name = record.get("name")
            value = record.get("value")
            domain = record.get("domain")
            if not (
                all(isinstance(item, str) and item for item in (name, value, domain))
                and _is_chatgpt_cookie_domain(domain)
            ):
                continue
            kwargs: dict[str, Any] = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": str(record.get("path") or "/"),
                "secure": bool(record.get("secure", True)),
                "http_only": bool(record.get("http_only", False)),
            }
            expires = record.get("expires")
            if isinstance(expires, (int, float)) and float(expires) > 0:
                kwargs["expires"] = cdp.network.TimeSinceEpoch(float(expires))
            elif fallback_expires is not None:
                kwargs["expires"] = cdp.network.TimeSinceEpoch(fallback_expires)
            enum_fields = (
                ("same_site", "CookieSameSite"),
                ("priority", "CookiePriority"),
                ("source_scheme", "CookieSourceScheme"),
            )
            for field, enum_name in enum_fields:
                enum_type = getattr(cdp.network, enum_name, None)
                raw = record.get(field)
                if enum_type is not None and isinstance(raw, str):
                    try:
                        kwargs[field] = enum_type(raw)
                    except ValueError:
                        pass
            for field in ("same_party", "source_port"):
                if field in record:
                    kwargs[field] = record[field]
            params.append(cdp.network.CookieParam(**kwargs))
    if params:
        return params
    return [
        cdp.network.CookieParam(
            name=str(name),
            value=str(value),
            url=CHAT_URL,
            secure=True,
            expires=(
                cdp.network.TimeSinceEpoch(fallback_expires)
                if fallback_expires is not None
                else None
            ),
        )
        for name, value in fallback_cookies.items()
        if name is not None and value is not None
    ]
