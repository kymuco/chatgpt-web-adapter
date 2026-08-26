from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.browser_owned_product_transport import BrowserOwnedProductTransport
from chatgpt_web_adapter.product_runtime import _known_browser_owned_rich_input_transport


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
REPAIR = EXT / "service_worker_rich_input_deadline_repair_pr9_2.js"
ENTRYPOINT = EXT / "service_worker_temporary_chat_route_reopen_probe.js"


def test_deadline_repair_overlay_is_loaded_after_primary_rich_input_overlay():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    primary = 'importScripts("service_worker_rich_input_pr9_2.js");'
    repair = 'importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");'
    assert primary in text
    assert repair in text
    assert text.index(primary) < text.index(repair)


def test_deadline_repair_guards_submit_and_requires_destructive_stale_cleanup_proof():
    text = REPAIR.read_text(encoding="utf-8")
    assert "const PR92_DEADLINE_REPAIR_SCHEMA = 4;" in text
    assert "PRE_SUBMIT_MOUSE_PRESS" in text
    assert "PRE_SUBMIT_MOUSE_RELEASE" in text
    assert "PRE_SUBMIT_ENTER_KEY_DOWN" in text
    assert "POST_SUBMIT_ENTER_KEY_UP" not in text
    assert 'type: "keyUp"' in text
    assert ".catch(() => {})" in text
    assert "enterKeyReleaseAffectsSubmittedOutcome: false" in text
    assert "mouseToEnterFallbackAfterReleaseAttempt: false" in text
    assert "mouseReleaseOutcomeAmbiguityFailsClosed: true" in text
    assert "PR9_2_MOUSE_RELEASE_OUTCOME_UNCONFIRMED" in text
    assert "let mouseReleaseAttempted = false;" in text
    assert "mouseReleaseAttempted = true;" in text
    assert "if (mouseReleaseAttempted)" in text
    assert "_pr92SubmitOfficialPageTurnWithoutPostBoundaryRetry" in text
    assert "CLEANUP_RUNTIME_TAB_LOOKUP" in text
    assert "CLEANUP_RUNTIME_TAB_CLOSE" in text
    assert "CLEANUP_RUNTIME_TAB_ABSENCE_CONFIRM" in text
    assert "chrome.tabs.remove(tabId)" in text
    assert "DOM.setFileInputFiles" not in text
    assert (
        'staleAttachmentCleanupProof: "RUNTIME_TAB_REMOVED_AND_ABSENCE_CONFIRMED"'
        in text
    )
    assert "postWriteFenceRetainedUntilNextPrewrite: true" in text
    assert "preSubmitDeadlineGuard: true" in text
    assert "deadlineBoundedPostWriteCleanup: true" in text


def test_rich_input_transport_authority_rejects_browser_owned_subclasses():
    exact = object.__new__(BrowserOwnedProductTransport)

    class BypassTransport(BrowserOwnedProductTransport):
        def send_text(self, *args, **kwargs):  # pragma: no cover - must never authorize
            raise AssertionError("bypass")

    bypass = object.__new__(BypassTransport)

    assert _known_browser_owned_rich_input_transport(exact) is True
    assert _known_browser_owned_rich_input_transport(bypass) is False
