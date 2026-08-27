from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SCHEMA7 = EXT / "service_worker_rich_input_schema7_repair_pr9_2.js"
ENTRYPOINT = EXT / "service_worker_temporary_chat_route_reopen_probe.js"


def test_schema_7_overlay_is_loaded_after_all_prior_pr9_2_layers():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    primary = 'importScripts("service_worker_rich_input_pr9_2.js");'
    deadline = 'importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");'
    closure = 'importScripts("service_worker_rich_input_closure_repair_pr9_2.js");'
    schema7 = 'importScripts("service_worker_rich_input_schema7_repair_pr9_2.js");'

    for item in (primary, deadline, closure, schema7):
        assert item in text
    assert text.index(primary) < text.index(deadline) < text.index(closure) < text.index(schema7)


def test_schema_7_final_attachment_validation_and_click_are_one_page_expression():
    text = SCHEMA7.read_text(encoding="utf-8")

    assert "const PR92_SCHEMA7_REPAIR_SCHEMA = 7;" in text
    assert "_pr92Schema7AtomicAttachmentSubmitExpression" in text
    assert "const evidence = ${evidenceExpression};" in text
    assert "attachment-evidence-missing" in text
    assert "button.click();" in text
    assert "atomic-page-owned-click" in text
    assert "atomicAttachmentValidationAndSubmit: true" in text
    assert (
        'PR92_SCHEMA7_PROTECTED_SUBMIT_PRIMITIVE =\n  '
        '"PAGE_DEADLINE_GUARDED_ATOMIC_ATTACHMENT_VALIDATE_AND_CLICK"'
        in text
    )

    expression = text[
        text.index("function _pr92Schema7AtomicAttachmentSubmitExpression") :
        text.index("submitOfficialPageTurn = async function _pr92Schema7AtomicAttachmentSubmit")
    ]
    assert expression.index("const evidence = ${evidenceExpression};") < expression.index("button.click();")


def test_schema_7_does_not_await_debugger_ack_after_potential_click():
    text = SCHEMA7.read_text(encoding="utf-8")
    submit = text[
        text.index("submitOfficialPageTurn = async function _pr92Schema7AtomicAttachmentSubmit") :
        text.index("executeNativeTurn = async function _executeNativeTurnWithPr92Schema7Repair")
    ]

    dispatch = 'const pending = chrome.debugger.sendCommand(debuggee, "Runtime.evaluate", {'
    assert dispatch in submit
    assert "pending.catch(() => {});" in submit
    assert "await chrome.debugger.sendCommand(debuggee, \"Runtime.evaluate\"" not in submit
    assert "PR92_SCHEMA7_SUBMIT_OBSERVATION_RESERVE_MS" in submit
    assert "postClickDebuggerAckRequired: false" in text
    assert 'protectedSubmitOutcomeProof: PR92_SCHEMA7_POST_SUBMIT_PROOF' in text
    assert 'PR92_SCHEMA7_POST_SUBMIT_PROOF = "NETWORK_REQUEST_OBSERVATION"' in text


def test_schema_7_fenced_tab_cleanup_requires_browser_session_identity():
    text = SCHEMA7.read_text(encoding="utf-8")

    assert 'PR92_SCHEMA7_SESSION_IDENTITY_KEY = "pr92DirtyAttachmentSessionIdentityV1"' in text
    assert "chrome.storage.session.set" in text
    assert "chrome.storage.session.get" in text
    assert "storedRuntimeTabId()" in text
    assert "if (!isChatGPTUrl(candidate?.url || \"\")) return true;" in text
    assert "if (currentRuntimeTabId !== tabId)" in text
    assert "if (records.session == null)" in text
    assert "sessionIdentity !== localIdentity" in text
    assert "chrome.tabs.remove(tabId)" in text
    assert "staleAttachmentCleanupRequiresSessionRuntimeIdentity: true" in text
    assert "staleAttachmentIdentityMismatchClosesTab: false" in text
    assert "staleAttachmentUnprovenIdentityFailsClosed: true" in text

    cleanup = text[
        text.index("_pr92ClearOfficialPageAttachments = async function _pr92Schema7ClearFencedRuntimeTab") :
        text.index("function _pr92Schema7AtomicAttachmentSubmitExpression")
    ]
    session_check = cleanup.index("if (records.session == null)")
    identity_match = cleanup.index("sessionIdentity !== localIdentity")
    close = cleanup.index("chrome.tabs.remove(tabId)")
    assert session_check < identity_match < close
