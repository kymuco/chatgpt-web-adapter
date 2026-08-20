from __future__ import annotations

import argparse
import copy
import hashlib
import json
import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable

from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .client import ChatGPTWebClient
from .product_runtime import assemble_product_runtime

DEFAULT_TIMEOUT = 150.0
DEFAULT_POLL_INTERVAL = 0.25
SCHEMA_VERSION = 1
PROBE_CONTEXT = "pr8_9_incremental_canonical_partial_text_characterization"
DEFAULT_PROMPT = (
    "PR8.9 canonical streaming characterization. Produce exactly 24 numbered plain-text "
    "lines. Each line must be one neutral sentence of roughly 12 to 18 words about "
    "mathematics, computing, or measurement. Start line 1 with PR8_9_STREAM_PROBE_START "
    "and end line 24 with PR8_9_STREAM_PROBE_END. Do not use a code block."
)


class TextObservationKind(str, Enum):
    SNAPSHOT = "SNAPSHOT"
    DELTA = "DELTA"
    REVISION = "REVISION"


class StreamCanonicalReconciliation(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    CANONICAL_EXTENDS_STREAM = "CANONICAL_EXTENDS_STREAM"
    STREAM_REVISED_BY_CANONICAL = "STREAM_REVISED_BY_CANONICAL"
    STREAM_INCOMPLETE = "STREAM_INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _preview(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _message_key(message: Any) -> str | None:
    message_id = _optional_text(getattr(message, "message_id", None))
    if message_id is not None:
        return message_id
    node_id = _optional_text(getattr(message, "node_id", None))
    return f"node:{node_id}" if node_id is not None else None


def _status_fields(status: Any) -> tuple[str | None, str | None]:
    return (
        _optional_text(getattr(status, "status", None)),
        _optional_text(getattr(status, "message_id", None)),
    )


def _message_finalized(status: Any, message: Any) -> bool:
    status_value, status_message_id = _status_fields(status)
    message_id = _optional_text(getattr(message, "message_id", None))
    return (
        status_value == "completed"
        and message_id is not None
        and status_message_id == message_id
    )


@dataclass(frozen=True)
class CanonicalTextObservation:
    sequence: int
    kind: TextObservationKind
    observed_at_ms: int
    message_key: str
    message_id: str | None
    text_length: int
    text_sha256: str
    text_preview: str
    delta_length: int | None
    delta_sha256: str | None
    delta_preview: str | None
    previous_text_sha256: str | None
    finish_reason: str | None
    canonical_status: str | None
    canonical_status_message_id: str | None
    finality_proven_at_observation: bool
    write_in_flight: bool

    @property
    def pre_final(self) -> bool:
        return not self.finality_proven_at_observation

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["pre_final"] = self.pre_final
        return payload


class RevisionSafeCanonicalTracker:
    """Classify canonical text changes without assuming append-only behavior."""

    def __init__(self, baseline_message_keys: set[str] | None = None) -> None:
        self.baseline_message_keys = set(baseline_message_keys or ())
        self._last_text_by_key: dict[str, str] = {}
        self._observations: list[CanonicalTextObservation] = []

    @property
    def observations(self) -> tuple[CanonicalTextObservation, ...]:
        return tuple(self._observations)

    def observe(
        self,
        message: Any,
        *,
        status: Any,
        observed_at_ms: int,
        write_in_flight: bool,
    ) -> CanonicalTextObservation | None:
        key = _message_key(message)
        if key is None or key in self.baseline_message_keys:
            return None
        text = getattr(message, "text", "")
        text = "" if text is None else str(text)
        if not text.strip():
            return None

        previous = self._last_text_by_key.get(key)
        if previous == text:
            return None

        if previous is None:
            kind = TextObservationKind.SNAPSHOT
            delta = None
        elif text.startswith(previous):
            kind = TextObservationKind.DELTA
            delta = text[len(previous) :]
        else:
            kind = TextObservationKind.REVISION
            delta = None

        status_value, status_message_id = _status_fields(status)
        finalized = _message_finalized(status, message)
        observation = CanonicalTextObservation(
            sequence=len(self._observations) + 1,
            kind=kind,
            observed_at_ms=max(0, int(observed_at_ms)),
            message_key=key,
            message_id=_optional_text(getattr(message, "message_id", None)),
            text_length=len(text),
            text_sha256=_sha256(text),
            text_preview=_preview(text),
            delta_length=len(delta) if delta is not None else None,
            delta_sha256=_sha256(delta) if delta else None,
            delta_preview=_preview(delta) if delta else None,
            previous_text_sha256=_sha256(previous) if previous is not None else None,
            finish_reason=_optional_text(getattr(message, "finish_reason", None)),
            canonical_status=status_value,
            canonical_status_message_id=status_message_id,
            finality_proven_at_observation=finalized,
            write_in_flight=bool(write_in_flight),
        )
        self._last_text_by_key[key] = text
        self._observations.append(observation)
        return observation

    def reconciliation(
        self,
        *,
        final_message_id: str | None,
        final_text: str | None,
    ) -> StreamCanonicalReconciliation:
        canonical = "" if final_text is None else str(final_text)
        if not canonical:
            return StreamCanonicalReconciliation.STREAM_INCOMPLETE

        matching: list[CanonicalTextObservation] = []
        if final_message_id:
            matching = [
                item
                for item in self._observations
                if item.message_id == final_message_id
            ]
        if not matching:
            matching = list(self._observations)
        if not matching:
            return StreamCanonicalReconciliation.UNAVAILABLE

        last = matching[-1]
        observed_text = self._last_text_by_key.get(last.message_key, "")
        if observed_text == canonical:
            return StreamCanonicalReconciliation.EXACT_MATCH
        if canonical.startswith(observed_text):
            return StreamCanonicalReconciliation.CANONICAL_EXTENDS_STREAM
        return StreamCanonicalReconciliation.STREAM_REVISED_BY_CANONICAL


def _baseline_assistant_keys(client: Any, conversation: str) -> set[str]:
    messages = client.get_messages(
        conversation,
        limit=None,
        roles={"assistant"},
        include_empty=True,
    )
    return {
        key
        for key in (_message_key(message) for message in messages)
        if key is not None
    }


def _newest_candidate(
    client: Any,
    conversation: str,
    *,
    baseline_keys: set[str],
) -> Any | None:
    messages = client.get_messages(
        conversation,
        limit=None,
        roles={"assistant"},
        include_empty=True,
    )
    candidates = [
        message
        for message in messages
        if (key := _message_key(message)) is not None
        and key not in baseline_keys
        and bool(str(getattr(message, "text", "") or "").strip())
    ]
    return candidates[-1] if candidates else None


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


class IncrementalCanonicalCharacterizationRunner:
    """Observe canonical assistant text concurrently with exactly one product write."""

    def __init__(
        self,
        runtime: Any,
        read_client: Any,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.runtime = runtime
        self.read_client = read_client
        self._monotonic = monotonic
        self._sleep = sleep

    def run(
        self,
        *,
        conversation: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        prompt: str = DEFAULT_PROMPT,
    ) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        conversation = conversation.strip()

        baseline_status = self.read_client.get_status(conversation)
        if getattr(baseline_status, "status", None) != "completed":
            raise RuntimeError("PR8_9_CANONICAL_PROBE_BASELINE_NOT_COMPLETED")
        baseline_keys = _baseline_assistant_keys(self.read_client, conversation)
        tracker = RevisionSafeCanonicalTracker(baseline_keys)

        report: dict[str, Any] = {
            "ok": False,
            "pr": "PR8.9.1",
            "probe_context": PROBE_CONTEXT,
            "conversation": conversation,
            "schema": SCHEMA_VERSION,
            "product_write_budget": 1,
            "write_attempts": 1,
            "write_completions": 0,
            "automatic_write_retry": False,
            "poll_interval_ms": round(poll_interval * 1000),
            "baseline_assistant_identity_count": len(baseline_keys),
            "canonical_poll_count": 0,
            "canonical_poll_error_count": 0,
            "observations": [],
        }

        started = self._monotonic()
        write_result: dict[str, Any] = {}
        write_error: dict[str, BaseException] = {}
        event_times: dict[str, int] = {}

        def elapsed_ms() -> int:
            return round((self._monotonic() - started) * 1000)

        def on_event(event: dict[str, Any]) -> None:
            if not isinstance(event, dict):
                return
            event_type = _optional_text(event.get("type"))
            if event_type and event_type not in event_times:
                event_times[event_type] = elapsed_ms()

        def writer() -> None:
            try:
                write_result["execution"] = self.runtime.send_text_observed(
                    prompt,
                    conversation=conversation,
                    timeout=timeout,
                    poll_interval=max(0.2, poll_interval),
                    conversation_mode="normal",
                    browser_authority_policy="PERSISTENT",
                    on_event=on_event,
                )
            except BaseException as error:
                write_error["error"] = error

        thread = threading.Thread(
            target=writer,
            name="pr8.9-incremental-canonical-write",
            daemon=False,
        )
        thread.start()

        deadline = started + timeout + 5.0
        first_canonical_completion_ms: int | None = None
        last_poll_error: dict[str, str] | None = None

        while thread.is_alive() and self._monotonic() < deadline:
            try:
                status = self.read_client.get_status(conversation)
                candidate = _newest_candidate(
                    self.read_client,
                    conversation,
                    baseline_keys=baseline_keys,
                )
                report["canonical_poll_count"] += 1
                if candidate is not None:
                    observation = tracker.observe(
                        candidate,
                        status=status,
                        observed_at_ms=elapsed_ms(),
                        write_in_flight=thread.is_alive(),
                    )
                    if observation is not None:
                        report["observations"].append(observation.to_dict())
                    if (
                        first_canonical_completion_ms is None
                        and _message_finalized(status, candidate)
                    ):
                        first_canonical_completion_ms = elapsed_ms()
            except Exception as error:
                report["canonical_poll_count"] += 1
                report["canonical_poll_error_count"] += 1
                last_poll_error = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            if thread.is_alive():
                self._sleep(poll_interval)

        thread.join(timeout=max(0.0, deadline - self._monotonic()))
        if thread.is_alive():
            report["failure"] = {
                "type": "RuntimeError",
                "message": "PR8_9_CANONICAL_PROBE_WRITE_THREAD_DID_NOT_SETTLE",
                "automatic_retry_attempted": False,
            }
            report["last_canonical_poll_error"] = last_poll_error
            return report

        # One read-only final sample improves reconciliation coverage without
        # performing or retrying a product write.
        try:
            final_status = self.read_client.get_status(conversation)
            final_candidate = _newest_candidate(
                self.read_client,
                conversation,
                baseline_keys=baseline_keys,
            )
            report["canonical_poll_count"] += 1
            if final_candidate is not None:
                observation = tracker.observe(
                    final_candidate,
                    status=final_status,
                    observed_at_ms=elapsed_ms(),
                    write_in_flight=False,
                )
                if observation is not None:
                    report["observations"].append(observation.to_dict())
                if (
                    first_canonical_completion_ms is None
                    and _message_finalized(final_status, final_candidate)
                ):
                    first_canonical_completion_ms = elapsed_ms()
        except Exception as error:
            report["canonical_poll_count"] += 1
            report["canonical_poll_error_count"] += 1
            last_poll_error = {
                "type": type(error).__name__,
                "message": str(error),
            }

        if "error" in write_error:
            report["failure"] = _failure(write_error["error"])
            report["last_canonical_poll_error"] = last_poll_error
            return report

        execution = write_result.get("execution")
        response = getattr(execution, "response", None)
        response_text = str(getattr(response, "text", "") or "")
        response_conversation = getattr(response, "conversation", None)
        final_message_id = _optional_text(getattr(response_conversation, "message_id", None))
        report["write_completions"] = 1
        report["response_returned_ms"] = elapsed_ms()
        report["canonical_completion_observed_ms"] = first_canonical_completion_ms
        report["event_times_ms"] = event_times

        observations = tracker.observations
        pre_final = [
            item
            for item in observations
            if item.pre_final and item.write_in_flight
        ]
        revision_count = sum(
            item.kind is TextObservationKind.REVISION for item in observations
        )
        first_text_ms = observations[0].observed_at_ms if observations else None
        last_text_ms = observations[-1].observed_at_ms if observations else None
        last_pre_final_ms = pre_final[-1].observed_at_ms if pre_final else None
        reconciliation = tracker.reconciliation(
            final_message_id=final_message_id,
            final_text=response_text,
        )

        report["summary"] = {
            "canonical_text_observed": bool(observations),
            "pre_final_partial_text_observed": bool(pre_final),
            "useful_incremental_canonical_observation_supported": bool(pre_final),
            "observation_count": len(observations),
            "revision_count": revision_count,
            "message_identity_count": len({item.message_key for item in observations}),
            "first_text_observed_ms": first_text_ms,
            "last_text_observed_ms": last_text_ms,
            "last_pre_final_text_observed_ms": last_pre_final_ms,
            "canonical_completion_observed_ms": first_canonical_completion_ms,
            "ttft_ms": first_text_ms,
            "finality_lag_ms": (
                first_canonical_completion_ms - last_pre_final_ms
                if first_canonical_completion_ms is not None
                and last_pre_final_ms is not None
                and first_canonical_completion_ms >= last_pre_final_ms
                else None
            ),
            "response_return_lag_ms": (
                report["response_returned_ms"] - first_canonical_completion_ms
                if first_canonical_completion_ms is not None
                and report["response_returned_ms"] >= first_canonical_completion_ms
                else None
            ),
            "final_response_length": len(response_text),
            "final_response_sha256": _sha256(response_text) if response_text else None,
            "final_message_id": final_message_id,
            "stream_canonical_reconciliation": reconciliation.value,
        }
        report["last_canonical_poll_error"] = last_poll_error
        report["architecture_invalidation_check"] = {
            "current_browser_owned_write_path_invalidated": False,
            "production_streaming_enabled": False,
            "candidate_a_incremental_canonical_observation": (
                "SUPPORTED" if bool(pre_final) else "NOT_PROVEN"
            ),
            "next_source_if_not_proven": "SAFE_BROWSER_RESPONSE_OBSERVATION",
        }
        report["ok"] = True
        return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PR8.9.1 bounded live characterization of incremental canonical "
            "assistant text during one existing-conversation product turn."
        )
    )
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
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
    provider = BrowserAuthorityCharacterizationProvider()
    runtime = assemble_product_runtime(
        client=write_client,
        provider=provider,
        browser_authority_policy="PERSISTENT",
    )
    report = IncrementalCanonicalCharacterizationRunner(
        runtime,
        read_client,
    ).run(
        conversation=args.conversation,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
