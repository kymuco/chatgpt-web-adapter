from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import chatgpt_web_adapter.cli as cli
from chatgpt_web_adapter.post_answer_tail_latency_pr8_11 import (
    PostAnswerTailTimingProvider,
    StandaloneTailTimingObserver,
)

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "src" / "chatgpt_web_adapter" / "browser_native_extension"


def test_extension_loads_tail_timing_after_revision_safe_delivery() -> None:
    source = (EXTENSION / "service_worker_observability.js").read_text(encoding="utf-8")
    delivery = 'importScripts("service_worker_revision_safe_text_delivery_pr8_9.js");'
    tail = 'importScripts("service_worker_post_answer_tail_timing_pr8_11.js");'
    assert delivery in source and tail in source
    assert source.index(delivery) < source.index(tail)


def test_tail_overlay_is_numeric_observability_only() -> None:
    source = (EXTENSION / "service_worker_post_answer_tail_timing_pr8_11.js").read_text(
        encoding="utf-8"
    )
    assert "lastTextToNetworkCompleteMs" in source
    assert "networkCompleteToNativeCompleteMs" in source
    assert "lastTextToNativeCompleteMs" in source
    assert "characterizePostAnswerTailTiming" in source
    assert "changesWriteSemantics: false" in source
    assert "Input.insertText" not in source
    assert "Input.dispatchMouseEvent" not in source
    assert "raw SSE" in source


def test_tail_provider_normalizes_bounded_record(monkeypatch) -> None:
    provider = PostAnswerTailTimingProvider()

    def fake_rpc(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == "lease-1"
        return {
            "postAnswerTailTimingSupported": True,
            "postAnswerTailTiming": {
                "schemaVersion": 1,
                "browserAuthorityLeaseId": "lease-1",
                "assistantTextObservationCount": 4,
                "writeDelegatedMs": 100,
                "lastAssistantTextObservedMs": 900,
                "networkCompleteMs": 1500,
                "nativeCompleteMs": 2250,
                "lastTextToNetworkCompleteMs": 600,
                "networkCompleteToNativeCompleteMs": 750,
                "lastTextToNativeCompleteMs": 1350,
            },
        }

    monkeypatch.setattr(provider, "_characterization_rpc", fake_rpc)
    record = provider.timing_for_lease("lease-1")
    assert record["schema"] == 1
    assert record["assistant_text_observation_count"] == 4
    assert record["last_text_to_network_complete_ms"] == 600
    assert record["network_complete_to_native_complete_ms"] == 750
    assert record["last_text_to_native_complete_ms"] == 1350


def test_local_observer_measures_stream_to_return_tail() -> None:
    values = iter([10.0, 10.1, 10.2, 10.8, 11.4, 11.5, 11.51, 11.52])
    forwarded = []
    observer = StandaloneTailTimingObserver(forwarded.append, monotonic=lambda: next(values))

    observer.on_event({"type": "browser_native_turn_started"})
    observer.on_event({"type": "assistant_text_snapshot", "sequence": 1, "text": "a"})
    observer.on_event({"type": "assistant_text_delta", "sequence": 2, "delta": "b"})
    observer.on_event({"type": "browser_native_write_completed"})
    observer.on_event({"type": "canonical_text_finalized", "text": "ab"})
    observer.on_event({"type": "browser_native_readback_completed"})
    observer.mark_runtime_return()

    report = observer.report()
    assert len(forwarded) == 6
    assert report["local_text_event_count"] == 2
    assert report["local_tail_deltas_ms"]["last_text_to_write_completed"] == 600
    assert report["local_tail_deltas_ms"]["write_completed_to_canonical_finalized"] == 100
    assert report["local_tail_deltas_ms"]["last_text_to_runtime_return"] == 720


def _execution():
    return SimpleNamespace(
        transport="browser-owned",
        response=SimpleNamespace(
            text="done",
            title="Conversation",
            conversation=SimpleNamespace(
                conversation_id="conversation-1",
                message_id="assistant-1",
                finish_reason="stop",
            ),
            request=SimpleNamespace(observed_model="gpt-test"),
            metrics=SimpleNamespace(backend_status=200),
        ),
        observation=SimpleNamespace(
            to_dict=lambda: {"browser_authority_lease_id": "lease-1"}
        ),
        provenance=SimpleNamespace(to_dict=lambda: {}),
    )


class _Runtime:
    def send_text_observed(self, text, **kwargs):
        on_event = kwargs["on_event"]
        on_event({"type": "browser_native_turn_started"})
        on_event({"type": "assistant_text_snapshot", "sequence": 1, "text": "done"})
        on_event({"type": "browser_native_write_completed"})
        on_event({"type": "canonical_text_finalized", "text": "done"})
        on_event({"type": "browser_native_readback_completed"})
        return _execution()


def test_cli_timings_require_stream() -> None:
    args = cli._build_parser().parse_args(["send", "hello", "--timings"])
    assert args.timings is True
    assert args.stream is False


def test_cli_stream_timings_print_browser_record_to_stderr(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "assemble_product_runtime", lambda **kwargs: _Runtime())

    class FakeTailProvider:
        def timing_for_lease(self, lease_id):
            assert lease_id == "lease-1"
            return {
                "schema": 1,
                "browser_authority_lease_id": lease_id,
                "last_text_to_network_complete_ms": 450,
                "network_complete_to_native_complete_ms": 750,
                "last_text_to_native_complete_ms": 1200,
            }

    monkeypatch.setattr(cli, "PostAnswerTailTimingProvider", FakeTailProvider)

    code = cli.main(["send", "hello", "--stream", "--timings"])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "done\n"
    diagnostic = json.loads(captured.err)
    browser = diagnostic["post_answer_tail_timing"]["browser_tail_timing"]
    assert browser["available"] is True
    assert browser["last_text_to_network_complete_ms"] == 450
    assert browser["network_complete_to_native_complete_ms"] == 750
