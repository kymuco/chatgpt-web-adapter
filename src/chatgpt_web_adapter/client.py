from __future__ import annotations

from typing import Any

from . import legacy_client_core as _core
from .attach import attach_conversation as _attach_conversation
from .auth_refresh import refresh_auth_session as _refresh_auth_session
from .browser_native_client import (
    send_browser_native as _send_browser_native,
)
from .browser_native_client import (
    set_browser_native_turn_provider as _set_browser_native_turn_provider,
)
from .browserless_request_guards import gate_browserless_poll_deadline
from .canonical_conversation_snapshot import (
    get_conversation_snapshot as _get_conversation_snapshot,
)
from .conversation_read_v2 import (
    get_messages_v2 as _get_messages_v2,
)
from .conversation_read_v2 import (
    read_conversation_payload_v2 as _read_conversation_payload_v2,
)
from .conversation_send import send_to_conversation as _send_to_conversation
from .diagnostic_metrics import (
    send_with_expanded_metrics as _send_with_expanded_metrics,
)
from .export import export_conversation as _export_conversation
from .model_registry import (
    DEFAULT_MODEL as DEFAULT_MODEL,
)
from .model_registry import (
    DEFAULT_THINKING_MODEL as DEFAULT_THINKING_MODEL,
)
from .model_registry import (
    MODEL_ALIASES as MODEL_ALIASES,
)
from .model_registry import (
    normalize_reasoning_effort as _normalize_reasoning_effort,
)
from .model_registry import (
    resolve_model as _resolve_model,
)
from .payload_validation import validate_payload as _validate_payload
from .policy_approval import approve_pending_action as _policy_approve_pending_action
from .policy_approval import send_and_auto_approve as _policy_send_and_auto_approve
from .policy_approval import (
    wait_and_approve_pending_actions as _policy_wait_and_approve_pending_actions,
)
from .prepared_text_send import (
    send_existing_text_prepared as _send_existing_text_prepared,
)
from .raw_payload import send_payload as _send_payload
from .required_action import get_required_action as _get_required_action
from .sentinel_bundle import (
    gate_prepared_build_headers as _gate_prepared_build_headers,
)
from .sentinel_bundle import (
    gate_prepared_get_ready_requirements as _gate_prepared_get_ready_requirements,
)
from .sentinel_bundle import (
    gate_prepared_text_send as _gate_prepared_text_send,
)
from .sentinel_bundle import (
    get_prepared_sentinel_bundle as _get_prepared_sentinel_bundle,
)
from .sentinel_bundle import (
    prefetch_finalized_sentinel_bundle as _prefetch_finalized_sentinel_bundle,
)
from .sentinel_bundle import (
    redact_ephemeral_write_headers as _redact_ephemeral_write_headers,
)
from .sentinel_bundle import (
    start_finalized_sentinel_bundle_refill as _start_finalized_sentinel_bundle_refill,
)
from .sentinel_transaction import (
    set_sentinel_bundle_provider as _set_sentinel_bundle_provider,
)
from .sentinel_transaction import (
    set_sentinel_challenge_provider as _set_sentinel_challenge_provider,
)
from .status import get_pending_approval as _get_pending_approval
from .status import get_status as _get_status
from .wait import wait_until_completed as _wait_until_completed
from .web_session import (
    gate_debug_trace_writer as _gate_debug_trace_writer,
)
from .web_session import (
    gate_get_ready_requirements as _gate_get_ready_requirements,
)
from .web_session import (
    redact_web_session_headers as _redact_web_session_headers,
)

# Stable constants used by modules that participate in client composition.
DEFAULT_TIMEOUT_SECONDS = _core.DEFAULT_TIMEOUT_SECONDS
DEFAULT_STREAM_RECOVERY_POLL_TIMEOUT_SECONDS = (
    _core.DEFAULT_STREAM_RECOVERY_POLL_TIMEOUT_SECONDS
)
DEFAULT_STREAM_RECOVERY_POLL_INTERVAL_SECONDS = (
    _core.DEFAULT_STREAM_RECOVERY_POLL_INTERVAL_SECONDS
)

# Keep historical endpoint seams owned by the public client module. The frozen
# core retains its original values; composed calls resolve any patched endpoint
# at the curl-command boundary without mutating shared core globals.
CHAT_REQUIREMENTS_URL = _core.CHAT_REQUIREMENTS_URL
CHAT_BACKEND_URL = _core.CHAT_BACKEND_URL
CHAT_CONVERSATION_PREPARE_URL = _core.CHAT_CONVERSATION_PREPARE_URL
CHAT_CONVERSATION_URL = _core.CHAT_CONVERSATION_URL
CHAT_CONVERSATIONS_URL = _core.CHAT_CONVERSATIONS_URL
CHAT_FILES_URL = _core.CHAT_FILES_URL
CELSIUS_WS_USER_URL = _core.CELSIUS_WS_USER_URL


def _conversation_endpoint_override_active() -> bool:
    """Preserve the historical endpoint-override compatibility seam.

    PR12.3 deliberately kept endpoint constants patchable from this public module.
    A consumer that replaces either conversation endpoint is therefore opting into
    that historical contract; do not silently reinterpret its mock/server as the
    newer plural item endpoint.
    """

    return (
        CHAT_CONVERSATION_URL != _core.CHAT_CONVERSATION_URL
        or CHAT_CONVERSATIONS_URL != _core.CHAT_CONVERSATIONS_URL
    )


def _remap_legacy_endpoint(url: str) -> str:
    for historical, current in (
        (_core.CHAT_REQUIREMENTS_URL, CHAT_REQUIREMENTS_URL),
        (_core.CHAT_BACKEND_URL, CHAT_BACKEND_URL),
        (_core.CHAT_CONVERSATION_PREPARE_URL, CHAT_CONVERSATION_PREPARE_URL),
        (_core.CELSIUS_WS_USER_URL, CELSIUS_WS_USER_URL),
    ):
        if url == historical:
            return current

    for historical, current in (
        (_core.CHAT_CONVERSATIONS_URL, CHAT_CONVERSATIONS_URL),
        (_core.CHAT_FILES_URL, CHAT_FILES_URL),
    ):
        if url == historical:
            return current
        if url.startswith(f"{historical}/") or url.startswith(f"{historical}?"):
            return f"{current}{url[len(historical) :]}"

    marker = "{conversation_id}"
    historical_template = _core.CHAT_CONVERSATION_URL
    current_template = CHAT_CONVERSATION_URL
    if marker in historical_template and marker in current_template:
        historical_prefix = historical_template.split(marker, 1)[0]
        current_prefix = current_template.split(marker, 1)[0]
        if url.startswith(historical_prefix):
            return f"{current_prefix}{url[len(historical_prefix) :]}"

    return url


def __getattr__(name: str) -> Any:
    """Delegate untouched legacy module attributes to the frozen core.

    ``ChatGPTWebClient`` deliberately does not delegate while this module is being
    initialized: a composition helper importing the class too early must fail
    loudly rather than silently capture the uncomposed legacy base class.
    """

    if name == "ChatGPTWebClient":
        raise AttributeError(name)
    return getattr(_core, name)


_original_send = _core.ChatGPTWebClient.send


class ChatGPTWebClient(_core.ChatGPTWebClient):
    """Explicitly composed compatibility client over the frozen historical core."""

    _normalize_reasoning_effort = staticmethod(_normalize_reasoning_effort)
    _resolve_model = staticmethod(_resolve_model)
    _poll_conversation_after_prepare = gate_browserless_poll_deadline(
        _core.ChatGPTWebClient._poll_conversation_after_prepare
    )

    def _build_curl_command(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        header_path: str,
        body_path: str | None = None,
        *,
        no_buffer: bool = False,
        follow_redirects: bool = False,
    ) -> list[str]:
        return _core.ChatGPTWebClient._build_curl_command(
            self,
            method,
            _remap_legacy_endpoint(url),
            headers,
            header_path,
            body_path,
            no_buffer=no_buffer,
            follow_redirects=follow_redirects,
        )

    def _get_conversation_payload(self, conversation_id: str) -> dict[str, Any]:
        if _conversation_endpoint_override_active():
            return _core.ChatGPTWebClient._get_conversation_payload(
                self,
                conversation_id,
            )
        return _read_conversation_payload_v2(
            self,
            conversation_id,
            current_base_url=CHAT_CONVERSATIONS_URL,
            legacy_url_template=CHAT_CONVERSATION_URL,
            include_all_pages=False,
        )

    def _get_full_conversation_payload(self, conversation_id: str) -> dict[str, Any]:
        if _conversation_endpoint_override_active():
            return _core.ChatGPTWebClient._get_conversation_payload(
                self,
                conversation_id,
            )
        return _read_conversation_payload_v2(
            self,
            conversation_id,
            current_base_url=CHAT_CONVERSATIONS_URL,
            legacy_url_template=CHAT_CONVERSATION_URL,
            include_all_pages=True,
        )

    _get_ready_requirements = _gate_prepared_get_ready_requirements(
        _gate_get_ready_requirements(_core.ChatGPTWebClient._get_ready_requirements)
    )
    _get_prepared_sentinel_bundle = _get_prepared_sentinel_bundle
    prefetch_sentinel_bundle = _prefetch_finalized_sentinel_bundle
    start_sentinel_bundle_refill = _start_finalized_sentinel_bundle_refill
    set_sentinel_challenge_provider = _set_sentinel_challenge_provider
    set_sentinel_bundle_provider = _set_sentinel_bundle_provider
    set_browser_native_turn_provider = _set_browser_native_turn_provider
    send_browser_native = _send_browser_native
    refresh_auth = _refresh_auth_session

    _build_headers = _gate_prepared_build_headers(_core.ChatGPTWebClient._build_headers)
    _sanitize_header_value = _redact_ephemeral_write_headers(
        _redact_web_session_headers(_core.ChatGPTWebClient._sanitize_header_value)
    )
    _write_debug_trace = _gate_debug_trace_writer(
        _core.ChatGPTWebClient._write_debug_trace
    )

    approve_pending_action = _policy_approve_pending_action(
        _core.ChatGPTWebClient.approve_pending_action
    )
    attach_conversation = _attach_conversation
    export_conversation = _export_conversation
    get_conversation_snapshot = _get_conversation_snapshot
    get_messages = _get_messages_v2
    get_pending_approval = _get_pending_approval
    get_required_action = _get_required_action
    get_status = _get_status

    send = _send_with_expanded_metrics(
        _gate_prepared_text_send(_original_send, require_provider=False)
    )
    _send_existing_text_prepared = _send_with_expanded_metrics(
        _gate_prepared_text_send(_send_existing_text_prepared)
    )
    send_and_auto_approve = _policy_send_and_auto_approve(
        _core.ChatGPTWebClient.send_and_auto_approve
    )
    send_payload = _send_payload
    send_to_conversation = _send_to_conversation
    wait_and_approve_pending_actions = _policy_wait_and_approve_pending_actions
    wait_until_completed = _wait_until_completed


# Keep the historical module-level validation helper available through the public
# module without mutating the frozen legacy core.
validate_payload = _validate_payload
