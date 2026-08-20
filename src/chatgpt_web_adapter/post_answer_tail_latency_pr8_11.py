from __future__ import annotations

import time
from typing import Any, Callable

from .browser_authority_live_characterization import BrowserAuthorityCharacterizationProvider
from .exceptions import RequestError
from .revision_safe_streaming_pr8_9 import (
    ASSISTANT_TEXT_DELTA,
    ASSISTANT_TEXT_REVISION,
    ASSISTANT_TEXT_SNAPSHOT,
    CANONICAL_TEXT_FINALIZED,
)

SCHEMA = 1
_TEXT_EVENT_TYPES = {
    ASSISTANT_TEXT_SNAPSHOT,
    ASSISTANT_TEXT_DELTA,
    ASSISTANT_TEXT_REVISION,
}


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _delta_ms(start: int | None, end: int | None) -> int | None:
    if start is None or end is None or end < start:
        return None
    return end - start


class PostAnswerTailTimingProvider(BrowserAuthorityCharacterizationProvider):
    """Read-only access to the PR8.11 numeric browser-local tail record."""

    def support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        response = self._characterization_rpc(
            {"characterizePostAnswerTailTimingSupport": True},
            timeout=timeout,
        )
        return {
            "supported": response.get("postAnswerTailTimingSupported") is True,
            "schema": _optional_int(response.get("postAnswerTailTimingSchemaVersion")),
            "numeric_only": response.get("numericOnly") is True,
            "changes_write_semantics": response.get("changesWriteSemantics") is True,
        }

    def timing_for_lease(
        self,
        lease_id: str,
        *,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError("lease_id is required")
        lease_id = lease_id.strip()
        response = self._characterization_rpc(
            {
                "characterizePostAnswerTailTiming": True,
                "expectedBrowserAuthorityLeaseId": lease_id,
            },
            timeout=timeout,
        )
        if response.get("postAnswerTailTimingSupported") is not True:
            raise RequestError(
                "PR8_11_TAIL_TIMING_NOT_SUPPORTED",
                request_stage="post_answer_tail_timing",
            )
        record = response.get("postAnswerTailTiming")
        if not isinstance(record, dict):
            raise RequestError(
                "PR8_11_TAIL_TIMING_RECORD_MISSING",
                request_stage="post_answer_tail_timing",
            )
        if record.get("browserAuthorityLeaseId") != lease_id:
            raise RequestError(
                "PR8_11_TAIL_TIMING_LEASE_MISMATCH",
                request_stage="post_answer_tail_timing",
            )
        if _optional_int(record.get("schemaVersion")) != SCHEMA:
            raise RequestError(
                "PR8_11_TAIL_TIMING_SCHEMA_MISMATCH",
                request_stage="post_answer_tail_timing",
            )

        mapping = {
            "assistant_text_observation_count": "assistantTextObservationCount",
            "write_delegated_ms": "writeDelegatedMs",
            "last_assistant_text_observed_ms": "lastAssistantTextObservedMs",
            "network_complete_ms": "networkCompleteMs",
            "native_complete_ms": "nativeCompleteMs",
            "last_text_to_network_complete_ms": "lastTextToNetworkCompleteMs",
            "network_complete_to_native_complete_ms": "networkCompleteToNativeCompleteMs",
            "last_text_to_native_complete_ms": "lastTextToNativeCompleteMs",
        }
        result: dict[str, Any] = {
            "schema": SCHEMA,
            "browser_authority_lease_id": lease_id,
        }
        for output_name, wire_name in mapping.items():
            result[output_name] = _optional_int(record.get(wire_name))
        return result


class StandaloneTailTimingObserver:
    """Measure callback-visible tail boundaries without changing stream semantics."""

    def __init__(
        self,
        downstream: Callable[[dict[str, Any]], None] | None = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.downstream = downstream
        self._monotonic = monotonic
        self._started_at = monotonic()
        self._events: dict[str, int] = {}
        self._text_event_count = 0

    def _now_ms(self) -> int:
        return max(0, round((self._monotonic() - self._started_at) * 1000))

    def on_event(self, event: dict[str, Any]) -> None:
        if isinstance(event, dict):
            event_type = event.get("type")
            now_ms = self._now_ms()
            if event_type == "browser_native_turn_started":
                self._events.setdefault("turn_started_ms", now_ms)
            elif event_type in _TEXT_EVENT_TYPES:
                self._events.setdefault("first_text_event_ms", now_ms)
                self._events["last_text_event_ms"] = now_ms
                self._text_event_count += 1
            elif event_type == "browser_native_write_completed":
                self._events["write_completed_ms"] = now_ms
            elif event_type == CANONICAL_TEXT_FINALIZED:
                self._events["canonical_finalized_ms"] = now_ms
            elif event_type == "browser_native_readback_completed":
                self._events["readback_completed_ms"] = now_ms
        if self.downstream is not None:
            self.downstream(event)

    def mark_runtime_return(self) -> None:
        self._events["runtime_return_ms"] = self._now_ms()

    def report(self, *, browser_tail: dict[str, Any] | None = None) -> dict[str, Any]:
        first_text = self._events.get("first_text_event_ms")
        last_text = self._events.get("last_text_event_ms")
        write_completed = self._events.get("write_completed_ms")
        canonical_finalized = self._events.get("canonical_finalized_ms")
        readback_completed = self._events.get("readback_completed_ms")
        runtime_return = self._events.get("runtime_return_ms")
        return {
            "schema": SCHEMA,
            "local_event_timing_ms": dict(self._events),
            "local_text_event_count": self._text_event_count,
            "local_tail_deltas_ms": {
                "first_text_to_last_text": _delta_ms(first_text, last_text),
                "last_text_to_write_completed": _delta_ms(last_text, write_completed),
                "write_completed_to_canonical_finalized": _delta_ms(
                    write_completed,
                    canonical_finalized,
                ),
                "canonical_finalized_to_readback_completed": _delta_ms(
                    canonical_finalized,
                    readback_completed,
                ),
                "readback_completed_to_runtime_return": _delta_ms(
                    readback_completed,
                    runtime_return,
                ),
                "last_text_to_runtime_return": _delta_ms(last_text, runtime_return),
            },
            "browser_tail_timing": dict(browser_tail) if isinstance(browser_tail, dict) else None,
        }
