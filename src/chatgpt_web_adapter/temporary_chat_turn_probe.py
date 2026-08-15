from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .browser_native_protocol import PROTOCOL_VERSION
from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .product_runtime import assemble_product_runtime

DEFAULT_SMOKE_TEXT = "Reply with exactly: SDK_TEMPORARY_CHAT_TURN_OK"


@dataclass(frozen=True)
class CanonicalTemporaryTurnObservation:
    attempted: bool
    status_ok: bool | None
    status: str | None
    status_finish_reason: str | None
    messages_ok: bool | None
    message_count: int | None
    user_message_count: int | None
    assistant_message_count: int | None
    observed_models: tuple[str, ...]
    attach_ok: bool | None
    attach_current_node_present: bool | None
    attach_detected_model: str | None
    attach_title_present: bool | None
    error_types: tuple[str, ...]


@dataclass(frozen=True)
class TemporaryChatTurnProbeResult:
    probe_context: str
    activation_action: str
    selection_proven_before_write: bool
    selected_before: bool | None
    selected_after_activation: bool | None
    selected_after_turn: bool | None
    pre_write_proof_signals: tuple[str, ...]
    post_turn_proof_signals: tuple[str, ...]
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
    tab_was_active: bool
    tab_active_after: bool | None
    tab_activated_during_probe: bool | None
    foreground_activation_observed: bool | None
    probe_tab_closed: bool
    elapsed_ms: int | None
    canonical_after_tab_close: CanonicalTemporaryTurnObservation

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


def _safe_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return tuple(result)


def _canonical_observation(
    conversation_id: str | None,
    *,
    auth_file: str | Path,
) -> CanonicalTemporaryTurnObservation:
    if not conversation_id:
        return CanonicalTemporaryTurnObservation(
            attempted=False,
            status_ok=None,
            status=None,
            status_finish_reason=None,
            messages_ok=None,
            message_count=None,
            user_message_count=None,
            assistant_message_count=None,
            observed_models=(),
            attach_ok=None,
            attach_current_node_present=None,
            attach_detected_model=None,
            attach_title_present=None,
            error_types=(),
        )

    runtime = assemble_product_runtime(auth_file=auth_file)
    error_types: list[str] = []

    status_ok: bool | None = None
    status_value: str | None = None
    status_finish_reason: str | None = None
    try:
        status = runtime.get_status(conversation_id)
        status_ok = True
        status_value = getattr(status, "status", None)
        status_finish_reason = getattr(status, "finish_reason", None)
    except Exception as error:  # diagnostic: preserve failure class, not raw payload
        status_ok = False
        error_types.append(f"status:{type(error).__name__}")

    messages_ok: bool | None = None
    message_count: int | None = None
    user_message_count: int | None = None
    assistant_message_count: int | None = None
    observed_models: tuple[str, ...] = ()
    try:
        messages = runtime.get_messages(conversation_id)
        messages_ok = True
        message_count = len(messages)
        user_message_count = sum(
            1 for message in messages if getattr(message, "role", None) == "user"
        )
        assistant_message_count = sum(
            1 for message in messages if getattr(message, "role", None) == "assistant"
        )
        observed_models = tuple(
            sorted(
                {
                    model.strip()
                    for message in messages
                    if isinstance((model := getattr(message, "model", None)), str)
                    and model.strip()
                }
            )
        )
    except Exception as error:
        messages_ok = False
        error_types.append(f"messages:{type(error).__name__}")

    attach_ok: bool | None = None
    attach_current_node_present: bool | None = None
    attach_detected_model: str | None = None
    attach_title_present: bool | None = None
    try:
        attached = runtime.attach_conversation(conversation_id)
        attach_ok = True
        attach_current_node_present = bool(getattr(attached, "current_node", None))
        detected_model = getattr(attached, "detected_model", None)
        attach_detected_model = (
            detected_model.strip()
            if isinstance(detected_model, str) and detected_model.strip()
            else None
        )
        attach_title_present = bool(getattr(attached, "title", None))
    except Exception as error:
        attach_ok = False
        error_types.append(f"attach:{type(error).__name__}")

    return CanonicalTemporaryTurnObservation(
        attempted=True,
        status_ok=status_ok,
        status=status_value if isinstance(status_value, str) else None,
        status_finish_reason=(
            status_finish_reason if isinstance(status_finish_reason, str) else None
        ),
        messages_ok=messages_ok,
        message_count=message_count,
        user_message_count=user_message_count,
        assistant_message_count=assistant_message_count,
        observed_models=observed_models,
        attach_ok=attach_ok,
        attach_current_node_present=attach_current_node_present,
        attach_detected_model=attach_detected_model,
        attach_title_present=attach_title_present,
        error_types=tuple(error_types),
    )


def probe_temporary_chat_turn(
    text: str = DEFAULT_SMOKE_TEXT,
    *,
    acknowledge_durable_risk: bool,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 150.0,
) -> TemporaryChatTurnProbeResult:
    """Run the PR8.7 controlled one-shot Temporary Chat characterization write.

    This is research/diagnostic only. Current ChatGPT did not expose a reliable
    pre-write selected-state signal, so the first real write may create one
    ordinary durable smoke conversation if activation did not enable Temporary
    mode. Callers must acknowledge that bounded risk explicitly.
    """

    if not acknowledge_durable_risk:
        raise ValueError("acknowledge_durable_risk must be true for the write probe")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    if len(text) > 20_000:
        raise ValueError("text is too large for Temporary Chat turn probe")
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
            "characterizeTemporaryTurn": True,
            "acknowledgeDurableRisk": True,
        },
        timeout=float(timeout) + max(0.1, connect_timeout),
    )

    if response.get("protocol") != PROTOCOL_VERSION:
        raise RequestError(
            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid Temporary turn probe response",
            request_stage="temporary_chat_turn_probe",
        )
    if response.get("request_id") != request_id:
        raise RequestError(
            "BROWSER_NATIVE_RESPONSE_MISMATCH",
            request_stage="temporary_chat_turn_probe",
        )
    if not response.get("ok"):
        error = response.get("error") or "TEMPORARY_CHAT_TURN_PROBE_FAILED"
        raise RequestError(str(error), request_stage="temporary_chat_turn_probe")

    conversation_id = _optional_str(response, "conversationId")
    canonical = _canonical_observation(conversation_id, auth_file=auth_file)

    return TemporaryChatTurnProbeResult(
        probe_context=_optional_str(response, "probeContext") or "unknown",
        activation_action=_optional_str(response, "activationAction") or "unknown",
        selection_proven_before_write=bool(response.get("selectionProvenBeforeWrite")),
        selected_before=_optional_bool(response, "selectedBefore"),
        selected_after_activation=_optional_bool(response, "selectedAfterActivation"),
        selected_after_turn=_optional_bool(response, "selectedAfterTurn"),
        pre_write_proof_signals=_safe_string_tuple(response.get("preWriteProofSignals")),
        post_turn_proof_signals=_safe_string_tuple(response.get("postTurnProofSignals")),
        conversation_write_count=_optional_int(response, "conversationWriteCount") or 0,
        conversation_id=conversation_id,
        turn_exchange_id=_optional_str(response, "turnExchangeId"),
        response_status=_optional_int(response, "responseStatus"),
        response_mime_type=_optional_str(response, "responseMimeType"),
        final_url_kind=_optional_str(response, "finalUrlKind") or "unknown",
        url_conversation_id_present=bool(response.get("urlConversationIdPresent")),
        submit_strategy=_optional_str(response, "submitStrategy"),
        submit_ack_ms=_optional_int(response, "submitAckMs"),
        completion_ready_wait_ms=_optional_int(response, "completionReadyWaitMs"),
        tab_was_active=bool(response.get("tabWasActive")),
        tab_active_after=_optional_bool(response, "tabActiveAfter"),
        tab_activated_during_probe=_optional_bool(response, "tabActivatedDuringProbe"),
        foreground_activation_observed=_optional_bool(
            response, "foregroundActivationObserved"
        ),
        probe_tab_closed=bool(response.get("probeTabClosed")),
        elapsed_ms=_optional_int(response, "elapsedMs"),
        canonical_after_tab_close=canonical,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_turn_probe",
        description=(
            "Run the PR8.7 controlled one-shot Temporary Chat write characterization. "
            "Because selected state is not pre-write observable in the current UI, "
            "the experiment may create one ordinary durable smoke chat if Temporary "
            "activation did not take effect."
        ),
    )
    parser.add_argument("--text", default=DEFAULT_SMOKE_TEXT)
    parser.add_argument("--timeout", type=float, default=150.0)
    parser.add_argument("--auth-file", type=Path, default=DEFAULT_AUTH_FILE)
    parser.add_argument(
        "--acknowledge-durable-risk",
        action="store_true",
        help=(
            "required: acknowledge that this characterization may create one "
            "ordinary durable smoke conversation if Temporary activation fails"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.acknowledge_durable_risk:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "TEMPORARY_CHAT_TURN_PROBE_DURABLE_RISK_ACK_REQUIRED",
                },
                indent=2,
            )
        )
        return 2

    try:
        result = probe_temporary_chat_turn(
            args.text,
            acknowledge_durable_risk=True,
            auth_file=args.auth_file,
            timeout=args.timeout,
        )
    except (RequestError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
