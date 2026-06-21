from __future__ import annotations

from .approval_policy import ApprovalDecision, ApprovalPolicy
from .approval_types import ApprovalEvent, ApprovalResult, ApprovalRound
from .attach import attach_conversation as _attach_conversation
from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .client import DEFAULT_MODEL, ChatGPTWebClient
from .conversation_send import send_to_conversation as _send_to_conversation
from .exceptions import (
    AuthError,
    ConversationTimeoutError,
    MediaError,
    RequestError,
    WebChatAdapterError,
)
from .export import export_conversation as _export_conversation
from .messages import get_messages as _get_messages
from .policy_approval import ApprovalDeniedError
from .policy_approval import approve_pending_action as _policy_approve_pending_action
from .policy_approval import send_and_auto_approve as _policy_send_and_auto_approve
from .policy_approval import wait_and_approve_pending_actions as _policy_wait_and_approve_pending_actions
from .status import get_pending_approval as _get_pending_approval
from .status import get_status as _get_status
from .types import (
    AttachedConversation,
    AuthData,
    ChatConversation,
    ChatMessage,
    ChatMetrics,
    ChatResponse,
    ConversationRef,
    ConversationStatus,
    MediaItem,
    MediaSource,
    PendingApproval,
    WaitResult,
)
from .wait import wait_until_completed as _wait_until_completed

_original_approve_pending_action = ChatGPTWebClient.approve_pending_action
_original_send_and_auto_approve = ChatGPTWebClient.send_and_auto_approve

ChatGPTWebClient.approve_pending_action = _policy_approve_pending_action(
    _original_approve_pending_action
)
ChatGPTWebClient.attach_conversation = _attach_conversation
ChatGPTWebClient.export_conversation = _export_conversation
ChatGPTWebClient.get_messages = _get_messages
ChatGPTWebClient.get_pending_approval = _get_pending_approval
ChatGPTWebClient.get_status = _get_status
ChatGPTWebClient.send_and_auto_approve = _policy_send_and_auto_approve(
    _original_send_and_auto_approve
)
ChatGPTWebClient.send_to_conversation = _send_to_conversation
ChatGPTWebClient.wait_and_approve_pending_actions = _policy_wait_and_approve_pending_actions
ChatGPTWebClient.wait_until_completed = _wait_until_completed
WebChatClient = ChatGPTWebClient

__all__ = [
    "ApprovalDecision",
    "ApprovalDeniedError",
    "ApprovalEvent",
    "ApprovalPolicy",
    "ApprovalResult",
    "ApprovalRound",
    "AttachedConversation",
    "AuthData",
    "AuthError",
    "ChatConversation",
    "ChatGPTWebClient",
    "ChatMessage",
    "ChatMetrics",
    "ChatResponse",
    "ConversationRef",
    "ConversationStatus",
    "ConversationTimeoutError",
    "DEFAULT_AUTH_FILE",
    "DEFAULT_MODEL",
    "MediaError",
    "MediaItem",
    "MediaSource",
    "PendingApproval",
    "RequestError",
    "WaitResult",
    "WebChatAdapterError",
    "WebChatClient",
    "load_auth_data",
]
