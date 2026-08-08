from __future__ import annotations

from . import client as _client_module
from . import errors
from .approval_policy import ApprovalDecision, ApprovalPolicy
from .approval_types import ApprovalEvent, ApprovalResult, ApprovalRound
from .attach import attach_conversation as _attach_conversation
from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .client import ChatGPTWebClient
from .conversation_prepare import PrepareResult, prepare_text_turn
from .diagnostic_metrics import send_with_expanded_metrics as _send_with_expanded_metrics
from .prepared_text_send import send_existing_text_prepared as _send_existing_text_prepared
from .conversation_send import send_to_conversation as _send_to_conversation
from .exceptions import (
    AuthError,
    ConversationTimeoutError,
    MediaError,
    PayloadValidationError,
    RequestError,
    WebChatAdapterError,
)
from .export import export_conversation as _export_conversation
from .messages import get_messages as _get_messages
from .model_registry import (
    DEFAULT_MODEL,
    DEFAULT_THINKING_MODEL,
    MODEL_ALIASES,
    normalize_reasoning_effort as _normalize_reasoning_effort,
    resolve_model as _resolve_model,
)
from .payload_builder import PayloadBuilder
from .payload_validation import validate_payload
from .policy_approval import ApprovalDeniedError
from .policy_approval import approve_pending_action as _policy_approve_pending_action
from .policy_approval import send_and_auto_approve as _policy_send_and_auto_approve
from .policy_approval import wait_and_approve_pending_actions as _policy_wait_and_approve_pending_actions
from .raw_payload import send_payload as _send_payload
from .required_action import RequiredAction, find_required_action
from .required_action import get_required_action as _get_required_action
from .status import get_pending_approval as _get_pending_approval
from .status import get_status as _get_status
from .types import (
    AttachedConversation,
    AuthData,
    ChatConversation,
    ChatMessage,
    ChatMetrics,
    ChatRequestDiagnostics,
    ChatResponse,
    ConversationRef,
    ConversationStatus,
    MediaItem,
    MediaSource,
    PendingApproval,
    WaitResult,
)
from .wait import wait_until_completed as _wait_until_completed
from .web_session import (
    gate_get_ready_requirements as _gate_get_ready_requirements,
    redact_web_session_headers as _redact_web_session_headers,
)

# The registry is the canonical model-policy source. Keep the legacy monolithic
# client module synchronized at package import time until its policy constants can
# be physically removed without mixing that refactor into the live-contract PR.
_client_module.DEFAULT_MODEL = DEFAULT_MODEL
_client_module.DEFAULT_THINKING_MODEL = DEFAULT_THINKING_MODEL
_client_module.MODEL_ALIASES = MODEL_ALIASES
ChatGPTWebClient._normalize_reasoning_effort = staticmethod(_normalize_reasoning_effort)
ChatGPTWebClient._resolve_model = staticmethod(_resolve_model)

_original_send = ChatGPTWebClient.send
_original_approve_pending_action = ChatGPTWebClient.approve_pending_action
_original_send_and_auto_approve = ChatGPTWebClient.send_and_auto_approve
_original_get_ready_requirements = ChatGPTWebClient._get_ready_requirements
_original_sanitize_header_value = ChatGPTWebClient._sanitize_header_value

ChatGPTWebClient._get_ready_requirements = _gate_get_ready_requirements(
    _original_get_ready_requirements
)
ChatGPTWebClient._sanitize_header_value = _redact_web_session_headers(
    _original_sanitize_header_value
)
ChatGPTWebClient.approve_pending_action = _policy_approve_pending_action(
    _original_approve_pending_action
)
ChatGPTWebClient.attach_conversation = _attach_conversation
ChatGPTWebClient.export_conversation = _export_conversation
ChatGPTWebClient.get_messages = _get_messages
ChatGPTWebClient.get_pending_approval = _get_pending_approval
ChatGPTWebClient.get_required_action = _get_required_action
ChatGPTWebClient.get_status = _get_status
ChatGPTWebClient.send = _send_with_expanded_metrics(_original_send)
ChatGPTWebClient._send_existing_text_prepared = _send_with_expanded_metrics(
    _send_existing_text_prepared
)
ChatGPTWebClient.send_and_auto_approve = _policy_send_and_auto_approve(
    _original_send_and_auto_approve
)
ChatGPTWebClient.send_payload = _send_payload
ChatGPTWebClient.send_to_conversation = _send_to_conversation
ChatGPTWebClient.wait_and_approve_pending_actions = _policy_wait_and_approve_pending_actions
ChatGPTWebClient.wait_until_completed = _wait_until_completed
WebChatClient = ChatGPTWebClient

CORE_PUBLIC_API = [
    "ChatGPTWebClient",
    "WebChatClient",
    "ChatConversation",
    "AttachedConversation",
    "ChatMessage",
    "ConversationStatus",
    "PendingApproval",
    "ChatResponse",
    "ChatMetrics",
    "ChatRequestDiagnostics",
    "AuthData",
    "errors",
]

ERROR_EXPORTS = [
    "WebChatAdapterError",
    "AuthError",
    "ConversationTimeoutError",
    "MediaError",
    "PayloadValidationError",
    "RequestError",
]

ADVANCED_HELPERS = [
    "ConversationRef",
    "WaitResult",
]

MEDIA_EXPORTS = [
    "MediaItem",
    "MediaSource",
]

EXPERIMENTAL_APPROVAL_EXPORTS = [
    "ApprovalDecision",
    "ApprovalDeniedError",
    "ApprovalEvent",
    "ApprovalPolicy",
    "ApprovalResult",
    "ApprovalRound",
]

EXPERIMENTAL_REQUIRED_ACTION_EXPORTS = [
    "RequiredAction",
    "find_required_action",
]

EXPERIMENTAL_RAW_PAYLOAD_EXPORTS = [
    "PayloadBuilder",
    "validate_payload",
]

EXPERIMENTAL_PREPARE_EXPORTS = [
    "PrepareResult",
    "prepare_text_turn",
]

SUPPORT_EXPORTS = [
    "DEFAULT_AUTH_FILE",
    "DEFAULT_MODEL",
    "load_auth_data",
]

__all__ = [
    *CORE_PUBLIC_API,
    *ERROR_EXPORTS,
    *ADVANCED_HELPERS,
    *MEDIA_EXPORTS,
    *EXPERIMENTAL_APPROVAL_EXPORTS,
    *EXPERIMENTAL_REQUIRED_ACTION_EXPORTS,
    *EXPERIMENTAL_RAW_PAYLOAD_EXPORTS,
    *EXPERIMENTAL_PREPARE_EXPORTS,
    *SUPPORT_EXPORTS,
]
