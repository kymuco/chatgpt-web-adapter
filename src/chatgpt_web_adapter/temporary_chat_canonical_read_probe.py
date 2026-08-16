from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .client import ChatGPTWebClient, DEFAULT_TIMEOUT_SECONDS
from .exceptions import AuthError, RequestError
from .status import _status_from_payload


@dataclass(frozen=True)
class TemporaryCanonicalReadResult:
    probe_context: str
    ephemeral_backend_conversation_id: str
    source_temporary_tab_confirmed_open: bool
    source_temporary_tab_confirmed_closed: bool
    source_temporary_tab_state: str
    canonical_payload_read_calls: int
    canonical_read_succeeded: bool
    canonical_readability_status: str
    http_status: int | None
    request_stage: str | None
    canonical_endpoint_kind: str
    canonical_http_read_by_id: bool
    browser_navigation_performed: bool
    product_route_open_attempted: bool
    attach_performed: bool
    write_performed: bool
    http_referer_uses_conversation_route_shape: bool
    payload_id_present: bool
    payload_id_matches_requested: bool | None
    mapping_present: bool
    mapping_node_count: int
    current_node_present: bool
    current_branch_node_count: int
    current_branch_message_count: int
    user_message_count: int
    assistant_message_count: int
    tool_message_count: int
    other_message_count: int
    lifecycle_status: str | None
    current_role: str | None
    finish_reason_present: bool
    raw_payload_exported: bool
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


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _source_tab_state(
    *,
    source_temporary_tab_confirmed_open: bool,
    source_temporary_tab_confirmed_closed: bool,
) -> str:
    if source_temporary_tab_confirmed_open == source_temporary_tab_confirmed_closed:
        raise ValueError(
            "exactly one source Temporary tab state must be confirmed: open or closed"
        )
    return "OPEN" if source_temporary_tab_confirmed_open else "CLOSED"


def _probe_context_for_source_state(source_temporary_tab_state: str) -> str:
    if source_temporary_tab_state == "OPEN":
        return "temporary_canonical_direct_id_read_while_live"
    return "temporary_canonical_direct_id_read_after_source_close"


def _current_branch_message_roles(payload: dict[str, Any]) -> tuple[int, list[str]]:
    mapping = payload.get("mapping")
    if not isinstance(mapping, dict):
        return 0, []

    node_id = _optional_str(payload.get("current_node"))
    seen: set[str] = set()
    branch_nodes = 0
    roles: list[str] = []

    while node_id:
        if node_id in seen:
            break
        seen.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            break
        branch_nodes += 1

        message = node.get("message")
        if isinstance(message, dict):
            author = message.get("author")
            role = _optional_str(author.get("role")) if isinstance(author, dict) else None
            roles.append(role or "other")

        node_id = _optional_str(node.get("parent"))

    return branch_nodes, roles


def _readability_status_from_error(error: RequestError) -> str:
    if error.status_code == 404:
        return "NOT_FOUND"
    if error.status_code in {401, 403}:
        return "ACCESS_DENIED"
    if error.status_code is not None:
        return "HTTP_ERROR"
    return "ERROR"


def _failed_result(
    ephemeral_backend_conversation_id: str,
    *,
    source_temporary_tab_state: str,
    status: str,
    error: RequestError,
) -> TemporaryCanonicalReadResult:
    source_open = source_temporary_tab_state == "OPEN"
    return TemporaryCanonicalReadResult(
        probe_context=_probe_context_for_source_state(source_temporary_tab_state),
        ephemeral_backend_conversation_id=ephemeral_backend_conversation_id,
        source_temporary_tab_confirmed_open=source_open,
        source_temporary_tab_confirmed_closed=not source_open,
        source_temporary_tab_state=source_temporary_tab_state,
        canonical_payload_read_calls=1,
        canonical_read_succeeded=False,
        canonical_readability_status=status,
        http_status=error.status_code,
        request_stage=error.request_stage,
        canonical_endpoint_kind="backend_conversation_by_id",
        canonical_http_read_by_id=True,
        browser_navigation_performed=False,
        product_route_open_attempted=False,
        attach_performed=False,
        write_performed=False,
        http_referer_uses_conversation_route_shape=True,
        payload_id_present=False,
        payload_id_matches_requested=None,
        mapping_present=False,
        mapping_node_count=0,
        current_node_present=False,
        current_branch_node_count=0,
        current_branch_message_count=0,
        user_message_count=0,
        assistant_message_count=0,
        tool_message_count=0,
        other_message_count=0,
        lifecycle_status=None,
        current_role=None,
        finish_reason_present=False,
        raw_payload_exported=False,
        message_text_exported=False,
    )


def probe_temporary_canonical_read(
    ephemeral_backend_conversation_id: str,
    *,
    source_temporary_tab_confirmed_open: bool = False,
    source_temporary_tab_confirmed_closed: bool = False,
    client: Any | None = None,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TemporaryCanonicalReadResult:
    """Perform one logical canonical direct-id read for a proven Temporary turn.

    The caller must explicitly confirm whether the original Temporary source tab
    is still OPEN (T4) or has been intentionally CLOSED (T7a). The supplied id
    is treated only as an ephemeral backend identity returned by the proven
    Temporary write.

    This probe never opens ``/c/<id>`` in a browser, never attaches for
    continuation, and never writes. The current canonical HTTP implementation
    does use a conversation-shaped Referer while fetching
    ``/backend-api/conversation/<id>``; that distinction is reported explicitly.

    Raw conversation payloads and message text never leave this diagnostic.
    """

    ephemeral_backend_conversation_id = _validate_ephemeral_backend_conversation_id(
        ephemeral_backend_conversation_id
    )
    source_temporary_tab_state = _source_tab_state(
        source_temporary_tab_confirmed_open=source_temporary_tab_confirmed_open,
        source_temporary_tab_confirmed_closed=source_temporary_tab_confirmed_closed,
    )
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    canonical = client
    if canonical is None:
        canonical = ChatGPTWebClient(
            auth_file=auth_file,
            timeout=max(10, int(timeout)),
            auto_refresh_auth=True,
            persist_refreshed_auth=False,
            auto_login=False,
            auto_sentinel=False,
        )

    payload_reader = getattr(canonical, "_get_conversation_payload", None)
    if not callable(payload_reader):
        raise TypeError("client must provide _get_conversation_payload(conversation_id)")

    try:
        payload = payload_reader(ephemeral_backend_conversation_id)
    except RequestError as error:
        return _failed_result(
            ephemeral_backend_conversation_id,
            source_temporary_tab_state=source_temporary_tab_state,
            status=_readability_status_from_error(error),
            error=error,
        )

    if not isinstance(payload, dict):
        raise RequestError(
            "temporary canonical read expected JSON object",
            request_stage="temporary_chat_canonical_read",
        )

    mapping = payload.get("mapping")
    mapping_present = isinstance(mapping, dict)
    mapping_node_count = len(mapping) if mapping_present else 0
    current_node = _optional_str(payload.get("current_node"))
    branch_node_count, roles = _current_branch_message_roles(payload)
    lifecycle = _status_from_payload(payload)

    payload_id = _optional_str(payload.get("id"))
    source_open = source_temporary_tab_state == "OPEN"
    return TemporaryCanonicalReadResult(
        probe_context=_probe_context_for_source_state(source_temporary_tab_state),
        ephemeral_backend_conversation_id=ephemeral_backend_conversation_id,
        source_temporary_tab_confirmed_open=source_open,
        source_temporary_tab_confirmed_closed=not source_open,
        source_temporary_tab_state=source_temporary_tab_state,
        canonical_payload_read_calls=1,
        canonical_read_succeeded=True,
        canonical_readability_status="READABLE",
        http_status=200,
        request_stage="conversation_fetch",
        canonical_endpoint_kind="backend_conversation_by_id",
        canonical_http_read_by_id=True,
        browser_navigation_performed=False,
        product_route_open_attempted=False,
        attach_performed=False,
        write_performed=False,
        http_referer_uses_conversation_route_shape=True,
        payload_id_present=payload_id is not None,
        payload_id_matches_requested=(
            payload_id == ephemeral_backend_conversation_id if payload_id is not None else None
        ),
        mapping_present=mapping_present,
        mapping_node_count=mapping_node_count,
        current_node_present=current_node is not None,
        current_branch_node_count=branch_node_count,
        current_branch_message_count=len(roles),
        user_message_count=roles.count("user"),
        assistant_message_count=roles.count("assistant"),
        tool_message_count=roles.count("tool"),
        other_message_count=sum(
            1 for role in roles if role not in {"user", "assistant", "tool"}
        ),
        lifecycle_status=_optional_str(getattr(lifecycle, "status", None)),
        current_role=_optional_str(getattr(lifecycle, "role", None)),
        finish_reason_present=bool(_optional_str(getattr(lifecycle, "finish_reason", None))),
        raw_payload_exported=False,
        message_text_exported=False,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m chatgpt_web_adapter.temporary_chat_canonical_read_probe",
        description=(
            "Perform one read-only canonical direct-id characterization for an "
            "ephemeral backend id returned by a manually proven Temporary Chat. "
            "Explicitly confirm whether the original source Temporary tab is open "
            "or intentionally closed. No browser /c/<id> navigation, attach, "
            "continuation, or write is performed."
        ),
    )
    parser.add_argument("ephemeral_backend_conversation_id")
    parser.add_argument("--timeout", type=float, default=float(DEFAULT_TIMEOUT_SECONDS))
    parser.add_argument(
        "--source-temporary-tab-confirmed-open",
        action="store_true",
        help="confirm the original true Temporary Chat tab is still open (T4)",
    )
    parser.add_argument(
        "--source-temporary-tab-confirmed-closed",
        action="store_true",
        help="confirm the original true Temporary Chat tab was intentionally closed (T7a)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if (
        args.source_temporary_tab_confirmed_open
        == args.source_temporary_tab_confirmed_closed
    ):
        error = (
            "TEMPORARY_CANONICAL_READ_SOURCE_TAB_STATE_CONFLICT"
            if args.source_temporary_tab_confirmed_open
            else "TEMPORARY_CANONICAL_READ_SOURCE_TAB_STATE_CONFIRMATION_REQUIRED"
        )
        print(json.dumps({"ok": False, "error": error}, indent=2))
        return 2

    try:
        result = probe_temporary_canonical_read(
            args.ephemeral_backend_conversation_id,
            source_temporary_tab_confirmed_open=args.source_temporary_tab_confirmed_open,
            source_temporary_tab_confirmed_closed=args.source_temporary_tab_confirmed_closed,
            timeout=args.timeout,
        )
    except (AuthError, RequestError, OSError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, **result.to_dict()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
