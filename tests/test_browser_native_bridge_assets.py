from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "experiments" / "browser_native_bridge" / "extension"


def test_manifest_is_narrow_and_has_required_debugger_capability() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    assert manifest["manifest_version"] == 3
    assert set(manifest["permissions"]) == {"debugger", "tabs"}
    assert manifest["host_permissions"] == ["https://chatgpt.com/*"]
    assert manifest["minimum_chrome_version"] == "118"


def test_probe_does_not_request_cookie_or_native_messaging_access_yet() -> None:
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    permissions = set(manifest["permissions"])
    assert "cookies" not in permissions
    assert "nativeMessaging" not in permissions


def test_worker_does_not_call_protected_chat_endpoint_directly() -> None:
    worker = (EXTENSION / "service_worker.js").read_text()
    assert "fetch(" not in worker
    assert "sentinel/chat-requirements" not in worker
    assert "turnstile" not in worker.lower()
    assert "proofofwork" not in worker.lower()
    assert "Fetch.failRequest" not in worker


def test_send_requires_explicit_chatgpt_tab_target() -> None:
    worker = (EXTENSION / "service_worker.js").read_text()
    popup = (EXTENSION / "popup.js").read_text()
    html = (EXTENSION / "popup.html").read_text()
    assert "TAB_ID_REQUIRED" in worker
    assert "tabId" in popup
    assert 'id="tab"' in html


def test_raw_stream_body_is_not_returned_or_displayed() -> None:
    worker = (EXTENSION / "service_worker.js").read_text()
    assert "responseBody:" not in worker
    assert "responseBodyBase64Encoded" not in worker
    assert "resume_conversation_token" not in worker
    assert '"type":"stream_handoff"' in worker
    assert "conversationId" in worker
    assert "turnExchangeId" in worker


def test_repeatability_harness_is_fixed_background_only_and_leak_checked() -> None:
    worker = (EXTENSION / "service_worker.js").read_text()
    popup = (EXTENSION / "popup.js").read_text()
    html = (EXTENSION / "popup.html").read_text()
    assert "STRESS_TURN_COUNT = 20" in worker
    assert "SDK_BRIDGE_STRESS_" in worker
    assert "STRESS_TARGET_MUST_BE_BACKGROUND" in worker
    assert "waitForComposerReady" in worker
    assert "debuggerAttachedAfter" in worker
    assert "run_repeatability_stress" in worker
    assert "run_repeatability_stress" in popup
    assert 'id="stress"' in html


def test_repeatability_verifier_exists() -> None:
    verifier = ROOT / "examples" / "verify_browser_native_stress.py"
    source = verifier.read_text()
    assert "analyze_stress_messages" in source
    assert "SDK_BRIDGE_STRESS_" in source
    assert '"duplicate_user"' in source
    assert '"duplicate_assistant"' in source
    assert '"order_ok"' in source
