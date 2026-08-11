from __future__ import annotations

import pytest

from chatgpt_web_adapter.browser_sentinel import (
    ZendriverSentinelBundleProvider,
    _bundle_from_finalize_capture,
    _sync_chatgpt_cookies,
)
from chatgpt_web_adapter.exceptions import RequestError


def test_bundle_from_finalize_capture_preserves_one_shot_headers() -> None:
    bundle = _bundle_from_finalize_capture(
        {
            "prepare_token": "prepare-current",
            "proofofwork": "proof-current",
            "turnstile": "turnstile-current",
        },
        200,
        {
            "persona": "chatgpt-web",
            "token": "requirements-current",
            "expire_after": 60,
            "expire_at": 1060,
        },
        acquired_monotonic=10,
        acquired_wallclock=1000,
    )

    assert bundle.requirements_token == "requirements-current"
    assert bundle.proof_token == "proof-current"
    assert bundle.turnstile_token == "turnstile-current"
    assert bundle.expires_monotonic == 65
    assert bundle.source == "browser_finalize_capture"


@pytest.mark.parametrize("missing", ["prepare_token", "proofofwork", "turnstile"])
def test_bundle_from_finalize_capture_rejects_incomplete_request(missing: str) -> None:
    request = {
        "prepare_token": "prepare-current",
        "proofofwork": "proof-current",
        "turnstile": "turnstile-current",
    }
    request.pop(missing)

    with pytest.raises(RequestError, match="CAPTURE_INVALID"):
        _bundle_from_finalize_capture(
            request,
            200,
            {
                "persona": "chatgpt-web",
                "token": "requirements-current",
                "expire_after": 60,
                "expire_at": 1060,
            },
            acquired_monotonic=10,
            acquired_wallclock=1000,
        )


def test_zendriver_provider_validates_timeout() -> None:
    with pytest.raises(ValueError, match="positive"):
        ZendriverSentinelBundleProvider(timeout=0)


def test_zendriver_provider_accepts_persistent_auth_profile(tmp_path) -> None:
    provider = ZendriverSentinelBundleProvider(profile_dir=tmp_path / "profile")
    assert provider.profile_dir == tmp_path / "profile"
    assert provider.seeds_client_cookies is False


def test_zendriver_provider_seeds_only_temporary_profile() -> None:
    provider = ZendriverSentinelBundleProvider()
    assert provider.seeds_client_cookies is True


def test_sync_chatgpt_cookies_updates_device_binding_only_for_chatgpt() -> None:
    from types import SimpleNamespace

    client = SimpleNamespace(
        auth=SimpleNamespace(cookies={"existing": "cookie"}),
        base_headers={},
    )
    _sync_chatgpt_cookies(
        client,
        [
            SimpleNamespace(domain=".chatgpt.com", name="oai-did", value="device"),
            SimpleNamespace(domain="example.com", name="outside", value="ignored"),
        ],
    )

    assert client.auth.cookies == {"existing": "cookie", "oai-did": "device"}
    assert client.base_headers["oai-device-id"] == "device"
