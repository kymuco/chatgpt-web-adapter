from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .product_capabilities import ORDINARY_CHATGPT_PRODUCT_SEMANTICS


class SubmissionEvidenceSource(str, Enum):
    """Evidence that a product write crossed the submission boundary."""

    BROWSER_NATIVE_WRITE_COMPLETED = "BROWSER_NATIVE_WRITE_COMPLETED"


def _required_text(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("optional text values must be strings or None")
    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True)
class ProductSubmissionProvenance:
    """Bounded evidence for submission acceptance, never finality authority."""

    product_semantics: str
    transport: str
    write_plane: str
    evidence_source: SubmissionEvidenceSource
    write_acknowledged: bool
    canonical_finality_proven: bool
    automatic_write_retry: bool
    fallback_transport: str | None

    def __post_init__(self) -> None:
        semantics = _required_text(self.product_semantics, name="product_semantics").lower()
        transport = _required_text(self.transport, name="transport").lower()
        write_plane = _required_text(self.write_plane, name="write_plane")
        source = self.evidence_source
        if not isinstance(source, SubmissionEvidenceSource):
            source = SubmissionEvidenceSource(source)
        if semantics != ORDINARY_CHATGPT_PRODUCT_SEMANTICS:
            raise ValueError("submission provenance requires ordinary ChatGPT product semantics")
        if self.write_acknowledged is not True:
            raise ValueError("successful submission provenance requires write_acknowledged=True")
        if self.canonical_finality_proven is not False:
            raise ValueError("submission acknowledgement cannot prove canonical finality")
        if self.automatic_write_retry is not False:
            raise ValueError("submission acknowledgement requires automatic_write_retry=False")
        if self.fallback_transport is not None:
            raise ValueError("submission acknowledgement requires fallback_transport=None")
        object.__setattr__(self, "product_semantics", semantics)
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "write_plane", write_plane)
        object.__setattr__(self, "evidence_source", source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_semantics": self.product_semantics,
            "transport": self.transport,
            "write_plane": self.write_plane,
            "evidence_source": self.evidence_source.value,
            "write_acknowledged": self.write_acknowledged,
            "canonical_finality_proven": self.canonical_finality_proven,
            "automatic_write_retry": self.automatic_write_retry,
            "fallback_transport": self.fallback_transport,
        }


@dataclass(frozen=True)
class ProductSubmissionAck:
    """First-class accepted-write handle used later by ``await_final``.

    This object proves that the selected transport acknowledged one submission.
    It intentionally does not claim that an assistant message is complete or that
    canonical readback has succeeded.
    """

    submission_id: str
    transport: str
    conversation_id: str | None
    turn_exchange_id: str | None
    accepted_at_ms: int
    turn_lifecycle_id: str | None
    write_may_have_committed: bool
    automatic_retry_allowed: bool
    canonical_finality_proven: bool
    provenance: ProductSubmissionProvenance

    def __post_init__(self) -> None:
        submission_id = _required_text(self.submission_id, name="submission_id")
        transport = _required_text(self.transport, name="transport").lower()
        conversation_id = _optional_text(self.conversation_id)
        turn_exchange_id = _optional_text(self.turn_exchange_id)
        turn_lifecycle_id = _optional_text(self.turn_lifecycle_id)
        if not isinstance(self.accepted_at_ms, int) or isinstance(self.accepted_at_ms, bool):
            raise TypeError("accepted_at_ms must be an integer")
        if self.accepted_at_ms <= 0:
            raise ValueError("accepted_at_ms must be positive")
        if self.write_may_have_committed is not True:
            raise ValueError("accepted submission must set write_may_have_committed=True")
        if self.automatic_retry_allowed is not False:
            raise ValueError("accepted submission must set automatic_retry_allowed=False")
        if self.canonical_finality_proven is not False:
            raise ValueError("submission acknowledgement cannot prove canonical finality")
        if not isinstance(self.provenance, ProductSubmissionProvenance):
            raise TypeError("provenance must be ProductSubmissionProvenance")
        if self.provenance.transport != transport:
            raise ValueError("submission/provenance transport mismatch")
        object.__setattr__(self, "submission_id", submission_id)
        object.__setattr__(self, "transport", transport)
        object.__setattr__(self, "conversation_id", conversation_id)
        object.__setattr__(self, "turn_exchange_id", turn_exchange_id)
        object.__setattr__(self, "turn_lifecycle_id", turn_lifecycle_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "transport": self.transport,
            "conversation_id": self.conversation_id,
            "turn_exchange_id": self.turn_exchange_id,
            "accepted_at_ms": self.accepted_at_ms,
            "turn_lifecycle_id": self.turn_lifecycle_id,
            "write_may_have_committed": self.write_may_have_committed,
            "automatic_retry_allowed": self.automatic_retry_allowed,
            "canonical_finality_proven": self.canonical_finality_proven,
            "provenance": self.provenance.to_dict(),
        }


def _install_runtime_surface() -> None:
    # Keep the frozen ProductWriteTransport protocol unchanged. Import-time
    # installation mirrors CWA's existing runtime gates while making the optional
    # submit/await extension available on ChatGPTProductRuntime itself.
    from .product_runtime import ChatGPTProductRuntime
    from .product_submission_runtime_gate import install_product_submission_runtime_surface

    install_product_submission_runtime_surface(ChatGPTProductRuntime)


_install_runtime_surface()
