from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

_REASON_CODE_RE = re.compile(r"^[A-Z0-9_]+$")


class BrowserUILivenessState(str, Enum):
    """Best-effort visible product UI liveness state.

    These states are observations only. They do not grant write authority,
    retry authority, or canonical-finality authority.
    """

    READY_FOR_INPUT = "READY_FOR_INPUT"
    GENERATING = "GENERATING"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class BrowserUILivenessObservation:
    """Sanitized, non-authoritative observation of the existing browser UI."""

    transport: str
    state: BrowserUILivenessState
    reason_code: str
    observed_at_ms: int
    bridge_available: bool | None
    extension_connected: bool | None
    runtime_tab_present: bool | None
    composer_visible: bool | None = None
    generation_control_visible: bool | None = None
    composer_busy: bool | None = None
    source: str = field(default="BROWSER_UI", init=False)
    canonical_finality_proven: bool = field(default=False, init=False)
    grants_write_authority: bool = field(default=False, init=False)
    grants_retry_authority: bool = field(default=False, init=False)
    raw_dom_exported: bool = field(default=False, init=False)
    navigation_performed: bool = field(default=False, init=False)
    runtime_tab_created: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.transport, str) or not self.transport.strip():
            raise ValueError("transport is required")
        if not isinstance(self.state, BrowserUILivenessState):
            raise TypeError("state must be BrowserUILivenessState")
        if (
            not isinstance(self.reason_code, str)
            or _REASON_CODE_RE.fullmatch(self.reason_code) is None
        ):
            raise ValueError("reason_code must be a stable uppercase identifier")
        if (
            isinstance(self.observed_at_ms, bool)
            or not isinstance(self.observed_at_ms, int)
            or self.observed_at_ms <= 0
        ):
            raise ValueError("observed_at_ms must be a positive integer")
        for name in (
            "bridge_available",
            "extension_connected",
            "runtime_tab_present",
            "composer_visible",
            "generation_control_visible",
            "composer_busy",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be bool or None")
        if self.state is BrowserUILivenessState.READY_FOR_INPUT:
            if self.composer_visible is not True:
                raise ValueError("READY_FOR_INPUT requires a visible composer")
            if self.generation_control_visible is not False:
                raise ValueError(
                    "READY_FOR_INPUT requires generation_control_visible=False"
                )
            if self.composer_busy is not False:
                raise ValueError("READY_FOR_INPUT requires composer_busy=False")
        if (
            self.state is BrowserUILivenessState.GENERATING
            and self.generation_control_visible is not True
        ):
            raise ValueError("GENERATING requires positive generation-control evidence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "state": self.state.value,
            "reason_code": self.reason_code,
            "observed_at_ms": self.observed_at_ms,
            "bridge_available": self.bridge_available,
            "extension_connected": self.extension_connected,
            "runtime_tab_present": self.runtime_tab_present,
            "composer_visible": self.composer_visible,
            "generation_control_visible": self.generation_control_visible,
            "composer_busy": self.composer_busy,
            "source": self.source,
            "canonical_finality_proven": self.canonical_finality_proven,
            "grants_write_authority": self.grants_write_authority,
            "grants_retry_authority": self.grants_retry_authority,
            "raw_dom_exported": self.raw_dom_exported,
            "navigation_performed": self.navigation_performed,
            "runtime_tab_created": self.runtime_tab_created,
        }
