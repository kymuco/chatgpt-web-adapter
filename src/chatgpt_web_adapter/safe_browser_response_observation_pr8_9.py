from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from typing import Any, Callable

from .browser_authority_live_characterization import (
    BrowserAuthorityCharacterizationProvider,
)
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
SCHEMA_VERSION = 1
PROBE_CONTEXT = "pr8_9_safe_browser_response_streaming_characterization"
DEFAULT_PROMPT = (
    "PR8.9 safe browser response streaming characterization. Produce exactly 32 "
    "numbered plain-text lines. Each line must be one neutral sentence of roughly "
    "12 to 18 words about mathematics, computing, measurement, or engineering. "
    "Start line 1 with PR8_9_BROWSER_STREAM_START and end line 32 with "
    "PR8_9_BROWSER_STREAM_END. Do not use a code block."
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _failure(error: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": type(error).__name__,
        "message": str(error),
        "automatic_retry_attempted": False,
    }
    for name in (
        "failure_kind",
        "write_may_have_been_submitted",
        "reconciliation_required",
        "automatic_retry_allowed",
        "manual_retry_safe_after_repair",
        "request_stage",
    ):
        if hasattr(error, name):
            payload[name] = getattr(error, name)
    return payload


class SafeBrowserResponseObservationProvider(BrowserAuthorityCharacterizationProvider):
    """Inject one diagnostic flag into the next ordinary browser-owned turn.

    The public/production provider contract is unchanged. This subclass is only
    used by the PR8.9 Candidate-B live harness and retains the bounded safe
    metadata that the extension returned for that one turn.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stream_probe_armed = False
        self._stream_probe_turn_count = 0
        self.last_safe_browser_stream: dict[str, Any] | None = None

    def arm_stream_probe(self) -> None:
        if self._stream_probe_armed:
            raise RuntimeError("PR8_9_BROWSER_STREAM_PROBE_ALREADY_ARMED")
        self._stream_probe_armed = True
        self._stream_probe_turn_count = 0
        self.last_safe_browser_stream = None

    def disarm_stream_probe(self) -> None:
        self._stream_probe_armed = False

    def _rpc(self, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        outgoing = dict(payload)
        is_product_turn = (
            outgoing.get("type") == "turn"
            and isinstance(outgoing.get("text"), str)
            and bool(outgoing["text"].strip())
        )
        injected = self._stream_probe_armed and is_product_turn
        if injected:
            if self._stream_probe_turn_count >= 1:
                raise RuntimeError("PR8_9_BROWSER_STREAM_PRODUCT_WRITE_BUDGET_EXCEEDED")
            outgoing["characterizeSafeBrowserResponseStreaming"] = True

        response = super()._rpc(outgoing, timeout=timeout)
        if injected:
            self._stream_probe_turn_count += 1
            value = response.get("safeBrowserResponseStreaming")
            self.last_safe_browser_stream = (
                copy.deepcopy(value) if isinstance(value, dict) else None
            )
        return response

    def support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        response = self._characterization_rpc(
            {
                "characterizeSafeBrowserResponseStreamingSupport": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        return {
            "supported": response.get("safeBrowserResponseStreamingSupported") is True,
            "schema": _optional_int(response.get("schemaVersion")),
            "cdp_method": _optional_text(response.get("cdpMethod")),
            "experimental_cdp_method": response.get("experimentalCdpMethod") is True,
        }


def summarize_safe_browser_stream(
    stream: dict[str, Any] | None,
    *,
    final_text: str,
) -> dict[str, Any]:
    stream = dict(stream or {})
    observations = [
        dict(item)
        for item in stream.get("observations", [])
        if isinstance(item, dict)
    ]
    first = observations[0] if observations else None
    last = observations[-1] if observations else None
    final_digest = _sha256(final_text) if final_text else None
    last_digest = _optional_text(last.get("textSha256")) if last else None
    last_length = _optional_int(last.get("textLength")) if last else None

    if last_digest and final_digest and last_digest == final_digest and last_length == len(final_text):
        reconciliation = "EXACT_MATCH"
    elif observations and final_text:
        reconciliation = "STREAM_INCOMPLETE"
    else:
        reconciliation = "UNAVAILABLE"

    pre_network = stream.get("preNetworkCompleteTextObserved") is True
    first_text_ms = _optional_int(stream.get("firstTextObservedMs"))
    network_complete_ms = _optional_int(stream.get("loadingFinishedMs"))

    return {
        "source": _optional_text(stream.get("source")),
        "experimental_cdp_method": stream.get("experimentalCdpMethod") is True,
        "conversation_request_observed": stream.get("conversationRequestObserved") is True,
        "response_status": _optional_int(stream.get("responseStatus")),
        "response_mime_type": _optional_text(stream.get("responseMimeType")),
        "stream_resource_content_attempted": (
            stream.get("streamResourceContentAttempted") is True
        ),
        "stream_resource_content_supported": (
            stream.get("streamResourceContentSupported") is True
        ),
        "stream_resource_content_error": _optional_text(
            stream.get("streamResourceContentError")
        ),
        "buffered_byte_length": _optional_int(stream.get("bufferedByteLength")) or 0,
        "data_event_count": _optional_int(stream.get("dataEventCount")) or 0,
        "data_byte_length": _optional_int(stream.get("dataByteLength")) or 0,
        "sse_event_count": _optional_int(stream.get("sseEventCount")) or 0,
        "json_event_count": _optional_int(stream.get("jsonEventCount")) or 0,
        "assistant_text_event_count": (
            _optional_int(stream.get("assistantTextEventCount")) or 0
        ),
        "observation_count": len(observations),
        "revision_count": sum(item.get("kind") == "REVISION" for item in observations),
        "delta_count": sum(item.get("kind") == "DELTA" for item in observations),
        "pre_network_complete_text_observed": pre_network,
        "first_text_observed_ms": first_text_ms,
        "last_text_observed_ms": _optional_int(stream.get("lastTextObservedMs")),
        "network_complete_ms": network_complete_ms,
        "first_text_lead_before_network_complete_ms": _optional_int(
            stream.get("firstTextLeadBeforeNetworkCompleteMs")
        ),
        "first_observation": first,
        "last_observation": last,
        "observations_truncated": stream.get("observationsTruncated") is True,
        "sse_buffer_truncated": stream.get("sseBufferTruncated") is True,
        "decode_error_count": _optional_int(stream.get("decodeErrorCount")) or 0,
        "processing_error_count": _optional_int(stream.get("processingErrorCount")) or 0,
        "final_response_length": len(final_text),
        "final_response_sha256": final_digest,
        "stream_canonical_reconciliation": reconciliation,
        "useful_safe_browser_response_observation_supported": bool(
            stream.get("streamResourceContentSupported") is True
            and observations
            and pre_network
            and first_text_ms is not None
            and network_complete_ms is not None
            and first_text_ms < network_complete_ms
        ),
    }


class SafeBrowserResponseCharacterizationRunner:
    """Run exactly one ordinary product turn with browser-local stream reduction."""

    def __init__(
        self,
        runtime: Any,
        provider: SafeBrowserResponseObservationProvider,
        read_client: Any,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.runtime = runtime
        self.provider = provider
        self.read_client = read_client
        self._monotonic = monotonic

    def run(
        self,
        *,
        conversation: str,
        timeout: float = DEFAULT_TIMEOUT,
        prompt: str = DEFAULT_PROMPT,
    ) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        conversation = conversation.strip()

        baseline = self.read_client.get_status(conversation)
        if getattr(baseline, "status", None) != "completed":
            raise RuntimeError("PR8_9_BROWSER_STREAM_BASELINE_NOT_COMPLETED")

        support = self.provider.support(timeout=min(5.0, timeout))
        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.9.2",
            "probe_context": PROBE_CONTEXT,
            "conversation": conversation,
            "schema": SCHEMA_VERSION,
            "product_write_budget": 1,
            "write_attempts": 1,
            "write_completions": 0,
            "automatic_write_retry": False,
            "support": support,
        }

        started = self._monotonic()
        event_times: dict[str, int] = {}

        def elapsed_ms() -> int:
            return round((self._monotonic() - started) * 1000)

        def on_event(event: dict[str, Any]) -> None:
            if not isinstance(event, dict):
                return
            event_type = _optional_text(event.get("type"))
            if event_type and event_type not in event_times:
                event_times[event_type] = elapsed_ms()

        self.provider.arm_stream_probe()
        try:
            execution = self.runtime.send_text_observed(
                prompt,
                conversation=conversation,
                timeout=timeout,
                poll_interval=0.5,
                conversation_mode="normal",
                browser_authority_policy="PERSISTENT",
                on_event=on_event,
            )
        except BaseException as error:
            report["failure"] = _failure(error)
            report["event_times_ms"] = event_times
            return report
        finally:
            self.provider.disarm_stream_probe()

        report["write_completions"] = 1
        report["response_returned_ms"] = elapsed_ms()
        report["event_times_ms"] = event_times

        response = getattr(execution, "response", None)
        final_text = str(getattr(response, "text", "") or "")
        stream = self.provider.last_safe_browser_stream
        report["safe_browser_response_streaming"] = copy.deepcopy(stream)
        summary = summarize_safe_browser_stream(stream, final_text=final_text)
        report["summary"] = summary
        report["architecture_invalidation_check"] = {
            "current_browser_owned_write_path_invalidated": False,
            "production_streaming_enabled": False,
            "candidate_a_incremental_canonical_observation": "CLOSED_NOT_INCREMENTAL",
            "candidate_b_safe_browser_response_observation": (
                "SUPPORTED"
                if summary["useful_safe_browser_response_observation_supported"]
                else "NOT_PROVEN"
            ),
            "next_source_if_not_proven": "RENDERED_PAGE_OBSERVATION",
        }
        report["ok"] = True
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PR8.9.2 bounded characterization of safe browser response-stream "
            "assistant text during exactly one existing-conversation product turn."
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.acknowledge_live_writes:
        raise SystemExit(
            "Refusing live characterization without --acknowledge-live-writes"
        )

    write_client = ChatGPTWebClient()
    read_client = ChatGPTWebClient(
        auth=copy.deepcopy(write_client.auth),
        timeout=max(10, int(args.timeout)),
        auto_refresh_auth=False,
        persist_refreshed_auth=False,
        auto_login=False,
        auto_sentinel=False,
    )
    provider = SafeBrowserResponseObservationProvider()
    runtime = assemble_product_runtime(
        client=write_client,
        provider=provider,
        browser_authority_policy="PERSISTENT",
    )
    report = SafeBrowserResponseCharacterizationRunner(
        runtime,
        provider,
        read_client,
    ).run(
        conversation=args.conversation,
        timeout=args.timeout,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())