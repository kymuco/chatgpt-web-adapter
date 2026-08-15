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


@dataclass(frozen=True)
class ManualTemporaryGroundTruthResult:
    probe_context: str
    manual_temporary_confirmed: bool
    source_tab_id: int | None
    source_tab_left_open: bool
    conversation_write_count: int
    conversation_id: str | None
    turn_exchange_id: str | None
    response_status: int | None
    response_mime_type: str | None
    final_url_kind: str
    url_conversation_id_present: bool
    submit_strategy: str | None
    submit_ack_ms: int | None
    completion_ready_wait_ms: int | None
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
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 150.0,
) -> ManualTemporaryGroundTruthResult:
    """Write one diagnostic turn into a manually prepared Temporary Chat tab.

    The operator must enable Temporary Chat in the visible ChatGPT UI first and
    leave that fresh new-chat tab selected in Chrome. The extension does not
    click or infer the Temporary control. It writes exactly once, returns safe
    identity/finality metadata, performs no canonical read, and leaves the tab
    open for subsequent history/readback characterization.
    """

    if not manual_temporary_confirmed:
        raise ValueError("manual_temporary_confirmed must be true")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    if len(text) > 20_000:
        raise ValueError("text is too large")
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
        conversation_write_count=_optional_int(response, "conversationWriteCount") or 0,
        conversation_id=_optional_str(response, "conversationId"),
        turn_exchange_id=_optional_str(response, "turnExchangeId"),
        response_status=_optional_int(response, "responseStatus"),
        response_mime_type=_optional_str(response, "responseMimeType"),
        final_url_kind=_optional_str(response, "finalUrlKind") or "unknown",
        url_conversation_id_present=bool(response.get("urlConversationIdPresent")),
        submit_strategy=_optional_str(response, "submitStrategy"),
        submit_ack_ms=_optional_int(response, "submitAckMs"),
        completion_ready_wait_ms=_optional_int(response, "completionReadyWaitMs"),
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
            "enabled in the visible ChatGPT UI. The selected ChatGPT tab must be a "
            "fresh new chat. The probe does not click Temporary, does not perform "
            "canonical readback, and leaves the source tab open."
        ),
    )
    parser.add_argument("--text", default=DEFAULT_SMOKE_TEXT)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument(
        "--manual-temporary-confirmed",
        action="store_true",
        help="required: confirm you manually enabled Temporary Chat in the selected fresh ChatGPT tab",
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
            timeout=args.timeout,
        )
    except (RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
