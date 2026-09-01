from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, TypeAlias

from .product_observations import (
    ProductObservationCollector,
    ProductObservationKind,
    ProductObservationPhase,
    StructuredProductObservation,
)

PRODUCT_CONNECTOR_OBSERVED = "product_connector_observed"
PRODUCT_CONNECTOR_STARTED = "product_connector_started"
PRODUCT_CONNECTOR_UPDATED = "product_connector_updated"
PRODUCT_CONNECTOR_COMPLETED = "product_connector_completed"
PRODUCT_CONNECTOR_FAILED = "product_connector_failed"

PRODUCT_REQUIRED_ACTION_OBSERVED = "product_required_action_observed"
PRODUCT_REQUIRED_ACTION_SURFACE_OBSERVED = "product_required_action_surface_observed"
PRODUCT_REQUIRED_ACTION_STARTED = "product_required_action_started"
PRODUCT_REQUIRED_ACTION_UPDATED = "product_required_action_updated"
PRODUCT_REQUIRED_ACTION_COMPLETED = "product_required_action_completed"
PRODUCT_REQUIRED_ACTION_FAILED = "product_required_action_failed"

_CONNECTOR_PHASE_BY_EVENT = {
    PRODUCT_CONNECTOR_OBSERVED: ProductObservationPhase.OBSERVED,
    PRODUCT_CONNECTOR_STARTED: ProductObservationPhase.STARTED,
    PRODUCT_CONNECTOR_UPDATED: ProductObservationPhase.UPDATED,
    PRODUCT_CONNECTOR_COMPLETED: ProductObservationPhase.COMPLETED,
    PRODUCT_CONNECTOR_FAILED: ProductObservationPhase.FAILED,
}
_REQUIRED_ACTION_PHASE_BY_EVENT = {
    PRODUCT_REQUIRED_ACTION_STARTED: ProductObservationPhase.STARTED,
    PRODUCT_REQUIRED_ACTION_UPDATED: ProductObservationPhase.UPDATED,
    PRODUCT_REQUIRED_ACTION_COMPLETED: ProductObservationPhase.COMPLETED,
    PRODUCT_REQUIRED_ACTION_FAILED: ProductObservationPhase.FAILED,
}
_TERMINAL_PHASES = frozenset(
    {ProductObservationPhase.COMPLETED, ProductObservationPhase.FAILED}
)


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _compatible_identity(
    previous: tuple[str | None, ...] | None,
    current: tuple[str | None, ...],
) -> bool:
    if previous is None:
        return True
    return all(
        old is None or new is None or old == new
        for old, new in zip(previous, current, strict=True)
    )


def _merge_identity(
    previous: tuple[str | None, ...] | None,
    current: tuple[str | None, ...],
) -> tuple[str | None, ...]:
    if previous is None:
        return current
    return tuple(old if old is not None else new for old, new in zip(previous, current, strict=True))


@dataclass(frozen=True)
class ProductConnectorObservation:
    """Safe evidence for one explicitly identified ChatGPT app/connector activity.

    This value reports product-visible evidence only. It carries no credential
    material and grants no connector, local, workspace, or Git authority to CWA
    or its caller.
    """

    observation_id: str
    connector_activity_id: str
    phase: ProductObservationPhase
    connector_id: str | None = None
    connector_name: str | None = None
    operation: str | None = None
    action_id: str | None = None
    label: str | None = None
    sequence: int | None = None
    observed_at_ms: int | None = None
    kind: ProductObservationKind = ProductObservationKind.CONNECTOR

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["phase"] = self.phase.value
        return payload


@dataclass(frozen=True)
class ProductRequiredActionLifecycleObservation:
    """Safe lifecycle evidence for an action requested by the ChatGPT product.

    Observing a required action is deliberately distinct from approving or
    executing it. The correlation fields only identify product evidence; they
    are not authorization capabilities.
    """

    observation_id: str
    action_id: str
    action_type: str
    phase: ProductObservationPhase
    connector_activity_id: str | None = None
    connector_id: str | None = None
    label: str | None = None
    sequence: int | None = None
    observed_at_ms: int | None = None
    kind: ProductObservationKind = ProductObservationKind.REQUIRED_ACTION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["phase"] = self.phase.value
        return payload


@dataclass(frozen=True)
class ProductRequiredActionSurfaceObservation:
    """Point evidence for a visible product authorization affordance.

    This type intentionally has no ``action_id``. A visible connect/dismiss surface
    proves that user action is required, but without an explicit stable product id
    it cannot be promoted into lifecycle correlation. It also grants no approval
    or execution authority.
    """

    observation_id: str
    action_type: str
    connector_name: str
    connect_control_present: bool
    dismiss_control_present: bool
    surface_origin: str = "product_surface"
    stable_action_id_present: bool = False
    kind: ProductObservationKind = ProductObservationKind.REQUIRED_ACTION
    phase: ProductObservationPhase = ProductObservationPhase.OBSERVED

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        payload["phase"] = self.phase.value
        return payload


PR100StructuredProductObservation: TypeAlias = (
    StructuredProductObservation
    | ProductConnectorObservation
    | ProductRequiredActionLifecycleObservation
    | ProductRequiredActionSurfaceObservation
)


class ProductConnectorLifecycleCollector:
    """Extend PR9.3 observations with fail-closed app/action correlation.

    PR10.0 accepts lifecycle semantics only when upstream supplies explicit stable
    identifiers. It never infers request/result pairing from labels, ordering,
    tool names, or payload contents. Point connector evidence may use a unique
    product message id, but remains `OBSERVED` rather than a fabricated lifecycle.
    A visible required-action surface may also become point evidence only when it
    proves both connect and dismiss controls while exposing no stable action id.
    Unknown event shapes continue through the PR9.3 collector unchanged.
    """

    def __init__(self) -> None:
        self._base = ProductObservationCollector()
        self._observations: list[PR100StructuredProductObservation] = []
        self._connector_identity: dict[str, tuple[str | None, ...]] = {}
        self._action_identity: dict[str, tuple[str | None, ...]] = {}
        self._connector_terminal: dict[str, ProductObservationPhase] = {}
        self._action_terminal: dict[str, ProductObservationPhase] = {}
        self.dropped_event_count = 0

    @property
    def observations(self) -> tuple[PR100StructuredProductObservation, ...]:
        return tuple(self._observations)

    def _drop(self) -> None:
        self.dropped_event_count += 1

    def _append(
        self,
        observation: PR100StructuredProductObservation,
    ) -> PR100StructuredProductObservation:
        self._observations.append(observation)
        return observation

    def consume(self, event: dict[str, Any]) -> PR100StructuredProductObservation | None:
        if not isinstance(event, dict):
            self._drop()
            return None

        event_type = _optional_text(event.get("type"))
        connector_phase = _CONNECTOR_PHASE_BY_EVENT.get(event_type)
        if connector_phase is not None:
            return self._consume_connector(event, connector_phase)

        if event_type == PRODUCT_REQUIRED_ACTION_SURFACE_OBSERVED:
            return self._consume_required_action_surface(event)

        required_action_phase = _REQUIRED_ACTION_PHASE_BY_EVENT.get(event_type)
        if required_action_phase is not None:
            return self._consume_required_action(event, required_action_phase)

        # PR9.3 already owns the compatibility point event. PR10.0 upgrades only
        # the explicitly correlated form carrying a stable action_id; legacy
        # events without an action_id continue through the original collector.
        if event_type == PRODUCT_REQUIRED_ACTION_OBSERVED and _optional_text(event.get("action_id")):
            return self._consume_required_action(event, ProductObservationPhase.OBSERVED)

        before = self._base.dropped_event_count
        observation = self._base.consume(event)
        self.dropped_event_count += self._base.dropped_event_count - before
        if observation is not None:
            return self._append(observation)
        return None

    def _consume_connector(
        self,
        event: dict[str, Any],
        phase: ProductObservationPhase,
    ) -> ProductConnectorObservation | None:
        observation_id = _optional_text(event.get("observation_id"))
        connector_activity_id = _optional_text(event.get("connector_activity_id"))
        if observation_id is None or connector_activity_id is None:
            self._drop()
            return None

        connector_id = _optional_text(event.get("connector_id"))
        connector_name = _optional_text(event.get("connector_name"))
        operation = _optional_text(event.get("operation"))
        action_id = _optional_text(event.get("action_id"))
        # Display names can localize or change without changing product identity.
        # Bind lifecycle correlation only to stable connector id + operation.
        identity = (connector_id, operation)
        prior_identity = self._connector_identity.get(connector_activity_id)
        if not _compatible_identity(prior_identity, identity):
            self._drop()
            return None

        prior_terminal = self._connector_terminal.get(connector_activity_id)
        if prior_terminal is not None and phase != prior_terminal:
            self._drop()
            return None

        self._connector_identity[connector_activity_id] = _merge_identity(
            prior_identity,
            identity,
        )
        if phase in _TERMINAL_PHASES:
            self._connector_terminal[connector_activity_id] = phase

        return self._append(
            ProductConnectorObservation(
                observation_id=observation_id,
                connector_activity_id=connector_activity_id,
                phase=phase,
                connector_id=connector_id,
                connector_name=connector_name,
                operation=operation,
                action_id=action_id,
                label=_optional_text(event.get("label")),
                sequence=_non_negative_int(event.get("sequence")),
                observed_at_ms=_non_negative_int(event.get("observed_at_ms")),
            )
        )

    def _consume_required_action_surface(
        self,
        event: dict[str, Any],
    ) -> ProductRequiredActionSurfaceObservation | None:
        observation_id = _optional_text(event.get("observation_id"))
        action_type = _optional_text(event.get("action_type"))
        connector_name = _optional_text(event.get("connector_name"))
        connect_present = event.get("connect_control_present") is True
        dismiss_present = event.get("dismiss_control_present") is True
        stable_action_id_present = event.get("stable_action_id_present") is True
        action_id = _optional_text(event.get("action_id"))

        if (
            observation_id is None
            or action_type is None
            or connector_name is None
            or not connect_present
            or not dismiss_present
            or stable_action_id_present
            or action_id is not None
        ):
            self._drop()
            return None

        return self._append(
            ProductRequiredActionSurfaceObservation(
                observation_id=observation_id,
                action_type=action_type,
                connector_name=connector_name,
                connect_control_present=True,
                dismiss_control_present=True,
            )
        )

    def _consume_required_action(
        self,
        event: dict[str, Any],
        phase: ProductObservationPhase,
    ) -> ProductRequiredActionLifecycleObservation | None:
        observation_id = _optional_text(event.get("observation_id"))
        action_id = _optional_text(event.get("action_id"))
        action_type = _optional_text(event.get("action_type"))
        if observation_id is None or action_id is None or action_type is None:
            self._drop()
            return None

        connector_activity_id = _optional_text(event.get("connector_activity_id"))
        connector_id = _optional_text(event.get("connector_id"))
        identity = (action_type, connector_activity_id, connector_id)
        prior_identity = self._action_identity.get(action_id)
        if not _compatible_identity(prior_identity, identity):
            self._drop()
            return None

        prior_terminal = self._action_terminal.get(action_id)
        if prior_terminal is not None and phase != prior_terminal:
            self._drop()
            return None

        self._action_identity[action_id] = _merge_identity(prior_identity, identity)
        if phase in _TERMINAL_PHASES:
            self._action_terminal[action_id] = phase

        return self._append(
            ProductRequiredActionLifecycleObservation(
                observation_id=observation_id,
                action_id=action_id,
                action_type=action_type,
                phase=phase,
                connector_activity_id=connector_activity_id,
                connector_id=connector_id,
                label=_optional_text(event.get("label")),
                sequence=_non_negative_int(event.get("sequence")),
                observed_at_ms=_non_negative_int(event.get("observed_at_ms")),
            )
        )
