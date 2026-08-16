from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .browser_native_protocol import PROTOCOL_VERSION
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError


DEFAULT_SMOKE_TEXT = "Reply with exactly: SDK_TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_OK"
DEFAULT_EXPECTED_ASSISTANT_TEXT = "SDK_TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_OK"


@dataclass(frozen=True)
class ManualTemporaryGroundTruthResult:
    probe_context: str
    manual_temporary_confirmed: bool
    source_tab_id: int | None
    source_tab_left_open: bool
    same_source_tab: bool
    initial_url_kind: str
    initial_url_temporary_marker: bool
    initial_url_temporary_query_true: bool
    initial_url_conversation_id_present: bool
    conversation_write_count: int
    conversation_id: str | None
    turn_exchange_id: str | None
    response_status: int | None
    response_mime_type: str | None
    final_url_kind: str
    final_url_temporary_marker: bool
    final_url_temporary_query_true: bool
    url_conversation_id_present: bool
    submit_strategy: str | None
    submit_ack_ms: int | None
    completion_ready_wait_ms: int | None
    conversation_turn_count_before: int | None
    conversation_turn_count_after: int | None
    turn_count_growth: int | None
    matching_user_message_count: int
    assistant_message_candidate_count: int
    matching_expected_assistant_message_count: int
    user_message_visible_after_turn: bool
    assistant_message_visible_after_turn: bool
    assistant_exact_expected_reply_visible: bool
    visible_turn_ground_truth_proven: bool
    turn_surface_evidence_status: str
    turn_surface_selector_kind: str
    ui_mode_marker_observed_after_turn: bool
    post_turn_ui_mode_signals: tuple[str, ...]
    elapsed_ms: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _safe_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def probe_manual_temporary_ground_truth(
    text: str = DEFAULT_SMOKE_TEXT,
    *,
    manual_temporary_confirmed: bool,
    expected_assistant_text: str | None = DEFAULT_EXPECTED_ASSISTANT_TEXT,
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 150.0,
) -> ManualTemporaryGroundTruthResult:
    """Write one diagnostic turn into a manually prepared Temporary Chat tab.

    The operator must enable Temporary Chat in the visible ChatGPT UI first and
    leave that fresh new-chat tab selected in Chrome. The extension requires the
    selected page to retain ``?temporary-chat=true``, does not click or infer the
    Temporary control, writes exactly once, returns safe identity/finality plus
    bounded visible-turn evidence, performs no canonical read, and leaves the tab
    open for subsequent history/readback characterization.
    """

    if not manual_temporary_confirmed:
        raise ValueError("manual_temporary_confirmed must be true")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    if len(text) > 20_000:
        raise ValueError("text is too large")
    if expected_assistant_text is not None and not isinstance(expected_assistant_text, str):
        raise TypeError("expected_assistant_text must be a string or None")
    expected_assistant_text = (expected_assistant_text or "").strip()
    if len(expected_assistant_text) > 20_000:
        raise ValueError("expected_assistant_text is too large")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    bridge = provider or BrowserNativeTurnProvider()
    request_id = str(uuid.uuid4())
    connect_timeout = float(getattr(bridge, "connect_timeout", 3.0))
    response = bridge._rpc(  # noqa: SLF001 - same-package diagnostic boundary
        {
            "type": "turn",
            "request_id": request_id,
            "conversationId": None,
            "text": text,
            "expectedAssistantText": expected_assistant_text,
            "timeoutMs": int(timeout * 1000),
            "canonicalCompleted": False,
            "canonicalCompletedAtMs": None,
            "probeTemporaryMode": False,
            "characterizeTemporaryTurn": False,
            "probeTemporaryHistoryPresence": False,
            "characterizeManualTemporaryGroundTruth": True,
            "manualTemporaryConfirmed": True,
        },
        timeout=float(timeout) + max(0.1, connect_timeout),
    )

    if response.get("protocol") != PROTOCOL_VERSION:
        raise RequestError(
            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid manual Temporary response",
            request_stage="temporary_chat_manual_ground_truth",
        )
    if response.get("request_id") != request_id:
        raise RequestError(
            "BROWSER_NATIVE_RESPONSE_MISMATCH",
            request_stage="temporary_chat_manual_ground_truth",
        )
    if not response.get("ok"):
        error = response.get("error") or "TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_FAILED"
        raise RequestError(str(error), request_stage="temporary_chat_manual_ground_truth")

    return ManualTemporaryGroundTruthResult(
        probe_context=_optional_str(response, "probeContext") or "unknown",
        manual_temporary_confirmed=bool(response.get("manualTemporaryConfirmed")),
        source_tab_id=_optional_int(response, "sourceTabId"),
        source_tab_left_open=bool(response.get("sourceTabLeftOpen")),
        same_source_tab=bool(response.get("sameSourceTab")),
        initial_url_kind=_optional_str(response, "initialUrlKind") or "unknown",
        initial_url_temporary_marker=bool(response.get("initialUrlTemporaryMarker")),
        initial_url_temporary_query_true=bool(response.get("initialUrlTemporaryQueryTrue")),
        initial_url_conversation_id_present=bool(
            response.get("initialUrlConversationIdPresent")
        ),
        conversation_write_count=_optional_int(response, "conversationWriteCount") or 0,
        conversation_id=_optional_str(response, "conversationId"),
        turn_exchange_id=_optional_str(response, "turnExchangeId"),
        response_status=_optional_int(response, "responseStatus"),
        response_mime_type=_optional_str(response, "responseMimeType"),
        final_url_kind=_optional_str(response, "finalUrlKind") or "unknown",
        final_url_temporary_marker=bool(response.get("finalUrlTemporaryMarker")),
        final_url_temporary_query_true=bool(response.get("finalUrlTemporaryQueryTrue")),
        url_conversation_id_present=bool(response.get("urlConversationIdPresent")),
        submit_strategy=_optional_str(response, "submitStrategy"),
        submit_ack_ms=_optional_int(response, "submitAckMs"),
        completion_ready_wait_ms=_optional_int(response, "completionReadyWaitMs"),
        conversation_turn_count_before=_optional_int(response, "conversationTurnCountBefore"),
        conversation_turn_count_after=_optional_int(response, "conversationTurnCountAfter"),
        turn_count_growth=_optional_int(response, "turnCountGrowth"),
        matching_user_message_count=_optional_int(response, "matchingUserMessageCount") or 0,
        assistant_message_candidate_count=(
            _optional_int(response, "assistantMessageCandidateCount") or 0
        ),
        matching_expected_assistant_message_count=(
            _optional_int(response, "matchingExpectedAssistantMessageCount") or 0
        ),
        user_message_visible_after_turn=bool(response.get("userMessageVisibleAfterTurn")),
        assistant_message_visible_after_turn=bool(
            response.get("assistantMessageVisibleAfterTurn")
        ),
        assistant_exact_expected_reply_visible=bool(
            response.get("assistantExactExpectedReplyVisible")
        ),
        visible_turn_ground_truth_proven=bool(response.get("visibleTurnGroundTruthProven")),
        turn_surface_evidence_status=(
            _optional_str(response, "turnSurfaceEvidenceStatus") or "INCONCLUSIVE"
        ),
        turn_surface_selector_kind=(
            _optional_str(response, "turnSurfaceSelectorKind") or "unavailable"
        ),
        ui_mode_marker_observed_after_turn=bool(
            response.get("uiModeMarkerObservedAfterTurn")
        ),
        post_turn_ui_mode_signals=_safe_string_tuple(response.get("postTurnUiModeSignals")),
        elapsed_ms=_optional_int(response, "elapsedMs"),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_manual_ground_truth_probe",
        description=(
            "Write one PR8.7 diagnostic turn into a Temporary Chat that you manually "
            "confirmed in the visible ChatGPT UI. The selected ChatGPT tab must be a "
            "fresh ?temporary-chat=true root page. The probe does not click Temporary, "
            "does not perform canonical readback, and leaves the source tab open."
        ),
    )
    parser.add_argument("--text", default=DEFAULT_SMOKE_TEXT)
    parser.add_argument(
        "--expected-assistant-text",
        default=DEFAULT_EXPECTED_ASSISTANT_TEXT,
        help="expected visible assistant reply used only for browser-local ground-truth matching",
    )
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument(
        "--manual-temporary-confirmed",
        action="store_true",
        help="required: confirm you manually verified Temporary Chat in the selected fresh tab",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.manual_temporary_confirmed:
        print(
            json.dumps(
                {"ok": False, "error": "TEMPORARY_CHAT_MANUAL_GROUND_TRUTH_CONFIRMATION_REQUIRED"},
                indent=2,
            )
        )
        return 2

    try:
        result = probe_manual_temporary_ground_truth(
            args.text,
            manual_temporary_confirmed=True,
            expected_assistant_text=args.expected_assistant_text,
            timeout=args.timeout,
        )
    except (RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
