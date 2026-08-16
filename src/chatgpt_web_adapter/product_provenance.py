from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .product_capabilities import ORDINARY_CHATGPT_PRODUCT_SEMANTICS


class CompletionSource(str, Enum):
    """Highest-level evidence source proving a successful returned execution."""

    CANONICAL_READBACK = "CANONICAL_READBACK"
    TRANSPORT_RETURN = "TRANSPORT_RETURN"


class ConversationMode(str, Enum):
    NORMAL = "NORMAL"
    TEMPORARY = "TEMPORARY"
    UNKNOWN = "UNKNOWN"


class ConversationModeEvidenceSource(str, Enum):
    TRANSPORT_SEMANTICS_CONTRACT = "TRANSPORT_SEMANTICS_CONTRACT"
    PRODUCT_MODE_OBSERVATION = "PRODUCT_MODE_OBSERVATION"
    NONE = "NONE"


class TemporaryLifecycleState(str, Enum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    LIVE = "LIVE"
    ENDED = "ENDED"
    UNKNOWN = "UNKNOWN"


class TemporaryLifecycleEvidenceSource(str, Enum):
    RUNTIME_GOVERNANCE_CONTRACT = "RUNTIME_GOVERNANCE_CONTRACT"
    PRODUCT_LIFECYCLE_OBSERVATION = "PRODUCT_LIFECYCLE_OBSERVATION"
    NONE = "NONE"


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _conversation_mode(value: ConversationMode | str) -> ConversationMode:
    if isinstance(value, ConversationMode):
        return value
    if not isinstance(value, str):
        raise TypeError("conversation mode must be a string or ConversationMode")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("conversation mode must not be empty")
    return ConversationMode(normalized)


def _conversation_mode_evidence_source(
    value: ConversationModeEvidenceSource | str,
) -> ConversationModeEvidenceSource:
    if isinstance(value, ConversationModeEvidenceSource):
        return value
    if not isinstance(value, str):
        raise TypeError(
            "conversation mode evidence source must be a string or ConversationModeEvidenceSource"
        )
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("conversation mode evidence source must not be empty")
    return ConversationModeEvidenceSource(normalized)


def _temporary_lifecycle_state(
    value: TemporaryLifecycleState | str,
) -> TemporaryLifecycleState:
    if isinstance(value, TemporaryLifecycleState):
        return value
    if not isinstance(value, str):
        raise TypeError(
            "temporary lifecycle state must be a string or TemporaryLifecycleState"
        )
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("temporary lifecycle state must not be empty")
    return TemporaryLifecycleState(normalized)


def _temporary_lifecycle_evidence_source(
    value: TemporaryLifecycleEvidenceSource | str,
) -> TemporaryLifecycleEvidenceSource:
    if isinstance(value, TemporaryLifecycleEvidenceSource):
        return value
    if not isinstance(value, str):
        raise TypeError(
            "temporary lifecycle evidence source must be a string or "
            "TemporaryLifecycleEvidenceSource"
        )
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("temporary lifecycle evidence source must not be empty")
    return TemporaryLifecycleEvidenceSource(normalized)


def _safe_observation_dict(observation: Any) -> dict[str, Any]:
    if isinstance(observation, Mapping):
        return copy.deepcopy(dict(observation))
    to_dict = getattr(observation, "to_dict", None)
    if callable(to_dict):
        try:
            payload = to_dict()
        except Exception:
            return {}
        if isinstance(payload, Mapping):
            return copy.deepcopy(dict(payload))
    return {}


@dataclass(frozen=True)
class ProductCompletionProvenance:
    completed: bool
    source: CompletionSource
    canonical_completion_proven: bool
    finish_reason: str | None
    finish_reason_observed: bool
    finality_detail: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, CompletionSource):
            object.__setattr__(self, "source", CompletionSource(self.source))
        finish_reason = _optional_text(self.finish_reason)
        object.__setattr__(self, "finish_reason", finish_reason)
        object.__setattr__(self, "finish_reason_observed", finish_reason is not None)
        object.__setattr__(self, "finality_detail", _optional_text(self.finality_detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": bool(self.completed),
            "source": self.source.value,
            "canonical_completion_proven": bool(self.canonical_completion_proven),
            "finish_reason": self.finish_reason,
            "finish_reason_observed": self.finish_reason_observed,
            "finality_detail": self.finality_detail,
        }


@dataclass(frozen=True)
class ProductIdentityProvenance:
    conversation_id: str | None
    message_id: str | None
    observed_model: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", _optional_text(self.conversation_id))
        object.__setattr__(self, "message_id", _optional_text(self.message_id))
        object.__setattr__(self, "observed_model", _optional_text(self.observed_model))

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "observed_model": self.observed_model,
        }


@dataclass(frozen=True)
class ProductConversationModeProvenance:
    requested_conversation_mode: ConversationMode
    observed_conversation_mode: ConversationMode
    observed_mode_evidence_source: ConversationModeEvidenceSource
    observed_mode_proven: bool
    proof_detail: str | None = None

    def __post_init__(self) -> None:
        requested = _conversation_mode(self.requested_conversation_mode)
        observed = _conversation_mode(self.observed_conversation_mode)
        source = _conversation_mode_evidence_source(self.observed_mode_evidence_source)
        if not isinstance(self.observed_mode_proven, bool):
            raise TypeError("observed_mode_proven must be a bool")
        proven = self.observed_mode_proven
        if proven and observed is ConversationMode.UNKNOWN:
            raise ValueError("proven observed conversation mode cannot be UNKNOWN")
        if not proven and observed is not ConversationMode.UNKNOWN:
            raise ValueError("unproven observed conversation mode must be UNKNOWN")
        if proven and source is ConversationModeEvidenceSource.NONE:
            raise ValueError("proven observed conversation mode requires an evidence source")
        if not proven and source is not ConversationModeEvidenceSource.NONE:
            raise ValueError("unproven observed conversation mode must use evidence source NONE")
        object.__setattr__(self, "requested_conversation_mode", requested)
        object.__setattr__(self, "observed_conversation_mode", observed)
        object.__setattr__(self, "observed_mode_evidence_source", source)
        object.__setattr__(self, "proof_detail", _optional_text(self.proof_detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_conversation_mode": self.requested_conversation_mode.value,
            "observed_conversation_mode": self.observed_conversation_mode.value,
            "observed_mode_evidence_source": self.observed_mode_evidence_source.value,
            "observed_mode_proven": self.observed_mode_proven,
            "proof_detail": self.proof_detail,
        }


@dataclass(frozen=True)
class ProductTemporaryLifecycleProvenance:
    temporary_lifecycle_state: TemporaryLifecycleState
    lifecycle_evidence_source: TemporaryLifecycleEvidenceSource
    lifecycle_state_proven: bool
    live_write_authority_proven: bool
    proof_detail: str | None = None

    def __post_init__(self) -> None:
        state = _temporary_lifecycle_state(self.temporary_lifecycle_state)
        source = _temporary_lifecycle_evidence_source(self.lifecycle_evidence_source)
        if not isinstance(self.lifecycle_state_proven, bool):
            raise TypeError("lifecycle_state_proven must be a bool")
        if not isinstance(self.live_write_authority_proven, bool):
            raise TypeError("live_write_authority_proven must be a bool")
        if self.lifecycle_state_proven:
            if state is TemporaryLifecycleState.UNKNOWN:
                raise ValueError("proven temporary lifecycle state cannot be UNKNOWN")
            if source is TemporaryLifecycleEvidenceSource.NONE:
                raise ValueError(
                    "proven temporary lifecycle state requires an evidence source"
                )
        else:
            if state is not TemporaryLifecycleState.UNKNOWN:
                raise ValueError("unproven temporary lifecycle state must be UNKNOWN")
            if source is not TemporaryLifecycleEvidenceSource.NONE:
                raise ValueError(
                    "unproven temporary lifecycle state must use evidence source NONE"
                )
        if self.live_write_authority_proven and (
            not self.lifecycle_state_proven
            or state is not TemporaryLifecycleState.LIVE
        ):
            raise ValueError(
                "live Temporary write authority requires a proven LIVE lifecycle"
            )
        object.__setattr__(self, "temporary_lifecycle_state", state)
        object.__setattr__(self, "lifecycle_evidence_source", source)
        object.__setattr__(self, "proof_detail", _optional_text(self.proof_detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "temporary_lifecycle_state": self.temporary_lifecycle_state.value,
            "lifecycle_evidence_source": self.lifecycle_evidence_source.value,
            "lifecycle_state_proven": self.lifecycle_state_proven,
            "live_write_authority_proven": self.live_write_authority_proven,
            "proof_detail": self.proof_detail,
        }


@dataclass(frozen=True)
class ProductExecutionProvenance:
    product_semantics: str
    transport: str
    write_plane: str | None
    readback_plane: str | None
    session_plane: str | None
    completion: ProductCompletionProvenance
    identity: ProductIdentityProvenance
    transport_metadata: dict[str, Any]
    conversation_mode: ProductConversationModeProvenance | None = None
    temporary_lifecycle: ProductTemporaryLifecycleProvenance | None = None

    def __post_init__(self) -> None:
        product_semantics = _optional_text(self.product_semantics)
        transport = _optional_text(self.transport)
        if product_semantics is None:
            raise ValueError("product_semantics is required")
        if transport is None:
            raise ValueError("transport is required")
        if not isinstance(self.completion, ProductCompletionProvenance):
            raise TypeError("completion must be ProductCompletionProvenance")
        if not isinstance(self.identity, ProductIdentityProvenance):
            raise TypeError("identity must be ProductIdentityProvenance")
        if not isinstance(self.transport_metadata, dict):
            raise TypeError("transport_metadata must be a dict")
        if self.conversation_mode is not None and not isinstance(
            self.conversation_mode,
            ProductConversationModeProvenance,
        ):
            raise TypeError(
                "conversation_mode must be ProductConversationModeProvenance or None"
            )
        if self.temporary_lifecycle is not None and not isinstance(
            self.temporary_lifecycle,
            ProductTemporaryLifecycleProvenance,
        ):
            raise TypeError(
                "temporary_lifecycle must be ProductTemporaryLifecycleProvenance or None"
            )
        object.__setattr__(self, "product_semantics", product_semantics.lower())
        object.__setattr__(self, "transport", transport.lower())
        object.__setattr__(self, "write_plane", _optional_text(self.write_plane))
        object.__setattr__(self, "readback_plane", _optional_text(self.readback_plane))
        object.__setattr__(self, "session_plane", _optional_text(self.session_plane))
        object.__setattr__(self, "transport_metadata", copy.deepcopy(self.transport_metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_semantics": self.product_semantics,
            "transport": self.transport,
            "write_plane": self.write_plane,
            "readback_plane": self.readback_plane,
            "session_plane": self.session_plane,
            "completion": self.completion.to_dict(),
            "identity": self.identity.to_dict(),
            "transport_metadata": copy.deepcopy(self.transport_metadata),
            "conversation_mode": (
                self.conversation_mode.to_dict()
                if self.conversation_mode is not None
                else None
            ),
            "temporary_lifecycle": (
                self.temporary_lifecycle.to_dict()
                if self.temporary_lifecycle is not None
                else None
            ),
        }


def build_product_execution_provenance(
    *,
    transport: str,
    response: Any,
    observation: Any,
    governance: Mapping[str, Any] | None,
    conversation_mode: ProductConversationModeProvenance | None = None,
    temporary_lifecycle: ProductTemporaryLifecycleProvenance | None = None,
) -> ProductExecutionProvenance:
    """Build generic provenance without inventing backend completion metadata.

    A successful runtime execution is complete by contract. When transport
    governance says canonical readback is required, that is the strongest
    high-level completion source we can state without claiming which private
    message field supplied the finality signal. Nullable ``finish_reason`` is
    preserved exactly as observed instead of being synthesized.
    """

    if conversation_mode is not None and not isinstance(
        conversation_mode,
        ProductConversationModeProvenance,
    ):
        raise TypeError(
            "conversation_mode must be ProductConversationModeProvenance or None"
        )

    if temporary_lifecycle is not None and not isinstance(
        temporary_lifecycle,
        ProductTemporaryLifecycleProvenance,
    ):
        raise TypeError(
            "temporary_lifecycle must be ProductTemporaryLifecycleProvenance or None"
        )

    governance_payload = dict(governance or {})
    canonical_required = governance_payload.get("canonical_readback_required") is True
    source = (
        CompletionSource.CANONICAL_READBACK
        if canonical_required
        else CompletionSource.TRANSPORT_RETURN
    )

    conversation = getattr(response, "conversation", None)
    request = getattr(response, "request", None)
    finish_reason = _optional_text(getattr(conversation, "finish_reason", None))

    completion = ProductCompletionProvenance(
        completed=True,
        source=source,
        canonical_completion_proven=canonical_required,
        finish_reason=finish_reason,
        finish_reason_observed=finish_reason is not None,
        finality_detail=None,
    )
    identity = ProductIdentityProvenance(
        conversation_id=getattr(conversation, "conversation_id", None),
        message_id=getattr(conversation, "message_id", None),
        observed_model=getattr(request, "observed_model", None),
    )

    product_semantics = _optional_text(governance_payload.get("product_semantics"))
    if product_semantics is None:
        product_semantics = ORDINARY_CHATGPT_PRODUCT_SEMANTICS

    return ProductExecutionProvenance(
        product_semantics=product_semantics,
        transport=transport,
        write_plane=_optional_text(governance_payload.get("write_plane")),
        readback_plane=_optional_text(governance_payload.get("read_plane")),
        session_plane=_optional_text(governance_payload.get("session_plane")),
        completion=completion,
        identity=identity,
        transport_metadata=_safe_observation_dict(observation),
        conversation_mode=conversation_mode,
        temporary_lifecycle=temporary_lifecycle,
    )
