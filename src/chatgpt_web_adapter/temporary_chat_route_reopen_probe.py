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
class TemporaryRouteReopenResult:
    probe_context: str
    ephemeral_backend_conversation_id: str
    source_temporary_tab_confirmed_closed: bool
    product_route_open_attempted: bool
    canonical_http_read_performed: bool
    conversation_attach_performed: bool
    write_performed: bool
    conversation_write_count: int
    observation_window_ms: int | None
    target_route_observed: bool
    target_route_first_seen_ms: int | None
    target_route_last_seen_ms: int | None
    target_route_sample_count: int
    root_route_observed: bool
    root_route_sample_count: int
    other_route_sample_count: int
    redirect_away_from_target_observed: bool
    final_url_kind: str
    final_url_conversation_id_matches_target: bool
    visible_turn_surface_observed: bool
    max_visible_turn_count: int
    final_visible_turn_count: int
    turn_surface_selector_kind: str
    recovered_sample_count: int
    first_recovered_ms: int | None
    last_recovered_ms: int | None
    stable_recovered: bool
    transient_recovered: bool
    recovery_evidence_status: str
    tab_was_active: bool
    tab_active_after: bool | None
    tab_activated_during_probe: bool | None
    foreground_activation_observed: bool | None
    debugger_attached_after: bool | None
    probe_tab_closed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_ephemeral_backend_conversation_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("ephemeral_backend_conversation_id must be a string")
    value = value.strip()
    if not value:
        raise ValueError("ephemeral_backend_conversation_id is required")
    if any(separator in value for separator in ("/", "?", "#")):
        raise ValueError(
            "ephemeral_backend_conversation_id must be a raw backend id, not a URL"
        )
    return value


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


def probe_temporary_product_route_reopen(
    ephemeral_backend_conversation_id: str,
    *,
    source_temporary_tab_confirmed_closed: bool,
    provider: BrowserNativeTurnProvider | Any | None = None,
    timeout: float = 30.0,
) -> TemporaryRouteReopenResult:
    """Characterize exact /c/<id> recovery after the true Temporary source closes.

    This diagnostic opens one disposable inactive product tab and samples route
    settling plus bounded visible-turn counts. It never types, submits, performs
    a canonical HTTP read, or exports message text / raw DOM.
    """

    conversation_id = _validate_ephemeral_backend_conversation_id(
        ephemeral_backend_conversation_id
    )
    if not source_temporary_tab_confirmed_closed:
        raise ValueError("source_temporary_tab_confirmed_closed must be true")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    bridge = provider or BrowserNativeTurnProvider()
    request_id = str(uuid.uuid4())
    connect_timeout = float(getattr(bridge, "connect_timeout", 3.0))
    response = bridge._rpc(  # noqa: SLF001 - same-package research diagnostic
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
            "probeTemporaryHistoryPresence": False,
            "characterizeManualTemporaryGroundTruth": False,
            "probeTemporaryRouteReopen": True,
            "sourceTemporaryTabConfirmedClosed": True,
        },
        timeout=float(timeout) + max(0.1, connect_timeout),
    )

    if response.get("protocol") != PROTOCOL_VERSION:
        raise RequestError(
            "BROWSER_NATIVE_PROTOCOL_MISMATCH: invalid Temporary route reopen response",
            request_stage="temporary_chat_route_reopen_probe",
        )
    if response.get("request_id") != request_id:
        raise RequestError(
            "BROWSER_NATIVE_RESPONSE_MISMATCH",
            request_stage="temporary_chat_route_reopen_probe",
        )
    if not response.get("ok"):
        error = response.get("error") or "TEMPORARY_CHAT_ROUTE_REOPEN_PROBE_FAILED"
        raise RequestError(str(error), request_stage="temporary_chat_route_reopen_probe")

    returned_id = _optional_str(response, "conversationId")
    if returned_id != conversation_id:
        raise RequestError(
            "TEMPORARY_CHAT_ROUTE_REOPEN_IDENTITY_MISMATCH",
            request_stage="temporary_chat_route_reopen_probe",
        )

    return TemporaryRouteReopenResult(
        probe_context=_optional_str(response, "probeContext") or "unknown",
        ephemeral_backend_conversation_id=conversation_id,
        source_temporary_tab_confirmed_closed=bool(
            response.get("sourceTemporaryTabConfirmedClosed")
        ),
        product_route_open_attempted=bool(response.get("productRouteOpenAttempted")),
        canonical_http_read_performed=bool(response.get("canonicalHttpReadPerformed")),
        conversation_attach_performed=bool(response.get("conversationAttachPerformed")),
        write_performed=bool(response.get("writePerformed")),
        conversation_write_count=_optional_int(response, "conversationWriteCount") or 0,
        observation_window_ms=_optional_int(response, "observationWindowMs"),
        target_route_observed=bool(response.get("targetRouteObserved")),
        target_route_first_seen_ms=_optional_int(response, "targetRouteFirstSeenMs"),
        target_route_last_seen_ms=_optional_int(response, "targetRouteLastSeenMs"),
        target_route_sample_count=_optional_int(response, "targetRouteSampleCount") or 0,
        root_route_observed=bool(response.get("rootRouteObserved")),
        root_route_sample_count=_optional_int(response, "rootRouteSampleCount") or 0,
        other_route_sample_count=_optional_int(response, "otherRouteSampleCount") or 0,
        redirect_away_from_target_observed=bool(
            response.get("redirectAwayFromTargetObserved")
        ),
        final_url_kind=_optional_str(response, "finalUrlKind") or "unknown",
        final_url_conversation_id_matches_target=bool(
            response.get("finalUrlConversationIdMatchesTarget")
        ),
        visible_turn_surface_observed=bool(response.get("visibleTurnSurfaceObserved")),
        max_visible_turn_count=_optional_int(response, "maxVisibleTurnCount") or 0,
        final_visible_turn_count=_optional_int(response, "finalVisibleTurnCount") or 0,
        turn_surface_selector_kind=(
            _optional_str(response, "turnSurfaceSelectorKind") or "unavailable"
        ),
        recovered_sample_count=_optional_int(response, "recoveredSampleCount") or 0,
        first_recovered_ms=_optional_int(response, "firstRecoveredMs"),
        last_recovered_ms=_optional_int(response, "lastRecoveredMs"),
        stable_recovered=bool(response.get("stableRecovered")),
        transient_recovered=bool(response.get("transientRecovered")),
        recovery_evidence_status=(
            _optional_str(response, "recoveryEvidenceStatus") or "INCONCLUSIVE"
        ),
        tab_was_active=bool(response.get("tabWasActive")),
        tab_active_after=_optional_bool(response, "tabActiveAfter"),
        tab_activated_during_probe=_optional_bool(response, "tabActivatedDuringProbe"),
        foreground_activation_observed=_optional_bool(
            response, "foregroundActivationObserved"
        ),
        debugger_attached_after=_optional_bool(response, "debuggerAttachedAfter"),
        probe_tab_closed=bool(response.get("probeTabClosed")),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_route_reopen_probe",
        description=(
            "Characterize exact /c/<ephemeral-backend-id> product-route recovery "
            "after the original true Temporary source tab has been closed. The "
            "probe is read-only: no typing, submit, continuation, canonical HTTP "
            "read, or message-text export."
        ),
    )
    parser.add_argument("ephemeral_backend_conversation_id")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--source-temporary-tab-confirmed-closed",
        action="store_true",
        help="required: confirm the original true Temporary source tab is closed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.source_temporary_tab_confirmed_closed:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "TEMPORARY_CHAT_ROUTE_REOPEN_SOURCE_CLOSED_CONFIRMATION_REQUIRED",
                },
                indent=2,
            )
        )
        return 2

    try:
        result = probe_temporary_product_route_reopen(
            args.ephemeral_backend_conversation_id,
            source_temporary_tab_confirmed_closed=True,
            timeout=args.timeout,
        )
    except (RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
