from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path, PureWindowsPath
import re
from typing import Any, TypeAlias

from .product_connector_lifecycle_pr10_0 import PR100StructuredProductObservation
from .product_connector_router_characterization_pr10_0 import (
    ProductConnectorRouterCharacterizationCollector,
)
from .product_observations import ProductObservationPhase

PRODUCT_ARTIFACT_OBSERVED = "product_artifact_observed"

_ALLOWED_ORIGINS = frozenset({"product_message_metadata", "product_content_part"})
_SENSITIVE_LOCATOR_KEYS = frozenset(
    {
        "url",
        "href",
        "download_url",
        "signed_url",
        "download_uri",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "secret",
    }
)
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,192}$")
_MEDIA_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


class ProductArtifactObservationKind(str, Enum):
    """Provisional PR10.1 kind pending authenticated artifact-shape proof."""

    ARTIFACT = "ARTIFACT"


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _safe_artifact_id(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None or not _OPAQUE_ID_RE.fullmatch(text):
        return None
    lower = text.lower()
    if any(marker in lower for marker in ("token", "secret", "credential", "authorization", "cookie")):
        return None
    return text


def _safe_filename(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if len(text) > 255 or text in {".", ".."} or any(ord(char) < 32 for char in text):
        return None
    if "/" in text or "\\" in text:
        return None
    if Path(text).name != text or PureWindowsPath(text).name != text:
        return None
    return text


def _safe_media_type(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    normalized = text.lower()
    if len(normalized) > 128 or not _MEDIA_TYPE_RE.fullmatch(normalized):
        return None
    return normalized


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


@dataclass(frozen=True)
class ProductArtifactObservation:
    """Safe point evidence for one explicitly identified product-generated artifact.

    The observation intentionally contains no URL, signed locator, token, bytes, or
    local destination. Seeing an artifact is distinct from authorizing a download or
    filesystem write. PR10.1 keeps the kind provisional until authenticated product
    evidence proves the real generated-artifact shape.
    """

    observation_id: str
    artifact_id: str
    filename: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    download_available: bool = False
    source_origin: str = "product_message_metadata"
    sequence: int | None = None
    observed_at_ms: int | None = None
    kind: ProductArtifactObservationKind = ProductArtifactObservationKind.ARTIFACT
    phase: ProductObservationPhase = ProductObservationPhase.OBSERVED

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["phase"] = self.phase.value
        return payload


PR101StructuredProductObservation: TypeAlias = (
    PR100StructuredProductObservation | ProductArtifactObservation
)


class ProductArtifactObservationCollector(ProductConnectorRouterCharacterizationCollector):
    """Extend PR10.0 observations with fail-closed generated-artifact point evidence."""

    @property
    def observations(self) -> tuple[PR101StructuredProductObservation, ...]:
        return tuple(self._observations)

    def consume(self, event: dict[str, Any]) -> PR101StructuredProductObservation | None:
        if not isinstance(event, dict):
            return super().consume(event)
        if event.get("type") != PRODUCT_ARTIFACT_OBSERVED:
            return super().consume(event)
        return self._consume_artifact(event)

    def _consume_artifact(self, event: dict[str, Any]) -> ProductArtifactObservation | None:
        # Locators and credentials are not merely hidden from serialization: their
        # presence on the event is itself a contract violation and fails closed.
        if any(key in event and event.get(key) is not None for key in _SENSITIVE_LOCATOR_KEYS):
            self._drop()
            return None

        observation_id = _optional_text(event.get("observation_id"))
        artifact_id = _safe_artifact_id(event.get("artifact_id"))
        if observation_id is None or artifact_id is None:
            self._drop()
            return None

        raw_filename = event.get("filename")
        filename = _safe_filename(raw_filename)
        if raw_filename is not None and filename is None:
            self._drop()
            return None

        raw_media_type = event.get("media_type")
        media_type = _safe_media_type(raw_media_type)
        if raw_media_type is not None and media_type is None:
            self._drop()
            return None

        raw_size = event.get("size_bytes")
        size_bytes = _non_negative_int(raw_size)
        if raw_size is not None and size_bytes is None:
            self._drop()
            return None

        source_origin = _optional_text(event.get("source_origin"))
        if source_origin not in _ALLOWED_ORIGINS:
            self._drop()
            return None

        raw_download_available = event.get("download_available")
        if not isinstance(raw_download_available, bool):
            self._drop()
            return None

        observation = ProductArtifactObservation(
            observation_id=observation_id,
            artifact_id=artifact_id,
            filename=filename,
            media_type=media_type,
            size_bytes=size_bytes,
            download_available=raw_download_available,
            source_origin=source_origin,
            sequence=_non_negative_int(event.get("sequence")),
            observed_at_ms=_non_negative_int(event.get("observed_at_ms")),
        )
        self._observations.append(observation)
        return observation
