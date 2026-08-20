from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.post_answer_tail_latency_pr8_11 import PostAnswerTailTimingProvider


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"
SOURCE = EXTENSION / "service_worker_early_product_completion_pr8_11_1.js"


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_observability_loads_pr8111_after_pr811() -> None:
    source = (EXTENSION / "service_worker_observability.js").read_text(encoding="utf-8")
    tail = 'importScripts("service_worker_post_answer_tail_timing_pr8_11.js");'
    early = 'importScripts("service_worker_early_product_completion_pr8_11_1.js");'
    assert tail in source and early in source
    assert source.index(tail) < source.index(early)


def test_pr8111_is_read_only_characterization() -> None:
    source = _source()
    assert "changesWriteSemantics: false" in source
    assert "changesCanonicalFinality: false" in source
    assert "readOnlyCharacterization: true" in source
    assert "Input.insertText" not in source
    assert "Input.dispatchMouseEvent" not in source
    assert "Input.dispatchKeyEvent" not in source
    assert "submitOfficialPageTurn" not in source


def test_pr8111_observes_terminal_and_composer_signals() -> None:
    source = _source()
    for token in (
        "assistantFinishReasonAt",
        "assistantEndTurnAt",
        "assistantIsCompleteAt",
        "assistantCompletedStatusAt",
        "messageMarkerAt",
        "streamHandoffAt",
        "doneSentinelAt",
        "firstComposerReadyAfterTextAt",
        "consecutiveComposerReadyAfterTextAt",
        "networkCompleteAt",
    ):
        assert token in source
    assert "queryComposerReadiness(debuggee)" in source
    assert "PR8111_COMPOSER_POLL_INTERVAL_MS = 100" in source


def test_pr8111_understands_pr89_patch_terminal_updates() -> None:
    source = _source()
    assert 'path === "/message/metadata"' in source
    assert 'path === "/message/end_turn"' in source
    assert 'path === "/message/status"' in source
    assert "streamContext?.patchAssistantActive === true" in source
    assert '"v", "value"' in source


def test_pr8111_composer_poll_is_gated_after_assistant_text() -> None:
    source = _source()
    poll_start = source.index("async function _pr8111PollComposerReadiness")
    poll_end = source.index("\nexecuteOfficialPageTurn =", poll_start)
    block = source[poll_start:poll_end]
    assert "Number.isFinite(context.lastAssistantTextObservedAt)" in block
    assert "consecutiveReady >= 2" in block


def test_pr8111_does_not_export_raw_text_or_sse() -> None:
    source = _source()
    record_start = source.index("function _pr8111Record(context)")
    record_end = source.index("\nexecuteNativeTurn =", record_start)
    record = source[record_start:record_end]
    assert "sseBuffer" not in record
    assert "responseBody" not in record
    assert "textPreview" not in record
    assert "content.parts" not in record
    assert "prompt" not in record.lower()
    assert "assistantFinishReason" in record
    assert "assistantTextObservationCount" in record


def test_earliest_terminal_excludes_nonterminal_handoff_markers() -> None:
    source = _source()
    start = source.index("function _pr8111FirstTerminal(context)")
    end = source.index("\nfunction _pr8111Record(context)", start)
    block = source[start:end]
    assert '"assistant_finish_reason"' in block
    assert '"assistant_end_turn"' in block
    assert '"done_sentinel"' in block
    assert '"stream_handoff"' not in block
    assert '"message_marker"' not in block


def test_early_completion_provider_normalizes_bounded_record(monkeypatch) -> None:
    provider = PostAnswerTailTimingProvider()

    def fake_rpc(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == "lease-1"
        assert payload["characterizeEarlyProductCompletion"] is True
        return {
            "earlyProductCompletionSupported": True,
            "earlyProductCompletion": {
                "schemaVersion": 1,
                "browserAuthorityLeaseId": "lease-1",
                "assistantTextObservationCount": 20,
                "composerProbeCount": 11,
                "composerProbeErrorCount": 0,
                "characterizationErrorCount": 0,
                "lastAssistantTextObservedMs": 22000,
                "assistantFinishReasonObservedMs": 22010,
                "assistantFinishReason": "stop",
                "assistantEndTurnObservedMs": 22012,
                "consecutiveComposerReadyAfterTextMs": 22200,
                "networkCompleteMs": 25000,
                "earliestTerminalSignalKind": "assistant_finish_reason",
                "earliestTerminalSignalMs": 22010,
                "lastTextToEarliestTerminalSignalMs": 10,
                "lastTextToComposerReadyMs": 200,
                "earliestTerminalSignalToNetworkCompleteMs": 2990,
                "composerReadyToNetworkCompleteMs": 2800,
                "lastTextToNetworkCompleteMs": 3000,
            },
        }

    monkeypatch.setattr(provider, "_characterization_rpc", fake_rpc)
    record = provider.early_completion_for_lease("lease-1")
    assert record["schema"] == 1
    assert record["assistant_text_observation_count"] == 20
    assert record["assistant_finish_reason"] == "stop"
    assert record["earliest_terminal_signal_kind"] == "assistant_finish_reason"
    assert record["last_text_to_earliest_terminal_signal_ms"] == 10
    assert record["last_text_to_composer_ready_ms"] == 200
    assert record["composer_ready_to_network_complete_ms"] == 2800


def test_tail_timing_report_includes_pr8111_when_available(monkeypatch) -> None:
    provider = PostAnswerTailTimingProvider()

    def fake_rpc(payload, *, timeout):
        if payload.get("characterizePostAnswerTailTiming") is True:
            return {
                "postAnswerTailTimingSupported": True,
                "postAnswerTailTiming": {
                    "schemaVersion": 1,
                    "browserAuthorityLeaseId": "lease-1",
                    "assistantTextObservationCount": 20,
                    "lastTextToNetworkCompleteMs": 3000,
                },
            }
        if payload.get("characterizeEarlyProductCompletion") is True:
            return {
                "earlyProductCompletionSupported": True,
                "earlyProductCompletion": {
                    "schemaVersion": 1,
                    "browserAuthorityLeaseId": "lease-1",
                    "earliestTerminalSignalKind": "assistant_finish_reason",
                    "lastTextToEarliestTerminalSignalMs": 5,
                    "composerReadyToNetworkCompleteMs": 2700,
                },
            }
        raise AssertionError(payload)

    monkeypatch.setattr(provider, "_characterization_rpc", fake_rpc)
    record = provider.timing_for_lease("lease-1")
    early = record["early_product_completion"]
    assert early["available"] is True
    assert early["earliest_terminal_signal_kind"] == "assistant_finish_reason"
    assert early["composer_ready_to_network_complete_ms"] == 2700
