from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import unquote, urlparse

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .temporary_chat_route_reopen_probe import (
    TemporaryRouteReopenResult,
    probe_temporary_product_route_reopen,
)

DEFAULT_CONTINUATION_TEXT = "Reply with exactly: SDK_TEMPORARY_CHAT_GHOST_CONTINUATION_OK"


@dataclass(frozen=True)
class TemporaryControlledContinuationResult:
    probe_context: str
    ephemeral_backend_conversation_id: str
    source_temporary_tab_confirmed_closed: bool
    single_write_acknowledged: bool
    canonical_http_read_performed: bool
    conversation_attach_performed: bool
    history_probe_performed: bool
    pre_route_probe_performed: bool
    pre_recovery_evidence_status: str
    pre_stable_recovered: bool
    pre_final_url_kind: str
    pre_final_visible_turn_count: int
    pre_max_visible_turn_count: int
    write_invocation_count: int
    provider_result_conversation_id_matches_target: bool
    provider_result_conversation_id_provenance: str
    write_response_status: int
    write_response_mime_type: str | None
    write_turn_exchange_id_present: bool
    write_final_url_kind: str
    write_final_url_conversation_id_matches_target: bool
    write_tab_was_active: bool
    write_tab_active_after: bool | None
    write_tab_activated_during_turn: bool | None
    write_foreground_activation_observed: bool | None
    post_route_probe_performed: bool
    post_recovery_evidence_status: str
    post_stable_recovered: bool
    post_final_url_kind: str
    post_final_visible_turn_count: int
    post_max_visible_turn_count: int
    persisted_turn_count_growth: int
    expected_minimum_turn_growth: int
    target_route_turn_growth_proven: bool
    continuation_evidence_status: str
    message_text_exported: bool

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


def _classify_product_url(url: str | None, target_id: str) -> tuple[str, bool]:
    if not isinstance(url, str) or not url.strip():
        return "missing", False
    try:
        parsed = urlparse(url)
    except ValueError:
        return "invalid", False
    if parsed.scheme != "https" or parsed.netloc != "chatgpt.com":
        return "other_origin", False
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 2 and parts[0] == "c":
        route_id = unquote(parts[1])
        return ("exact_target", True) if route_id == target_id else ("other_conversation", False)
    if not parts:
        return "root", False
    return "other_chatgpt", False


def _require_stable_recovery(
    stage: str,
    result: TemporaryRouteReopenResult,
) -> None:
    if not result.stable_recovered or result.recovery_evidence_status != "STABLE_RECOVERED":
        raise RequestError(
            f"TEMPORARY_CHAT_CONTINUATION_{stage}_ROUTE_NOT_STABLY_RECOVERED:"
            f"{result.recovery_evidence_status}",
            request_stage="temporary_chat_continuation_probe",
        )
    if not result.final_url_conversation_id_matches_target:
        raise RequestError(
            f"TEMPORARY_CHAT_CONTINUATION_{stage}_TARGET_ROUTE_NOT_FINAL",
            request_stage="temporary_chat_continuation_probe",
        )
    if result.final_visible_turn_count < 2:
        raise RequestError(
            f"TEMPORARY_CHAT_CONTINUATION_{stage}_VISIBLE_TURN_PRECONDITION_FAILED",
            request_stage="temporary_chat_continuation_probe",
        )


def probe_temporary_controlled_continuation(
    ephemeral_backend_conversation_id: str,
    *,
    source_temporary_tab_confirmed_closed: bool,
    acknowledge_single_continuation_write: bool,
    provider: BrowserNativeTurnProvider | Any | None = None,
    text: str = DEFAULT_CONTINUATION_TEXT,
    route_probe_timeout: float = 30.0,
    write_timeout: float = 150.0,
) -> TemporaryControlledContinuationResult:
    """T7d: prove recovered-route continuation with one ordinary page-owned write.

    The experiment composes already-proven primitives instead of introducing a
    special browser write path: settled read-only route recovery, one ordinary
    ``BrowserNativeTurnProvider.send_text`` invocation, then another settled
    read-only recovery of the exact same route. No canonical read, attach API, or
    ordinary-history probe runs inside T7d.
    """

    conversation_id = _validate_ephemeral_backend_conversation_id(
        ephemeral_backend_conversation_id
    )
    if not source_temporary_tab_confirmed_closed:
        raise ValueError("source_temporary_tab_confirmed_closed must be true")
    if not acknowledge_single_continuation_write:
        raise ValueError("acknowledge_single_continuation_write must be true")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text is required")
    if len(text) > 20_000:
        raise ValueError("text is too large")
    if route_probe_timeout <= 0:
        raise ValueError("route_probe_timeout must be positive")
    if write_timeout <= 0:
        raise ValueError("write_timeout must be positive")

    bridge = provider or BrowserNativeTurnProvider()

    pre = probe_temporary_product_route_reopen(
        conversation_id,
        source_temporary_tab_confirmed_closed=True,
        provider=bridge,
        timeout=route_probe_timeout,
    )
    _require_stable_recovery("PRE", pre)

    # Exactly one high-level page-owned write invocation. The existing provider
    # has no automatic retry in this path; this diagnostic does not add one.
    write = bridge.send_text(
        text,
        conversation=conversation_id,
        timeout=write_timeout,
    )

    write_url_kind, write_url_matches = _classify_product_url(
        getattr(write, "final_url", None),
        conversation_id,
    )
    provider_id_matches = getattr(write, "conversation_id", None) == conversation_id

    post = probe_temporary_product_route_reopen(
        conversation_id,
        source_temporary_tab_confirmed_closed=True,
        provider=bridge,
        timeout=route_probe_timeout,
    )
    _require_stable_recovery("POST", post)

    persisted_growth = post.final_visible_turn_count - pre.final_visible_turn_count
    growth_proven = bool(
        provider_id_matches
        and write_url_matches
        and post.final_url_conversation_id_matches_target
        and persisted_growth >= 2
    )

    evidence_status = "CONTINUATION_PROVEN" if growth_proven else "CONTINUATION_NOT_PROVEN"

    return TemporaryControlledContinuationResult(
        probe_context="temporary_recovered_route_controlled_continuation",
        ephemeral_backend_conversation_id=conversation_id,
        source_temporary_tab_confirmed_closed=True,
        single_write_acknowledged=True,
        canonical_http_read_performed=False,
        conversation_attach_performed=False,
        history_probe_performed=False,
        pre_route_probe_performed=True,
        pre_recovery_evidence_status=pre.recovery_evidence_status,
        pre_stable_recovered=pre.stable_recovered,
        pre_final_url_kind=pre.final_url_kind,
        pre_final_visible_turn_count=pre.final_visible_turn_count,
        pre_max_visible_turn_count=pre.max_visible_turn_count,
        write_invocation_count=1,
        provider_result_conversation_id_matches_target=provider_id_matches,
        provider_result_conversation_id_provenance="worker_resolved_or_requested_fallback",
        write_response_status=int(getattr(write, "response_status")),
        write_response_mime_type=(
            getattr(write, "response_mime_type", None)
            if isinstance(getattr(write, "response_mime_type", None), str)
            else None
        ),
        write_turn_exchange_id_present=isinstance(
            getattr(write, "turn_exchange_id", None), str
        ),
        write_final_url_kind=write_url_kind,
        write_final_url_conversation_id_matches_target=write_url_matches,
        write_tab_was_active=bool(getattr(write, "tab_was_active", False)),
        write_tab_active_after=(
            getattr(write, "tab_active_after", None)
            if isinstance(getattr(write, "tab_active_after", None), bool)
            else None
        ),
        write_tab_activated_during_turn=(
            getattr(write, "tab_activated_during_turn", None)
            if isinstance(getattr(write, "tab_activated_during_turn", None), bool)
            else None
        ),
        write_foreground_activation_observed=(
            getattr(write, "foreground_activation_observed", None)
            if isinstance(getattr(write, "foreground_activation_observed", None), bool)
            else None
        ),
        post_route_probe_performed=True,
        post_recovery_evidence_status=post.recovery_evidence_status,
        post_stable_recovered=post.stable_recovered,
        post_final_url_kind=post.final_url_kind,
        post_final_visible_turn_count=post.final_visible_turn_count,
        post_max_visible_turn_count=post.max_visible_turn_count,
        persisted_turn_count_growth=persisted_growth,
        expected_minimum_turn_growth=2,
        target_route_turn_growth_proven=growth_proven,
        continuation_evidence_status=evidence_status,
        message_text_exported=False,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_continuation_probe",
        description=(
            "T7d: require stable recovery of a closed-source Temporary /c/<id>, "
            "submit exactly one ordinary page-owned continuation turn, then "
            "re-probe the exact route to prove persisted +2 turn growth. No "
            "canonical HTTP read, attach API, or history probe is performed."
        ),
    )
    parser.add_argument("ephemeral_backend_conversation_id")
    parser.add_argument("--route-probe-timeout", type=float, default=30.0)
    parser.add_argument("--write-timeout", type=float, default=150.0)
    parser.add_argument(
        "--source-temporary-tab-confirmed-closed",
        action="store_true",
        help="required: confirm the original true Temporary source tab is closed",
    )
    parser.add_argument(
        "--acknowledge-single-continuation-write",
        action="store_true",
        help="required: acknowledge that T7d intentionally submits exactly one turn",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.source_temporary_tab_confirmed_closed:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "TEMPORARY_CHAT_CONTINUATION_SOURCE_CLOSED_CONFIRMATION_REQUIRED",
                },
                indent=2,
            )
        )
        return 2
    if not args.acknowledge_single_continuation_write:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "TEMPORARY_CHAT_CONTINUATION_SINGLE_WRITE_ACK_REQUIRED",
                },
                indent=2,
            )
        )
        return 2

    try:
        result = probe_temporary_controlled_continuation(
            args.ephemeral_backend_conversation_id,
            source_temporary_tab_confirmed_closed=True,
            acknowledge_single_continuation_write=True,
            route_probe_timeout=args.route_probe_timeout,
            write_timeout=args.write_timeout,
        )
    except (RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
