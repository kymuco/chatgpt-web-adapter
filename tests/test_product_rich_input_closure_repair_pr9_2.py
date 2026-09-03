from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
CLOSURE = EXT / "service_worker_rich_input_closure_repair_pr9_2.js"
WRITE = EXT / "service_worker_runtime_write.js"


def test_schema_6_closure_overlay_is_loaded_last():
    write = WRITE.read_text(encoding="utf-8")
    primary = 'importScripts("service_worker_rich_input_pr9_2.js");'
    deadline = 'importScripts("service_worker_rich_input_deadline_repair_pr9_2.js");'
    closure = 'importScripts("service_worker_rich_input_closure_repair_pr9_2.js");'

    assert primary in write
    assert deadline in write
    assert closure in write
    assert write.index(primary) < write.index(deadline) < write.index(closure)


def test_schema_6_rich_submit_uses_page_deadline_guard_not_raw_cdp_input():
    text = CLOSURE.read_text(encoding="utf-8")

    assert "const PR92_CLOSURE_REPAIR_SCHEMA = 6;" in text
    assert 'PR92_PAGE_GUARDED_SUBMIT_PRIMITIVE = "PAGE_DEADLINE_GUARDED_SEND_BUTTON_CLICK"' in text
    assert "PR9_2_RICH_INPUT_RAW_MOUSE_SUBMIT_FORBIDDEN" in text
    assert "PR9_2_RICH_INPUT_RAW_ENTER_SUBMIT_FORBIDDEN" in text
    assert "_pr92ClosurePageGuardedSubmitExpression" in text
    assert "Date.now() >= deadlineEpochMs" in text
    assert "button.click();" in text
    assert 'strategy: "page_deadline_guarded_send_button_click"' in text
    assert "richInputRawCdpInputSubmitDisabled: true" in text
    assert "richInputEnterFallbackEnabled: false" in text
    assert "lateProtectedSubmitExecutionPreventedByPageDeadline: true" in text

    guarded_submit = text[
        text.index("submitOfficialPageTurn = async function _pr92ClosurePageDeadlineGuardedSubmit") :
    ]
    guarded_submit = guarded_submit.split("executeNativeTurn = async function", 1)[0]
    assert 'Input.dispatchMouseEvent' not in guarded_submit
    assert 'Input.dispatchKeyEvent' not in guarded_submit


def test_schema_6_attachment_count_requires_page_owned_composer_evidence_after_readiness():
    text = CLOSURE.read_text(encoding="utf-8")

    assert 'PR92_PAGE_ATTACHMENT_EVIDENCE_SOURCE = "PAGE_OWNED_COMPOSER_ATTACHMENT_STATE"' in text
    assert "PR92_PAGE_ATTACHMENT_STABLE_POLLS = 2" in text
    assert "_pr92ClosureWaitForPageOwnedAttachmentEvidence" in text
    assert "_pr92ClosureReadPageOwnedAttachmentEvidence" in text
    assert "PR9_2_PAGE_ATTACHMENT_REJECTED" in text
    assert "PR9_2_PAGE_ATTACHMENT_COUNT_MISMATCH" in text
    assert "PR9_2_POST_READINESS_ATTACHMENT_EVIDENCE_MISMATCH" in text
    assert "preSubmitAttachmentRevalidation: true" in text
    assert "postSendReadinessAttachmentRevalidation: true" in text
    assert "attachmentEvidenceStablePollCount" in text
    assert "attachmentCountEvidence: PR92_PAGE_ATTACHMENT_EVIDENCE_SOURCE" in text

    staging = text.index("_pr92ClosurePriorStageOfficialPageAttachments(")
    page_evidence = text.index("_pr92ClosureWaitForPageOwnedAttachmentEvidence(", staging)
    returned_count = text.index("return pageOwnedCount;", page_evidence)
    assert staging < page_evidence < returned_count

    submit = text.index(
        "submitOfficialPageTurn = async function _pr92ClosurePageDeadlineGuardedSubmit"
    )
    pre_submit_evidence = text.index(
        "_pr92ClosureWaitForPageOwnedAttachmentEvidence(", submit
    )
    send_ready = text.index("point = await waitForSendButtonPoint", pre_submit_evidence)
    post_readiness_evidence = text.index(
        "_pr92ClosureWaitForPageOwnedAttachmentEvidence(", send_ready
    )
    page_click = text.index(
        "_pr92ClosurePageGuardedSubmitExpression(", post_readiness_evidence
    )
    assert submit < pre_submit_evidence < send_ready < post_readiness_evidence < page_click
