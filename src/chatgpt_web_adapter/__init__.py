from __future__ import annotations

from . import client as _client_module
from . import errors
from .approval_policy import ApprovalDecision, ApprovalPolicy
from .approval_types import ApprovalEvent, ApprovalResult, ApprovalRound
from .attach import attach_conversation as _attach_conversation
from .auth import DEFAULT_AUTH_FILE, load_auth_data
from .auth_browser import BrowserLoginResult, browser_login, default_browser_profile_dir
from .auth_refresh import (
    AuthRefreshResult,
    refresh_auth_session as _refresh_auth_session,
)
from .auth_status import AuthStatus, get_auth_status
from .browser_native_client import (
    send_browser_native as _send_browser_native,
    set_browser_native_turn_provider as _set_browser_native_turn_provider,
)
from .browser_native_install import (
    BrowserNativeInstallResult,
    EXTENSION_ID as BROWSER_NATIVE_EXTENSION_ID,
    browser_native_extension_dir,
    install_native_messaging_host,
)
from .browser_native_provider import (
    BrowserNativeBridgeStatus,
    BrowserNativeTurnProvider,
    BrowserNativeTurnResult,
)
from .browser_sentinel import ZendriverSentinelBundleProvider
from .browserless_request_guards import (
    gate_browserless_canonical_finalize as _gate_browserless_canonical_finalize,
    install_browserless_poll_deadline_guard as _install_browserless_poll_deadline_guard,
)
from .browserless_request_scope import (
    gate_browserless_request_execute as _gate_browserless_request_execute,
    gate_browserless_request_health as _gate_browserless_request_health,
)
from .browserless_shared_write_fence import (
    gate_browserless_transport_init as _gate_browserless_transport_init,
)
from .client import ChatGPTWebClient
from .conversation_prepare import PrepareResult, prepare_text_turn
from .diagnostic_metrics import send_with_expanded_metrics as _send_with_expanded_metrics
from .prepared_text_send import send_existing_text_prepared as _send_existing_text_prepared
from .product_capabilities import (
    ORDINARY_CHATGPT_PRODUCT_SEMANTICS,
    PRODUCT_CAPABILITY_NAMES,
    CapabilityOwner,
    CapabilityState,
    ProductCapabilities,
    ProductCapability,
)
from .product_contract import ProductRuntimeContract, product_runtime_contract
from .product_observations import (
    ProductActivityObservation,
    ProductCitationObservation,
    ProductObservationKind,
    ProductObservationPhase,
    ProductRequiredActionObservation,
    ProductSourceObservation,
    StructuredProductObservation,
)
from .product_provenance import (
    CompletionSource,
    ProductCompletionProvenance,
    ProductExecutionProvenance,
    ProductIdentityProvenance,
)
from .product_runtime import (
    BROWSER_OWNED_PRODUCT_TRANSPORT,
    DEFAULT_PRODUCT_TRANSPORT,
    SUPPORTED_PRODUCT_TRANSPORTS,
    ChatGPTProductRuntime,
    ProductRuntimeExecution,
    ProductRuntimeHealth,
    assemble_product_runtime,
)
from .product_runtime_observation_gate import (
    gate_product_runtime_send_text_observed as _gate_product_runtime_send_text_observed,
)
from .product_submission import (
    ProductSubmissionAck,
    ProductSubmissionProvenance,
    SubmissionEvidenceSource,
)
from .product_support import (
    PRODUCT_RUNTIME_CONTRACT_SCHEMA,
    ProductTransportSupportTier,
    product_transport_support_tier,
)
from .product_transport import CanonicalConversationClient, ProductWriteTransport
from .product_ui_liveness import (
    BrowserUILivenessObservation,
    BrowserUILivenessState,
)
from .public_surface import (
    PUBLIC_SURFACE_CLASSIFICATION,
    PUBLIC_SURFACE_TIERS,
    PRIMARY_PRODUCT_RUNTIME_EXPORTS,
    PublicSurfaceTier,
    public_surface_tier,
)
from .sentinel_requirements import (
    OBSERVED_FINALIZE_REQUEST_KEYS,
    OBSERVED_FINALIZE_RESPONSE_KEYS,
    SentinelPrepareProbeResult,
    probe_sentinel_requirements_prepare,
)
from .sentinel_bundle import (
    gate_prepared_build_headers as _gate_prepared_build_headers,
    gate_prepared_get_ready_requirements as _gate_prepared_get_ready_requirements,
    gate_prepared_text_send as _gate_prepared_text_send,
    get_prepared_sentinel_bundle as _get_prepared_sentinel_bundle,
    prefetch_finalized_sentinel_bundle as _prefetch_finalized_sentinel_bundle,
    redact_ephemeral_write_headers as _redact_ephemeral_write_headers,
    start_finalized_sentinel_bundle_refill as _start_finalized_sentinel_bundle_refill,
)
from .sentinel_transaction import (
    FinalizedSentinelBundle,
    SentinelBundleProvider,
    SentinelChallengeContext,
    SentinelChallengeEvidence,
    SentinelChallengeProvider,
    set_sentinel_bundle_provider as _set_sentinel_bundle_provider,
    set_sentinel_challenge_provider as _set_sentinel_challenge_provider,
)
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
    gate_debug_trace_writer as _gate_debug_trace_writer,
    gate_get_ready_requirements as _gate_get_ready_requirements,
    redact_web_session_headers as _redact_web_session_headers,
)

# The registry is the canonical model-policy source. Keep the legacy monolithic
# client module synchronized at package import time until its policy constants can
# be physically removed without mixing that refactor into the product-runtime work.
_client_module.DEFAULT_MODEL = DEFAULT_MODEL
_client_module.DEFAULT_THINKING_MODEL = DEFAULT_THINKING_MODEL
_client_module.MODEL_ALIASES = MODEL_ALIASES
ChatGPTWebClient._normalize_reasoning_effort = staticmethod(_normalize_reasoning_effort)
ChatGPTWebClient._resolve_model = staticmethod(_resolve_model)
_install_browserless_poll_deadline_guard(_client_module, ChatGPTWebClient)

_original_send = ChatGPTWebClient.send
_original_approve_pending_action = ChatGPTWebClient.approve_pending_action
_original_send_and_auto_approve = ChatGPTWebClient.send_and_auto_approve
_original_get_ready_requirements = ChatGPTWebClient._get_ready_requirements
_original_build_headers = ChatGPTWebClient._build_headers
_original_sanitize_header_value = ChatGPTWebClient._sanitize_header_value
_original_write_debug_trace = ChatGPTWebClient._write_debug_trace

ChatGPTWebClient._get_ready_requirements = _gate_prepared_get_ready_requirements(
    _gate_get_ready_requirements(_original_get_ready_requirements)
)
ChatGPTWebClient._get_prepared_sentinel_bundle = _get_prepared_sentinel_bundle
ChatGPTWebClient.prefetch_sentinel_bundle = _prefetch_finalized_sentinel_bundle
ChatGPTWebClient.start_sentinel_bundle_refill = _start_finalized_sentinel_bundle_refill
ChatGPTWebClient.set_sentinel_challenge_provider = _set_sentinel_challenge_provider
ChatGPTWebClient.set_sentinel_bundle_provider = _set_sentinel_bundle_provider
ChatGPTWebClient.set_browser_native_turn_provider = _set_browser_native_turn_provider
ChatGPTWebClient.send_browser_native = _send_browser_native
ChatGPTWebClient.refresh_auth = _refresh_auth_session
ChatGPTWebClient._build_headers = _gate_prepared_build_headers(_original_build_headers)
ChatGPTWebClient._sanitize_header_value = _redact_ephemeral_write_headers(
    _redact_web_session_headers(_original_sanitize_header_value)
)
ChatGPTWebClient._write_debug_trace = _gate_debug_trace_writer(
    _original_write_debug_trace
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
ChatGPTWebClient.send = _send_with_expanded_metrics(
    _gate_prepared_text_send(_original_send, require_provider=False)
)
ChatGPTWebClient._send_existing_text_prepared = _send_with_expanded_metrics(
    _gate_prepared_text_send(_send_existing_text_prepared)
)
ChatGPTWebClient.send_and_auto_approve = _policy_send_and_auto_approve(
    _original_send_and_auto_approve
)
ChatGPTWebClient.send_payload = _send_payload
ChatGPTWebClient.send_to_conversation = _send_to_conversation
ChatGPTWebClient.wait_and_approve_pending_actions = _policy_wait_and_approve_pending_actions
ChatGPTWebClient.wait_until_completed = _wait_until_completed

# Browserless owns one request scope spanning canonical attach, Sentinel preflight,
# the prepared mutation, and canonical reconciliation. Conversation-scoped health
# reads share the same no-replay header policy without acquiring mutation authority
# or inventing a write deadline. Finality additionally correlates canonical
# readback with the submitted assistant identity. Construction also fences the
# shared client's ordinary mutation entrypoints with the same per-client RLock,
# preventing a same-client continuation write from advancing the attached parent
# during browserless Sentinel preflight. These wrappers are installed at package
# import time like the other compatibility gates above.
from .browserless_request_transport import BrowserlessRequestTransport as _BrowserlessRequestTransport

_original_browserless_request_init = _BrowserlessRequestTransport.__init__
_BrowserlessRequestTransport.__init__ = _gate_browserless_transport_init(
    _original_browserless_request_init
)
_original_browserless_canonical_finalize = _BrowserlessRequestTransport._canonical_finalize
_BrowserlessRequestTransport._canonical_finalize = _gate_browserless_canonical_finalize(
    _original_browserless_canonical_finalize
)
_original_browserless_request_health = _BrowserlessRequestTransport.health
_BrowserlessRequestTransport.health = _gate_browserless_request_health(
    _original_browserless_request_health
)
_original_browserless_request_execute = _BrowserlessRequestTransport._execute
_BrowserlessRequestTransport._execute = _gate_browserless_request_execute(
    _original_browserless_request_execute
)

# PR9.3 installs structured product observation as a non-authoritative runtime
# gate. The underlying runtime remains the owner of transport dispatch, canonical
# finality, and provenance; this wrapper only derives immutable observations from
# the already-standardized event stream returned during send_text_observed().
_original_product_runtime_send_text_observed = ChatGPTProductRuntime.send_text_observed
ChatGPTProductRuntime.send_text_observed = _gate_product_runtime_send_text_observed(
    _original_product_runtime_send_text_observed
)

WebChatClient = ChatGPTWebClient

# The historical core prefix remains import-compatible. The forward-looking
# production API is PRODUCT_RUNTIME_EXPORTS below.
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

PRODUCT_RUNTIME_EXPORTS = list(PRIMARY_PRODUCT_RUNTIME_EXPORTS)

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

SUPPORT_EXPORTS = [
    "AuthStatus",
    "AuthRefreshResult",
    "BrowserLoginResult",
    "DEFAULT_AUTH_FILE",
    "DEFAULT_MODEL",
    "browser_login",
    "default_browser_profile_dir",
    "get_auth_status",
    "load_auth_data",
]

PUBLIC_SURFACE_METADATA_EXPORTS = [
    "PublicSurfaceTier",
    "PUBLIC_SURFACE_TIERS",
    "PUBLIC_SURFACE_CLASSIFICATION",
    "public_surface_tier",
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

# Kept import-compatible, but classified as research/diagnostic.
EXPERIMENTAL_SENTINEL_EXPORTS = [
    "FinalizedSentinelBundle",
    "OBSERVED_FINALIZE_REQUEST_KEYS",
    "OBSERVED_FINALIZE_RESPONSE_KEYS",
    "SentinelBundleProvider",
    "SentinelChallengeContext",
    "SentinelChallengeEvidence",
    "SentinelChallengeProvider",
    "SentinelPrepareProbeResult",
    "ZendriverSentinelBundleProvider",
    "probe_sentinel_requirements_prepare",
]

# Kept import-compatible, but direct low-level use is research/diagnostic. The
# production runtime consumes the browser-native implementation behind its
# ProductWriteTransport boundary.
EXPERIMENTAL_BROWSER_NATIVE_EXPORTS = [
    "BROWSER_NATIVE_EXTENSION_ID",
    "BrowserNativeBridgeStatus",
    "BrowserNativeInstallResult",
    "BrowserNativeTurnProvider",
    "BrowserNativeTurnResult",
    "browser_native_extension_dir",
    "install_native_messaging_host",
]

__all__ = [
    # Historical prefix retained for compatibility.
    *CORE_PUBLIC_API,
    # Primary production surface is intentionally promoted before legacy extras.
    *PRODUCT_RUNTIME_EXPORTS,
    *ERROR_EXPORTS,
    *ADVANCED_HELPERS,
    *MEDIA_EXPORTS,
    *SUPPORT_EXPORTS,
    *PUBLIC_SURFACE_METADATA_EXPORTS,
    # Lower-support-level compatibility exports remain available.
    *EXPERIMENTAL_APPROVAL_EXPORTS,
    *EXPERIMENTAL_REQUIRED_ACTION_EXPORTS,
    *EXPERIMENTAL_RAW_PAYLOAD_EXPORTS,
    *EXPERIMENTAL_PREPARE_EXPORTS,
    *EXPERIMENTAL_SENTINEL_EXPORTS,
    *EXPERIMENTAL_BROWSER_NATIVE_EXPORTS,
]
