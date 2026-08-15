from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .browser_native_protocol import PROTOCOL_VERSION
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError


@dataclass(frozen=True)
class TemporaryChatHistoryProbeResult:
    probe_context: str
    conversation_id: str
    history_link_present: bool
    history_visible_link_present: bool
    final_history_link_present: bool
    final_history_visible_link_present: bool
    stable_history_presence: bool
    transient_history_presence: bool
    disappeared_after_seen: bool
    first_seen_ms: int | None
    last_seen_ms: int | None
    seen_sample_count: int
    absent_sample_count: int
    settle_window_ms: int | None
    observation_window_ms: int | None
    conversation_link_count: int
    history_surface_ready: bool
    tab_was_active: bool
    tab_active_after: bool | None
    tab_activated_during_probe: bool | None
    foreground_activation_observed: bool | None
    probe_tab_closed: bool
    elapsed_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    return value if isinstance(value, bool) else None


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _validate_conversation_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("conversation_id must be a string")
    value = value.strip()
    if not value:
        raise ValueError("conversation_id is required")
    if any(separator in value for separator in ("/", "?", "#")):
        raise ValueError("conversation_id must be a raw id, not a URL")
    return value


def probe_temporary_chat_history_presence(
    conversation_id: str,
    *,
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 30.0,
) -> TemporaryChatHistoryProbeResult:
    """Observe a returned PR8.7 id on a fresh history surface over time.

    This is a no-write research probe. It distinguishes an exact conversation
    link that appears transiently during root-page hydration from one that
    remains stably visible after a bounded settling window. Conversation titles,
    link text, raw DOM, and page payloads are not exported.
    """

    conversation_id = _validate_conversation_id(conversation_id)
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    bridge = provider or BrowserNativeTurnProvider()
    request_id = str(uuid.uuid4())
    connect_timeout = float(getattr(bridge, "connect_timeout", 3.0))
    response = bridge._rpc(  # noqa: SLF001 - same-package diagnostic boundary
        {
            "type": "turn",
            "request_id": request_id,
            "conversationId": conversation_id,
            "text": None,
            "timeoutMs": int(timeout * 1000),
            "canonicalCompleted": False,
            "canonicalCompletedAtMs": None,
            "probeTemporaryMode": False,
            "characterizeTemporaryTurn": False,
            "probeTemporaryHistoryPresence": True,
        },
        timeout=float(timeout) + max(0.1, connect_timeout),
    )

    if response.get("protocol") != PROTOCOL_VERSION:
        raise RequestError(
            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid Temporary history probe response",
            request_stage="temporary_chat_history_probe",
        )
    if response.get("request_id") != request_id:
        raise RequestError(
            "BROWSER_NATIVE_RESPONSE_MISMATCH",
            request_stage="temporary_chat_history_probe",
        )
    if not response.get("ok"):
        error = response.get("error") or "TEMPORARY_CHAT_HISTORY_PROBE_FAILED"
        raise RequestError(str(error), request_stage="temporary_chat_history_probe")

    returned_id = _optional_str(response, "conversationId")
    if returned_id != conversation_id:
        raise RequestError(
            "TEMPORARY_CHAT_HISTORY_PROBE_IDENTITY_MISMATCH",
            request_stage="temporary_chat_history_probe",
        )

    return TemporaryChatHistoryProbeResult(
        probe_context=_optional_str(response, "probeContext") or "unknown",
        conversation_id=conversation_id,
        history_link_present=bool(response.get("historyLinkPresent")),
        history_visible_link_present=bool(response.get("historyVisibleLinkPresent")),
        final_history_link_present=bool(response.get("finalHistoryLinkPresent")),
        final_history_visible_link_present=bool(
            response.get("finalHistoryVisibleLinkPresent")
        ),
        stable_history_presence=bool(response.get("stableHistoryPresence")),
        transient_history_presence=bool(response.get("transientHistoryPresence")),
        disappeared_after_seen=bool(response.get("disappearedAfterSeen")),
        first_seen_ms=_optional_int(response, "firstSeenMs"),
        last_seen_ms=_optional_int(response, "lastSeenMs"),
        seen_sample_count=_optional_int(response, "seenSampleCount") or 0,
        absent_sample_count=_optional_int(response, "absentSampleCount") or 0,
        settle_window_ms=_optional_int(response, "settleWindowMs"),
        observation_window_ms=_optional_int(response, "observationWindowMs"),
        conversation_link_count=_optional_int(response, "conversationLinkCount") or 0,
        history_surface_ready=bool(response.get("historySurfaceReady")),
        tab_was_active=bool(response.get("tabWasActive")),
        tab_active_after=_optional_bool(response, "tabActiveAfter"),
        tab_activated_during_probe=_optional_bool(response, "tabActivatedDuringProbe"),
        foreground_activation_observed=_optional_bool(
            response, "foregroundActivationObserved"
        ),
        probe_tab_closed=bool(response.get("probeTabClosed")),
        elapsed_ms=_optional_int(response, "elapsedMs"),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_history_probe",
        description=(
            "Run the PR8.7 no-write fresh-sidebar settling probe for a specific "
            "conversation id returned by Temporary characterization."
        ),
    )
    parser.add_argument("conversation_id")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = probe_temporary_chat_history_presence(
            args.conversation_id,
            timeout=args.timeout,
        )
    except (RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
