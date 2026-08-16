from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_pr88_preserves_pr87_manifest_entrypoint():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    assert manifest["background"]["service_worker"] == "service_worker_temporary_chat_route_reopen_probe.js"


def test_pr88_release_primitive_lives_below_temporary_wrappers():
    text = (EXT / "service_worker_runtime_tab_reconciliation.js").read_text(
        encoding="utf-8"
    )
    assert 'importScripts("service_worker_observability.js")' in text
    assert 'message?.type !== "release_runtime_tab"' in text
    assert "browserAuthorityLeaseId" in text
    assert "expectedRuntimeTabId" in text
    assert "BROWSER_NATIVE_AUTHORITY_LEASE_CHANGED" in text
    assert "BROWSER_NATIVE_RUNTIME_TAB_CHANGED" in text
    assert "chrome.tabs.remove(storedTabId)" in text
    assert "activeRequestId !== null" in text