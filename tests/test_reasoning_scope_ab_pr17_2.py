from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
PROFILE = EXT / "service_worker_model_profile_selection_pr8_10.js"
TOOL = ROOT / "tools" / "pr17_2_reasoning_scope_ab_probe.py"


def _profile_source() -> str:
    return PROFILE.read_text(encoding="utf-8")


def _tool_module():
    spec = importlib.util.spec_from_file_location("pr17_2_scope_tool", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _obs(mode: str) -> dict[str, object]:
    return {"selectedMode": mode}


def test_pr17_2_scope_observation_is_read_only_and_stable() -> None:
    source = _profile_source()
    start = source.index("async function _pr172ReasoningScopeObservation")
    end = source.index("\nasync function _pr810StoredRecord", start)
    block = source[start:end]

    assert "characterizeReasoningScopeObservation" in source
    assert "conversationWriteCount" in block
    assert "PR17_2_SCOPE_OBSERVATION_WRITE_OBSERVED" in block
    assert "_pr172WaitForStableScopeMode" in block
    assert "stableCount >= 3" in source

    assert "Input.insertText" not in block
    assert "Input.dispatchKeyEvent" not in block
    assert "_pr88InstantEffortDispatchHome" not in block
    assert "_pr810DispatchKey" not in block
    assert "_pr88InstantEffortOpenPickerWithFallback" not in block
    assert '"DOM.focus"' not in block


def test_pr17_2_scope_observation_supports_persistent_and_fresh_renderers() -> None:
    source = _profile_source()
    start = source.index("async function _pr172ReasoningScopeObservation")
    end = source.index("\nasync function _pr810StoredRecord", start)
    block = source[start:end]

    assert "ensureRuntimeTab(conversationId)" in block
    assert "chrome.tabs.create({url: targetUrl, active: false})" in block
    assert "await chrome.tabs.remove(tabId)" in block
    assert "temporaryTabCreated" in block
    assert "temporaryTabClosed" in block
    assert "PR17_2_SCOPE_OBSERVATION_TAB_MUST_REMAIN_BACKGROUND" in block
    assert "PR17_2_SCOPE_OBSERVATION_TAB_ACTIVATED" in block


def test_pr17_2_scope_gate_budgets_three_writes_and_seven_reads() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"product_write_budget": 3' in source
    assert '"read_only_observation_count": 7' in source
    assert '"automatic_write_retry": False' in source
    assert "PR17_2_SCOPE_INITIAL_RUNTIME_TAB_MUST_BE_ABSENT" in source
    assert "--acknowledge-live-writes" in source
    assert "this gate performs exactly three ChatGPT product writes" in source


def test_pr17_2_scope_classifies_durable_conversation_local_state() -> None:
    module = _tool_module()
    persistent = {
        "a_after_b_setup": _obs("HIGH"),
        "b_after_setup": _obs("MEDIUM"),
        "a_after_mutation": _obs("INSTANT"),
        "b_after_a_mutation": _obs("MEDIUM"),
        "new_chat_after_a_mutation": _obs("INSTANT"),
    }
    fresh = {
        "a_after_mutation": _obs("INSTANT"),
        "b_after_a_mutation": _obs("MEDIUM"),
        "new_chat_after_a_mutation": _obs("INSTANT"),
    }

    result = module._classify(persistent=persistent, fresh=fresh)

    assert result["verdict"] == "CONVERSATION_LOCAL_DURABLE"
    assert result["setup_isolation_same_renderer"] is True
    assert result["mutation_isolation_same_renderer"] is True
    assert result["durable_isolation_fresh_renderers"] is True


def test_pr17_2_scope_classifies_shared_persistent_runtime_state() -> None:
    module = _tool_module()
    persistent = {
        "a_after_b_setup": _obs("MEDIUM"),
        "b_after_setup": _obs("MEDIUM"),
        "a_after_mutation": _obs("INSTANT"),
        "b_after_a_mutation": _obs("INSTANT"),
        "new_chat_after_a_mutation": _obs("INSTANT"),
    }
    fresh = {
        "a_after_mutation": _obs("INSTANT"),
        "b_after_a_mutation": _obs("INSTANT"),
        "new_chat_after_a_mutation": _obs("INSTANT"),
    }

    result = module._classify(persistent=persistent, fresh=fresh)

    assert result["verdict"] == "SHARED_ACROSS_CONVERSATIONS_IN_PERSISTENT_RUNTIME"
    assert result["setup_isolation_same_renderer"] is False
    assert result["mutation_isolation_same_renderer"] is False
