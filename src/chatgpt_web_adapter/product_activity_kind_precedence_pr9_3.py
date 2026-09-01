from __future__ import annotations

from typing import Any

from . import product_observations as _observations
from .product_observations import ProductObservationKind

_PR93_ACTIVITY_KIND_PRECEDENCE_MARKER = "__pr93_activity_kind_precedence__"


def _operation_first_activity_kind(
    *,
    activity_kind: str | None,
    operation: str | None,
) -> ProductObservationKind:
    """Classify explicit product operations before coarse tool-name activity kinds.

    ChatGPT may execute calculator/weather/etc. through a tool named ``web.run``.
    PR8.12 therefore reports the coarse ``activity_kind='web'`` while also exposing
    the stronger normalized operation (for example ``calculator``). Search/tool
    semantics must follow that explicit operation rather than the transport-ish
    tool name.
    """

    if operation is not None:
        if operation in _observations._SEARCH_OPERATIONS:
            return ProductObservationKind.SEARCH
        return ProductObservationKind.TOOL

    if activity_kind in _observations._SEARCH_ACTIVITY_KINDS:
        return ProductObservationKind.SEARCH
    if activity_kind in _observations._TOOL_ACTIVITY_KINDS:
        return ProductObservationKind.TOOL
    return ProductObservationKind.ACTIVITY


def install_product_activity_kind_precedence() -> None:
    current: Any = _observations._activity_observation_kind
    if getattr(current, _PR93_ACTIVITY_KIND_PRECEDENCE_MARKER, False):
        return

    setattr(
        _operation_first_activity_kind,
        _PR93_ACTIVITY_KIND_PRECEDENCE_MARKER,
        True,
    )
    _observations._activity_observation_kind = _operation_first_activity_kind
