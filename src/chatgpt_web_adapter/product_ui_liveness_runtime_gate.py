from __future__ import annotations

import time
from typing import Any, Callable
import uuid

from .exceptions import RequestError
from .product_transport import BROWSER_OWNED_PRODUCT_TRANSPORT
from .product_ui_liveness import (
    BrowserUILivenessObservation,
    BrowserUILivenessState,
)

_INSTALL_MARKER = "_pr115_browser_ui_liveness_installed"


def _now_ms() -> int:
    return max(1, int(time.time() * 1000))


def _unavailable(
    *,
    transport: str,
    reason_code: str,
    bridge_available: bool | None = None,
    extension_connected: bool | None = None,
    runtime_tab_present: bool | None = None,
) -> BrowserUILivenessObservation:
    return BrowserUILivenessObservation(
        transport=transport,
        state=BrowserUILivenessState.UNAVAILABLE,
        reason_code=reason_code,
        observed_at_ms=_now_ms(),
        bridge_available=bridge_available,
        extension_connected=extension_connected,
        runtime_tab_present=runtime_tab_present,
    )


def _unknown(
    *,
    transport: str,
    reason_code: str,
    bridge_available: bool | None,
    extension_connected: bool | None,
    runtime_tab_present: bool | None,
) -> BrowserUILivenessObservation:
    return BrowserUILivenessObservation(
        transport=transport,
        state=BrowserUILivenessState.UNKNOWN,
        reason_code=reason_code,
        observed_at_ms=_now_ms(),
        bridge_available=bridge_available,
        extension_connected=extension_connected,
        runtime_tab_present=runtime_tab_present,
    )


def _optional_bool(payload: dict[str, Any], key: str) -> bool | None:
    value = payload.get(key)
    return value if isinstance(value, bool) else None


def _observation_from_response(
    *,
    transport: str,
    request_id: str,
    response: dict[str, Any],
) -> BrowserUILivenessObservation:
    if response.get("request_id") != request_id:
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_RESPONSE_MISMATCH",
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=None,
        )
    if response.get("type") != "ui_liveness_result":
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_PROTOCOL_MISMATCH",
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=None,
        )
    if response.get("ok") is not True:
        error = str(response.get("error") or "")
        if error == "BROWSER_NATIVE_EXTENSION_NOT_CONNECTED":
            return _unavailable(
                transport=transport,
                reason_code="EXTENSION_DISCONNECTED",
                bridge_available=True,
                extension_connected=False,
                runtime_tab_present=None,
            )
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_REJECTED",
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=None,
        )

    if any(
        response.get(key) is True
        for key in (
            "rawDomExported",
            "navigationPerformed",
            "runtimeTabCreated",
            "writePerformed",
            "canonicalReadPerformed",
            "canonicalFinalityProven",
            "grantsWriteAuthority",
            "grantsRetryAuthority",
        )
    ):
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_CONTRACT_VIOLATION",
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=_optional_bool(response, "runtimeTabPresent"),
        )

    state_value = response.get("state")
    try:
        state = BrowserUILivenessState(state_value)
    except (TypeError, ValueError):
        state = BrowserUILivenessState.UNKNOWN
    reason_code = response.get("reasonCode")
    if not isinstance(reason_code, str) or not reason_code:
        reason_code = "OBSERVATION_REASON_MISSING"
    observed_at_ms = response.get("observedAtMs")
    if (
        isinstance(observed_at_ms, bool)
        or not isinstance(observed_at_ms, int)
        or observed_at_ms <= 0
    ):
        observed_at_ms = _now_ms()

    try:
        return BrowserUILivenessObservation(
            transport=transport,
            state=state,
            reason_code=reason_code,
            observed_at_ms=observed_at_ms,
            bridge_available=_optional_bool(response, "bridgeAvailable"),
            extension_connected=_optional_bool(response, "extensionConnected"),
            runtime_tab_present=_optional_bool(response, "runtimeTabPresent"),
            composer_visible=_optional_bool(response, "composerVisible"),
            generation_control_visible=_optional_bool(
                response,
                "generationControlVisible",
            ),
            composer_busy=_optional_bool(response, "composerBusy"),
        )
    except (TypeError, ValueError):
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_EVIDENCE_INVALID",
            bridge_available=True,
            extension_connected=True,
            runtime_tab_present=_optional_bool(response, "runtimeTabPresent"),
        )


def _observe_browser_provider(
    provider: Any,
    *,
    transport: str,
    timeout: float,
) -> BrowserUILivenessObservation:
    rpc = getattr(provider, "_rpc", None)
    if not callable(rpc):
        return _unavailable(
            transport=transport,
            reason_code="PROVIDER_OBSERVATION_UNSUPPORTED",
        )
    request_id = str(uuid.uuid4())
    try:
        response = rpc(
            {
                "type": "ui_liveness",
                "request_id": request_id,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
    except RequestError as error:
        if "RESPONSE_LOST_AFTER_DELEGATION" in str(error):
            return _unknown(
                transport=transport,
                reason_code="OBSERVATION_RESPONSE_LOST",
                bridge_available=True,
                extension_connected=None,
                runtime_tab_present=None,
            )
        return _unavailable(
            transport=transport,
            reason_code="BRIDGE_UNAVAILABLE",
            bridge_available=False,
            extension_connected=False,
            runtime_tab_present=None,
        )
    if not isinstance(response, dict):
        return _unknown(
            transport=transport,
            reason_code="OBSERVATION_RESPONSE_INVALID",
            bridge_available=True,
            extension_connected=None,
            runtime_tab_present=None,
        )
    return _observation_from_response(
        transport=transport,
        request_id=request_id,
        response=response,
    )


def _runtime_observe_ui_liveness(
    self: Any,
    *,
    timeout: float = 3.0,
) -> BrowserUILivenessObservation:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be a positive number")
    timeout_value = float(timeout)
    if timeout_value <= 0:
        raise ValueError("timeout must be positive")
    timeout_value = min(timeout_value, 10.0)

    transport = str(self.transport)
    if transport != BROWSER_OWNED_PRODUCT_TRANSPORT:
        return _unavailable(
            transport=transport,
            reason_code="TRANSPORT_OBSERVATION_UNSUPPORTED",
        )

    writer = self.write_transport
    provider = getattr(writer, "provider", None)
    if provider is None:
        return _unavailable(
            transport=transport,
            reason_code="PROVIDER_OBSERVATION_UNSUPPORTED",
        )
    return _observe_browser_provider(
        provider,
        transport=transport,
        timeout=timeout_value,
    )


def install_product_ui_liveness_runtime_surface(runtime_class: type[Any]) -> None:
    """Install the optional, non-authoritative PR11.5 runtime observation surface."""

    if getattr(runtime_class, _INSTALL_MARKER, False):
        return

    original_governance: Callable[..., dict[str, Any]] = runtime_class.governance

    def governance(self: Any) -> dict[str, Any]:
        payload = dict(original_governance(self))
        supported = self.transport == BROWSER_OWNED_PRODUCT_TRANSPORT
        payload.update(
            {
                "browser_ui_liveness_observation_supported": supported,
                "browser_ui_liveness_states": [
                    state.value for state in BrowserUILivenessState
                ],
                "browser_ui_liveness_source": "BROWSER_UI" if supported else None,
                "browser_ui_liveness_is_authority": False,
                "browser_ui_liveness_is_canonical_finality": False,
                "browser_ui_liveness_grants_write_authority": False,
                "browser_ui_liveness_grants_retry_authority": False,
                "browser_ui_liveness_raw_dom_exported": False,
                "browser_ui_liveness_navigation_performed": False,
                "browser_ui_liveness_runtime_tab_created": False,
                "browser_ui_liveness_acquires_browser_authority_lane": False,
            }
        )
        return payload

    runtime_class.observe_ui_liveness = _runtime_observe_ui_liveness
    runtime_class.governance = governance
    setattr(runtime_class, _INSTALL_MARKER, True)
