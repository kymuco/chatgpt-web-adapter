from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_manifest_presents_a_product_popup_without_expanding_permissions() -> None:
    manifest = json.loads(_read(EXT / "manifest.json"))

    assert manifest["name"] == "ChatGPT Web Adapter"
    assert manifest["description"] == (
        "Connects the CWA local runtime to your existing ChatGPT browser session."
    )
    # PR11.0 is a product-surface milestone, not a protocol/worker generation bump.
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == (
        "service_worker_temporary_chat_route_reopen_probe.js"
    )
    assert set(manifest["permissions"]) == {"debugger", "tabs", "storage", "nativeMessaging"}
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]
    assert manifest["action"]["default_popup"] == "popup.html"
    assert manifest["action"]["default_title"] == "ChatGPT Web Adapter"
    assert manifest["icons"] == {
        "16": "icon16.png",
        "32": "icon32.png",
        "48": "icon48.png",
        "128": "icon128.png",
    }
    assert manifest["action"]["default_icon"] == manifest["icons"]


def test_product_icon_assets_are_real_pngs_at_chrome_sizes() -> None:
    for size in (16, 32, 48, 128):
        path = EXT / f"icon{size}.png"
        assert path.is_file()
        assert _png_dimensions(path) == (size, size)


def test_popup_is_product_first_with_engineering_details_collapsed() -> None:
    html = _read(EXT / "popup.html")
    css = _read(EXT / "popup.css")
    script = _read(EXT / "popup.js")

    assert '<script src="popup.js"></script>' in html
    assert "popup.css" in html
    assert "Connects your local runtime to this browser session." in html
    assert "Open ChatGPT" in html
    assert "Copy diagnostics" in html
    assert "<details" in html
    assert "<summary>Details</summary>" in html
    assert "Native host" in html
    assert "Runtime tab" in html
    assert "LOCAL BROWSER BRIDGE" not in html
    assert "popup performs no ChatGPT product write" not in html
    assert "prefers-color-scheme: dark" in css

    assert 'const STATUS_MESSAGE_TYPE = "cwa_bridge_status";' in script
    assert 'const CHATGPT_URL = "https://chatgpt.com/";' in script
    assert 'elements.statusTitle.textContent = "Ready"' in script
    assert 'elements.statusTitle.textContent = "Needs attention"' in script
    assert "chrome.runtime.sendMessage" in script
    assert "chrome.tabs.create({ url: CHATGPT_URL })" in script
    assert "navigator.clipboard.writeText" in script
    assert "conversationId" not in script
    assert "tabId" not in script
    assert "authorization" not in script.lower()
    assert "cookie" not in script.lower()
    assert "signed_url" not in script.lower()
    assert "send_text" not in script
    assert "executeNativeTurn" not in script


def test_service_worker_status_surface_is_local_sanitized_and_non_mutating() -> None:
    worker = _read(EXT / "service_worker_product_surface_pr11_0.js")
    observability = _read(EXT / "service_worker_observability.js")

    assert 'const CWA_PRODUCT_STATUS_MESSAGE_TYPE = "cwa_bridge_status";' in worker
    assert "nativeHostConnected: nativePort !== null" in worker
    assert "runtimeTabPresent: runtimeTab.present" in worker
    assert "busy: activeRequestId !== null" in worker
    assert 'transport: "browser-owned"' in worker
    assert '"ChatGPT Web Adapter — Needs attention"' in worker
    assert '"ChatGPT Web Adapter — Ready"' in worker
    assert "chrome.action.setBadgeText" in worker
    assert "chrome.action.setTitle" in worker

    # The status layer may inspect the already-owned runtime tab identity locally,
    # but it must not export capability-bearing or product-private identifiers.
    assert "conversationId:" not in worker
    assert "tabId:" not in worker
    assert "finalUrl" not in worker
    assert "chrome.debugger" not in worker
    assert "Input.dispatch" not in worker
    assert "executeNativeTurn(" not in worker
    assert "ensureRuntimeTab(" not in worker
    assert "chrome.tabs.create" not in worker

    assert 'importScripts("service_worker_product_surface_pr11_0.js");' in observability
    assert observability.index('importScripts("service_worker_product_surface_pr11_0.js");') > (
        observability.index("_executeNativeTurnWithProvisioningObservability")
    )


def test_popup_clipboard_contract_is_explicitly_sanitized() -> None:
    script = _read(EXT / "popup.js")
    clipboard_contract = script.split("function safeStatusForClipboard", 1)[1].split(
        "async function copyStatus", 1
    )[0]

    expected_keys = {
        "product",
        "surface",
        "extensionVersion",
        "protocolVersion",
        "nativeHostConnected",
        "runtimeTabPresent",
        "runtimeTabRouteKind",
        "busy",
        "transport",
    }
    for key in expected_keys:
        assert key in clipboard_contract

    for forbidden in (
        "runtimeTabId",
        "conversationId",
        "turnExchangeId",
        "url",
        "href",
        "cookie",
        "token",
        "authorization",
    ):
        assert forbidden.lower() not in clipboard_contract.lower()


def test_package_and_release_gate_include_product_assets() -> None:
    pyproject = _read(ROOT / "pyproject.toml")
    release_gate = _read(ROOT / "tools" / "release_gate.py")

    for pattern in (
        '"browser_native_extension/*.html"',
        '"browser_native_extension/*.css"',
        '"browser_native_extension/*.png"',
    ):
        assert pattern in pyproject

    assert 'EXTENSION_PACKAGE_PATTERNS = ("*.json", "*.js", "*.html", "*.css", "*.png")' in release_gate
    for required in (
        "browser_native_extension/popup.html",
        "browser_native_extension/popup.css",
        "browser_native_extension/popup.js",
        "browser_native_extension/icon128.png",
        "browser_native_extension/service_worker_product_surface_pr11_0.js",
    ):
        assert required in release_gate
