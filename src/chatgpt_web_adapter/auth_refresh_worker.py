"""Bounded HTTPS worker for the ChatGPT Web session-refresh endpoint."""

from __future__ import annotations

import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .auth import CHATGPT_SESSION_COOKIE, CHAT_URL

SESSION_URL = f"{CHAT_URL.rstrip('/')}/api/auth/session"
MAX_REQUEST_BYTES = 128_000
MAX_RESPONSE_BYTES = 512_000
MAX_HEADER_COUNT = 24
MAX_HEADER_NAME_CHARS = 128
MAX_HEADER_VALUE_CHARS = 65_536
MAX_SET_COOKIE_HEADERS = 32
MAX_SET_COOKIE_CHARS = 32_768
_ALLOWED_HEADERS = frozenset(
    {
        "accept",
        "accept-encoding",
        "accept-language",
        "cookie",
        "oai-device-id",
        "origin",
        "priority",
        "referer",
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
        "user-agent",
    }
)


class _RejectSessionRedirects(HTTPRedirectHandler):
    """Keep session credentials bound to the fixed ChatGPT endpoint."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _is_session_cookie_name(value: str) -> bool:
    return value == CHATGPT_SESSION_COOKIE or value.startswith(
        f"{CHATGPT_SESSION_COOKIE}."
    )


def _bounded_cookie_header(value: str) -> str | None:
    accepted: list[str] = []
    for raw_pair in value.split(";"):
        pair = raw_pair.strip()
        if not pair or "=" not in pair:
            continue
        name, cookie_value = pair.split("=", 1)
        name = name.strip()
        if _is_session_cookie_name(name) or name == "oai-did":
            accepted.append(f"{name}={cookie_value.strip()}")
    if not any(
        pair.split("=", 1)[0] == CHATGPT_SESSION_COOKIE
        or pair.split("=", 1)[0].startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for pair in accepted
    ):
        return None
    result = "; ".join(accepted)
    return result if len(result) <= MAX_HEADER_VALUE_CHARS else None


def _bounded_headers(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict) or len(value) > MAX_HEADER_COUNT:
        return None
    headers: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        if not isinstance(raw_name, str) or not isinstance(raw_value, str):
            return None
        name = raw_name.strip().lower()
        if (
            name not in _ALLOWED_HEADERS
            or not name
            or len(name) > MAX_HEADER_NAME_CHARS
            or len(raw_value) > MAX_HEADER_VALUE_CHARS
            or "\r" in raw_value
            or "\n" in raw_value
        ):
            continue
        if name == "cookie":
            cookie_header = _bounded_cookie_header(raw_value)
            if cookie_header is None:
                return None
            headers[name] = cookie_header
        else:
            headers[name] = raw_value
    if "cookie" not in headers:
        return None
    return headers


def _session_set_cookie_headers(headers: Any) -> list[str]:
    get_all = getattr(headers, "get_all", None)
    if not callable(get_all):
        return []
    values = get_all("set-cookie", [])
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for value in values[:MAX_SET_COOKIE_HEADERS]:
        if not isinstance(value, str) or len(value) > MAX_SET_COOKIE_CHARS:
            continue
        name = value.split("=", 1)[0].strip()
        if _is_session_cookie_name(name):
            result.append(value)
    return result


def fetch_session(headers: dict[str, str], timeout: float) -> dict[str, Any]:
    """Fetch and reduce one fixed-endpoint session response."""

    bounded_headers = _bounded_headers(headers)
    if bounded_headers is None:
        return {"status": 0, "data": None, "set_cookie_headers": []}
    try:
        bounded_timeout = max(0.25, min(float(timeout), 300.0))
    except (TypeError, ValueError):
        return {"status": 0, "data": None, "set_cookie_headers": []}

    request = Request(SESSION_URL, method="GET", headers=bounded_headers)
    try:
        opener = build_opener(_RejectSessionRedirects())
        with opener.open(request, timeout=bounded_timeout) as response:
            status = int(response.status)
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
            set_cookie_headers = _session_set_cookie_headers(response.headers)
    except HTTPError as error:
        try:
            return {
                "status": int(error.code),
                "data": None,
                "set_cookie_headers": [],
            }
        finally:
            error.close()
    except (OSError, URLError, ValueError):
        return {"status": 0, "data": None, "set_cookie_headers": []}

    if len(raw_body) > MAX_RESPONSE_BYTES:
        return {"status": status, "data": None, "set_cookie_headers": []}
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    data = (
        {
            key: payload.get(key)
            for key in ("accessToken", "sessionToken", "expires")
        }
        if isinstance(payload, dict)
        else None
    )
    return {
        "status": status,
        "data": data,
        "set_cookie_headers": set_cookie_headers,
    }


def main() -> int:
    """Read one bounded private request from stdin and emit reduced JSON."""

    try:
        raw_request = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw_request) > MAX_REQUEST_BYTES:
            return 2
        request = json.loads(raw_request)
        headers = request["headers"]
        timeout = float(request["timeout"])
        bounded_headers = _bounded_headers(headers)
        if bounded_headers is None:
            return 2
        result = fetch_session(bounded_headers, timeout)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
