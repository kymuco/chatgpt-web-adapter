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
