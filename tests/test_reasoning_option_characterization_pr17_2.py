from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
PROBE = EXT / "service_worker_reasoning_option_characterization.js"
OBSERVABILITY = EXT / "service_worker_observability.js"
LIVE_GATE = ROOT / "tools" / "pr17_2_reasoning_option_characterization.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_no_tab_harness() -> dict[str, object]:
    prelude = r"""
const registrations = new Map();

function registerNativeTurnDiagnosticHandler(name, matches, handle) {
  registrations.set(name, { matches, handle });
}
async function storedRuntimeTabId() { return null; }
function isChatGPTUrl(url) {
  return typeof url === "string" && url.startsWith("https://chatgpt.com/");
}
globalThis.chrome = {
  tabs: {
    query: async () => []
  }
};
"""
    epilogue = r"""
(async () => {
  const handler = registrations.get("reasoning-option-characterization");
  const ordinaryMatches = handler.matches({ text: "ordinary" });
  const diagnosticMatches = handler.matches({
    characterizeReasoningOptionSurface: true
  });
  const noTab = await handler.handle({
    characterizeReasoningOptionSurface: true,
    targetPolicy: "ACTIVE"
  });

  let rejected = false;
  let rejection = null;
  try {
    await handler.handle({
      characterizeReasoningOptionSurface: true,
      text: "must reject"
    });
  } catch (error) {
    rejected = true;
    rejection = String(error?.message || error);
  }

  console.log(JSON.stringify({
    ordinaryMatches,
    diagnosticMatches,
    noTab,
    rejected,
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


def test_pr17_2_probe_is_loaded_only_as_diagnostic_overlay() -> None:
    observation = _source(OBSERVABILITY)
    probe_name = "service_worker_reasoning_option_characterization.js"

    assert f'importScripts("{probe_name}");' in observation
    assert '"reasoning-option-characterization"' in _source(PROBE)
    assert "registerNativeTurnDiagnosticHandler(" in _source(PROBE)


def test_pr17_2_probe_contains_no_write_or_activation_primitives() -> None:
    source = _source(PROBE)

    for forbidden in (
        "Input.insertText",
        "Input.dispatchMouseEvent",
        "Input.dispatchKeyEvent",
        "DOM.focus",
        ".requestSubmit(",
        ".submit(",
        "chrome.tabs.update",
        "chrome.tabs.create",
        "chrome.windows.update",
    ):
        assert forbidden not in source

    # The background-focus characterization intentionally permits one
    # ephemeral DOM click to open/restore the reasoning menu. It must not
    # broaden into arbitrary click-based product mutation.
    assert source.count(".click(") == 1
    assert source.count("target.click();") == 1
    assert "function _pr172BackgroundDomTriggerClickExpression(" in source

    for contract in (
        "writePerformed: false",
        "textInsertionPerformed: false",
        "focusPerformed: false",
        "clickPerformed: false",
        "optionSelectionAttempted: false",
        "submitAttempted: false",
        "navigationPerformed: false",
        "tabCreated: false",
        "tabActivated: false",
        "automaticWriteRetry: false",
        "fallbackTransport: null",
        "rawDomExported: false",
        "composerTextExported: false",
    ):
        assert contract in source


def test_pr17_2_probe_reports_bounded_direct_option_identity() -> None:
    source = _source(PROBE)

    for field in (
        "INSTANT",
        "MEDIUM",
        "HIGH",
        "EXTRA_HIGH",
        "pickerControl",
        "pickerControlCandidateCount",
        "optionCandidateCount",
        "optionCountsByMode",
        "ariaChecked",
        "ariaSelected",
        "ariaCurrent",
        "ariaExpanded",
        "ariaHaspopup",
        "dataState",
        "insideMenu",
        "insideListbox",
        "insideDialog",
        "centerHitIsSelfOrDescendant",
        "documentVisibilityState",
        "documentHidden",
        "surfaceCount",
        "surfaces",
        "surfaceActionableCount",
        "surfaceActionables",
        "semanticText",
        "classifiedMode",
        "parentRoles",
    ):
        assert field in source

    assert "options: options.slice(0, 32)" in source
    assert "surfaceActionables: surfaceActionables.slice(0, 48)" in source
    assert "innerText.slice(0, 160)" in source
    assert "innerText:" not in source
    assert "textContent" not in source


def test_pr17_2_active_and_runtime_target_policies_are_read_only() -> None:
    source = _source(PROBE)

    assert '"ACTIVE"' in source
    assert '"RUNTIME"' in source
    assert '"stored_runtime_tab"' in source
    assert '"unique_active_chatgpt_tab"' in source
    assert '"last_focused_window_active_chatgpt_tab"' in source
    assert "chrome.windows.getLastFocused()" in source
    assert "chrome.tabs.update" not in source


def test_pr17_2_diagnostic_rejects_ordinary_write_input() -> None:
    result = _run_no_tab_harness()

    assert result["ordinaryMatches"] is False
    assert result["diagnosticMatches"] is True
    assert result["rejected"] is True
    assert result["rejection"] == "PR17_2_REASONING_OPTION_PROBE_MUST_BE_NO_WRITE"

    no_tab = result["noTab"]
    assert isinstance(no_tab, dict)
    assert no_tab["diagnosticOnly"] is True
    assert no_tab["diagnosticTabPresent"] is False
    assert no_tab["diagnosticTabSelectionState"] == "no_existing_chatgpt_tab"
    assert no_tab["writePerformed"] is False
    assert no_tab["clickPerformed"] is False
    assert no_tab["optionSelectionAttempted"] is False
    assert no_tab["tabActivated"] is False


def test_pr17_2_live_gate_sends_only_characterization_fields() -> None:
    source = _source(LIVE_GATE)
    start = source.index("response = provider._characterization_rpc")
    end = source.index("_validate_no_write_contract(response)", start)
    request = source[start:end]

    assert '"characterizeReasoningOptionSurface": True' in request
    assert '"targetPolicy": target_policy' in request
    assert '"text"' not in request
    assert '"conversationId"' not in request
    assert '"browserAuthorityLeaseId"' not in request


def test_pr17_2_background_focus_probe_never_activates_or_changes_value() -> None:
    source = _source(PROBE)

    assert "characterizeBackgroundReasoningSliderFocus" in source
    assert "_pr172CharacterizeBackgroundSliderFocus" in source
    assert "PR17_2_BACKGROUND_FOCUS_REQUIRES_INACTIVE_RUNTIME_TAB" in source
    assert "_pr172BackgroundDomTriggerClick(" in source
    assert re.search(
        r'_pr172BackgroundResolvedSliderSnapshot\(\s*'
        r'debuggee,\s*"focus",\s*selectedModeBefore\s*\)',
        source,
    )
    assert "reasoningValueMutationAttempted: false" in source
    assert "keyDispatchPerformed: false" in source
    assert "mouseDispatchPerformed: false" in source
    assert "conversationWriteAttempted: false" in source
    assert "tabActivated: false" in source
    assert "chrome.tabs.update" not in source
    assert "Input.dispatchKeyEvent" not in source
    assert "Input.dispatchMouseEvent" not in source


def test_pr17_2_background_focus_requires_exact_0_2_slider_and_no_value_drift() -> None:
    source = _source(PROBE)

    assert "slider?.min === 0" in source
    assert "slider?.max === 2" in source
    assert "slider?.stepCount === 3" in source
    assert "selectedModeUnchanged" in source
    assert "focused.now === slider.now" in source
    assert "selectedModeAfterFocus === selectedModeBefore" in source


def test_pr17_2_background_focus_restores_ephemeral_picker_state() -> None:
    source = _source(PROBE)

    assert "openedByProbe" in source
    assert "uiTriggerRestoreAttempted" in source
    assert "uiTriggerRestoreProven" in source
    assert source.count("_pr172BackgroundDomTriggerClick(") >= 2
    assert "__cwaPr172ReasoningTrigger" in source
    assert "retainedReferenceUsed" in source
    assert re.search(
        r'_pr172BackgroundDomTriggerClick\(\s*'
        r'debuggee,\s*selectedModeBefore,\s*true\s*\)',
        source,
    )


def test_pr17_2_background_focus_uses_semantic_composer_fallback() -> None:
    source = _source(PROBE)

    assert "historicalComposer" in source
    assert '[contenteditable="true"][role="textbox"][aria-multiline="true"]' in source
    assert "candidate.closest('main')" in source
    assert "candidate.closest('form')" in source
    assert 'primary?.reason === "composer_missing"' in source
    assert 'primary?.reason === "current_effort_control_missing"' in source
    assert "_pr88InstantEffortRelaxedSliderSnapshot(debuggee, action)" in source


def test_pr17_2_background_focus_can_prove_unique_slider_without_trigger() -> None:
    source = _source(PROBE)

    assert "_pr172BackgroundExactSliderExpression" in source
    assert "_pr172BackgroundExactSliderSnapshot" in source
    assert "'[role=\"slider\"],input[type=\"range\"]'" not in source
    assert "'[role=\"slider\"],input[type=\"range\"]'" not in source
    assert "document.querySelectorAll('[role=\"slider\"],input[type=\"range\"]')" in source
    assert "min===0&&max===2&&now>=0&&now<=2" in source
    assert "now===0?'INSTANT':now===1?'MEDIUM':now===2?'HIGH':null" in source
    assert "exact_slider_mode_mismatch" in source
    assert "unique_exact_slider_value" in source
    assert "focused.now === slider.now" in source


def test_pr17_2_background_focus_tool_has_zero_value_and_write_budgets() -> None:
    tool = _source(ROOT / "tools" / "pr17_2_background_reasoning_slider_focus.py")

    assert '"conversation_write_budget": 0' in tool
    assert '"reasoning_value_mutation_budget": 0' in tool
    assert '"characterizeBackgroundReasoningSliderFocus": True' in tool
    assert '"tabActivated"' in tool
    assert '"reasoningValueMutationAttempted"' in tool
    assert '"keyDispatchPerformed"' in tool
    assert '"mouseDispatchPerformed"' in tool
    assert '"conversationWriteAttempted"' in tool
