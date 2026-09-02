from __future__ import annotations

from enum import Enum
from types import SimpleNamespace

from chatgpt_web_adapter.browser_cookies import (
    browser_cookie_params,
    flatten_browser_cookies,
    serialize_browser_cookies,
)


def test_browser_cookie_round_trip_preserves_scope() -> None:
    records = serialize_browser_cookies(
        [
            SimpleNamespace(
                name="session.0",
                value="chunk",
                domain=".chatgpt.com",
                path="/",
                secure=True,
                http_only=True,
                same_site="Lax",
                expires=1234.0,
            ),
            SimpleNamespace(
                name="outside",
                value="ignored",
                domain="example.com",
            ),
        ]
    )

    assert records == [
        {
            "name": "session.0",
            "value": "chunk",
            "domain": ".chatgpt.com",
            "path": "/",
            "secure": True,
            "http_only": True,
            "same_site": "Lax",
            "expires": 1234.0,
        }
    ]
    assert flatten_browser_cookies(records) == {"session.0": "chunk"}


def test_browser_cookie_domain_validation_rejects_lookalikes() -> None:
    records = serialize_browser_cookies(
        [
            SimpleNamespace(name="exact", value="ok", domain="chatgpt.com"),
            SimpleNamespace(name="subdomain", value="ok", domain=".auth.chatgpt.com"),
            SimpleNamespace(name="prefix-lookalike", value="bad", domain="evilchatgpt.com"),
            SimpleNamespace(
                name="suffix-lookalike",
                value="bad",
                domain="chatgpt.com.evil.example",
            ),
        ]
    )

    assert [record["name"] for record in records] == ["exact", "subdomain"]
    assert flatten_browser_cookies(
        [
            {"name": "exact", "value": "ok", "domain": "chatgpt.com"},
            {"name": "subdomain", "value": "ok", "domain": ".auth.chatgpt.com"},
            {"name": "prefix-lookalike", "value": "bad", "domain": "evilchatgpt.com"},
            {
                "name": "suffix-lookalike",
                "value": "bad",
                "domain": "chatgpt.com.evil.example",
            },
        ]
    ) == {"exact": "ok", "subdomain": "ok"}


def test_cookie_params_prefer_structured_records() -> None:
    network = SimpleNamespace(
        CookieParam=lambda **kwargs: kwargs,
        TimeSinceEpoch=float,
    )
    cdp = SimpleNamespace(network=network)

    params = browser_cookie_params(
        cdp,
        [
            {
                "name": "session.0",
                "value": "chunk",
                "domain": ".chatgpt.com",
                "path": "/",
                "secure": True,
                "http_only": True,
                "expires": 1234.0,
            }
        ],
        {"session.0": "flat-fallback"},
    )

    assert params == [
        {
            "name": "session.0",
            "value": "chunk",
            "domain": ".chatgpt.com",
            "path": "/",
            "secure": True,
            "http_only": True,
            "expires": 1234.0,
        }
    ]


def test_cookie_params_reject_lookalike_structured_domains() -> None:
    network = SimpleNamespace(
        CookieParam=lambda **kwargs: kwargs,
        TimeSinceEpoch=float,
    )
    cdp = SimpleNamespace(network=network)

    params = browser_cookie_params(
        cdp,
        [
            {
                "name": "poisoned",
                "value": "bad",
                "domain": "evilchatgpt.com",
                "path": "/",
            },
            {
                "name": "also-poisoned",
                "value": "bad",
                "domain": "chatgpt.com.evil.example",
                "path": "/",
            },
        ],
        {"safe-fallback": "value"},
    )

    assert params == [
        {
            "name": "safe-fallback",
            "value": "value",
            "url": "https://chatgpt.com/",
            "secure": True,
            "expires": None,
        }
    ]


def test_browser_cookie_serialization_prefers_domain_scoped_session_chunks() -> None:
    records = serialize_browser_cookies(
        [
            SimpleNamespace(
                name="__Secure-next-auth.session-token.0",
                value="domain",
                domain=".chatgpt.com",
                path="/",
            ),
            SimpleNamespace(
                name="__Secure-next-auth.session-token.0",
                value="host-only-duplicate",
                domain="chatgpt.com",
                path="/",
            ),
        ]
    )

    assert len(records) == 1
    assert records[0]["domain"] == ".chatgpt.com"
    assert records[0]["value"] == "domain"


def test_cookie_params_restore_enum_and_source_attributes() -> None:
    class SameSite(Enum):
        LAX = "Lax"

    class Priority(Enum):
        HIGH = "High"

    class SourceScheme(Enum):
        SECURE = "Secure"

    network = SimpleNamespace(
        CookieParam=lambda **kwargs: kwargs,
        TimeSinceEpoch=float,
        CookieSameSite=SameSite,
        CookiePriority=Priority,
        CookieSourceScheme=SourceScheme,
    )

    [param] = browser_cookie_params(
        SimpleNamespace(network=network),
        [
            {
                "name": "cookie",
                "value": "value",
                "domain": ".chatgpt.com",
                "same_site": "Lax",
                "priority": "High",
                "source_scheme": "Secure",
                "same_party": False,
                "source_port": 443,
            }
        ],
        {},
    )

    assert param["same_site"] is SameSite.LAX
    assert param["priority"] is Priority.HIGH
    assert param["source_scheme"] is SourceScheme.SECURE
    assert param["same_party"] is False
    assert param["source_port"] == 443
