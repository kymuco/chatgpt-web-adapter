from __future__ import annotations

from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_patch_protocol_is_owned_by_single_response_stream_worker() -> None:
    root = browser_native_extension_dir()
    observability = (root / "service_worker_observability.js").read_text(
        encoding="utf-8"
    )
    owner = 'importScripts("service_worker_browser_response_stream.js")'
    assert owner in observability
    assert "service_worker_safe_browser_response_stream_pr8_9.js" not in observability
    assert (
        "service_worker_safe_browser_response_patch_protocol_pr8_9.js"
        not in observability
    )
    assert "service_worker_revision_safe_text_delivery_pr8_9.js" not in observability


def test_patch_protocol_matches_existing_product_stream_parser_contract() -> None:
    root = browser_native_extension_dir()
    overlay = (root / "service_worker_browser_response_stream.js").read_text(
        encoding="utf-8"
    )
    client = (root.parent / "legacy_client_core.py").read_text(encoding="utf-8")

    for token in (
        "payload.v",
        "payload.p",
        "value.message",
        '"/message/content/parts/0"',
        '"/message/metadata"',
        "_pr89PatchAppendText",
        "patchProtocolEventCount",
        "patchTextDeltaCount",
    ):
        assert token in overlay

    for token in (
        'value = payload.get("v")',
        'path = payload.get("p")',
        'message = value.get("message")',
        '"/message/content/parts/0"',
        '"/message/metadata"',
    ):
        assert token in client


def test_patch_protocol_overlay_does_not_widen_network_or_secret_surface() -> None:
    root = browser_native_extension_dir()
    source = (root / "service_worker_browser_response_stream.js").read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "Network.getResponseBody",
        "Network.getRequestPostData",
        "Fetch.enable",
        "Fetch.fulfillRequest",
        "Fetch.failRequest",
        "Fetch.continueRequest",
        "document.cookie",
        "request.headers",
        "Authorization",
        "set-cookie",
        "chrome.tabs.create",
        "chrome.tabs.update",
        "conversation/write",
    ):
        assert forbidden not in source


def test_fragmented_pr89_response_workers_are_retired() -> None:
    root = browser_native_extension_dir()
    for name in (
        "service_worker_safe_browser_response_stream_pr8_9.js",
        "service_worker_safe_browser_response_patch_protocol_pr8_9.js",
        "service_worker_revision_safe_text_delivery_pr8_9.js",
    ):
        assert not (root / name).exists()
