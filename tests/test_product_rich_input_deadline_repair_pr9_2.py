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


def test_deadline_repair_guards_exact_submit_events_and_bounded_cleanup():
    text = REPAIR.read_text(encoding="utf-8")
    assert "PRE_SUBMIT_MOUSE_PRESS" in text
    assert "PRE_SUBMIT_MOUSE_RELEASE" in text
    assert "PRE_SUBMIT_ENTER_KEY_DOWN" in text
    assert "_pr92DeadlineRepairRunUntil" in text
    assert "CLEANUP_DEBUGGER_ATTACH" in text
    assert "CLEANUP_RUNTIME_ENABLE" in text
    assert "CLEANUP_DOM_ENABLE" in text
    assert "CLEANUP_FILE_INPUT_LOOKUP" in text
    assert "CLEANUP_FILE_SELECTION_CLEAR" in text
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
