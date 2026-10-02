from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
PROBE = EXT / "service_worker_chatgpt_composer_submit_characterization_pr17_1.js"
OBSERVABILITY = EXT / "service_worker_observability.js"
BASE_WORKER = EXT / "service_worker.js"
LIVE_GATE = ROOT / "tools" / "pr17_1_chatgpt_composer_submit_characterization.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_no_tab_harness() -> dict[str, object]:
    prelude = r"""
const registrations = new Map();

function registerNativeTurnDiagnosticHandler(name, matches, handle) {
  if (registrations.has(name)) throw new Error("duplicate:" + name);
  registrations.set(name, { matches, handle });
}

async function storedRuntimeTabId() {
  return null;
}
"""
    epilogue = r"""
(async () => {
  const handler = registrations.get("chatgpt-composer-submit-characterization");
  const ordinaryMatches = handler.matches({ text: "ordinary turn" });
  const diagnosticMatches = handler.matches({
    characterizeChatGPTComposerSubmitSurface: true
  });
  const noTab = await handler.handle({
    characterizeChatGPTComposerSubmitSurface: true
  });

  let writeBearingRejected = false;
  let rejection = null;
  try {
    await handler.handle({
      characterizeChatGPTComposerSubmitSurface: true,
      text: "must never be accepted"
    });
  } catch (error) {
    writeBearingRejected = true;
    rejection = String(error?.message || error);
  }

  console.log(JSON.stringify({
    ordinaryMatches,
    diagnosticMatches,
    noTab,
    writeBearingRejected,
    rejection
  }));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""

    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(prelude)
        handle.write("\n")
        handle.write(_source(PROBE))
        handle.write("\n")
        handle.write(epilogue)
        path = handle.name

    try:
        completed = subprocess.run(
            ["node", path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(completed.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


def test_pr17_1_probe_is_loaded_only_as_diagnostic_overlay() -> None:
    observation = _source(OBSERVABILITY)
    probe_name = "service_worker_chatgpt_composer_submit_characterization_pr17_1.js"

    assert f'importScripts("{probe_name}");' in observation
    assert "registerNativeTurnDiagnosticHandler(" in _source(PROBE)
    assert '"chatgpt-composer-submit-characterization"' in _source(PROBE)


def test_pr17_1_probe_contains_no_product_write_primitives() -> None:
    source = _source(PROBE)

    for forbidden in (
        "Input.insertText",
        "Input.dispatchMouseEvent",
        "Input.dispatchKeyEvent",
        "DOM.focus",
        ".click(",
        ".requestSubmit(",
        ".submit(",
        "chrome.tabs.update",
    ):
        assert forbidden not in source

    for contract in (
        "writePerformed: false",
        "textInsertionPerformed: false",
        "focusPerformed: false",
        "clickPerformed: false",
        "submitAttempted: false",
        "automaticWriteRetry: false",
        "fallbackTransport: null",
        "rawDomExported: false",
        "composerTextExported: false",
    ):
        assert contract in source


def test_pr17_1_probe_reports_bounded_submit_geometry_and_identity() -> None:
    source = _source(PROBE)

    for field in (
        "tagName",
        "role",
        "dataTestid",
        "ariaLabel",
        "type",
        "rect",
        "centerHit",
        "centerHitIsSelfOrDescendant",
        "insideNearestForm",
        "insideDerivedScope",
        "legacySelector",
        "oldResolverSelected",
        "composerCandidates",
        "scopedControls",
        "legacyControls",
    ):
        assert field in source

    assert "innerText" not in source
    assert "textContent" not in source
    assert ".value" not in source


def test_pr17_1_diagnostic_bypasses_ordinary_turns_and_rejects_write_input() -> None:
    result = _run_no_tab_harness()

    assert result["ordinaryMatches"] is False
    assert result["diagnosticMatches"] is True
    assert result["writeBearingRejected"] is True
    assert result["rejection"] == "PR17_1_COMPOSER_SUBMIT_PROBE_MUST_BE_NO_WRITE"

    no_tab = result["noTab"]
    assert isinstance(no_tab, dict)
    assert no_tab["diagnosticOnly"] is True
    assert no_tab["runtimeTabPresent"] is False
    assert no_tab["writePerformed"] is False
    assert no_tab["textInsertionPerformed"] is False
    assert no_tab["focusPerformed"] is False
    assert no_tab["clickPerformed"] is False
    assert no_tab["submitAttempted"] is False
    assert no_tab["automaticWriteRetry"] is False
    assert no_tab["fallbackTransport"] is None


def test_pr17_1_live_gate_sends_only_no_write_characterization_flag() -> None:
    source = _source(LIVE_GATE)
    start = source.index("response = provider._characterization_rpc")
    end = source.index("_validate_no_write_contract(response)", start)
    request_block = source[start:end]

    assert '"characterizeChatGPTComposerSubmitSurface": True' in request_block
    assert '"text"' not in request_block
    assert '"conversationId"' not in request_block
    assert '"attachmentPaths"' not in request_block
    assert '"browserAuthorityLeaseId"' not in request_block


def test_pr17_1_does_not_widen_production_submit_resolver_before_evidence() -> None:
    source = _source(BASE_WORKER)
    start = source.index("async function querySendButtonPoint")
    end = source.index("async function _cwaBaseWaitForSendButtonPoint", start)
    block = source[start:end]

    assert 'button[data-testid="send-button"]' in block
    assert 'button[data-testid="composer-submit-button"]' in block
    assert 'button[aria-label="Send prompt"]' in block
    assert 'button[aria-label="Send message"]' in block
    assert 'button[role="button"]' not in block
    assert '[role="button"]' not in block
