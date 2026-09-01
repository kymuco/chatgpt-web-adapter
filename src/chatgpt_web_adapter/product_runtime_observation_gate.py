from __future__ import annotations

from dataclasses import replace
from functools import wraps
from typing import Any, Callable

from .product_activity_kind_precedence_pr9_3 import (
    install_product_activity_kind_precedence,
)
from .product_connector_router_characterization_pr10_0 import (
    ProductConnectorRouterCharacterizationCollector,
)
from .product_rich_input_capability_gate_pr9_4 import (
    install_browser_owned_rich_input_capability_gate,
)
from .product_transport import ProductRuntimeExecution
from .product_web_search_capability_gate_pr9_3 import (
    install_browser_owned_web_search_capability_gate,
)

_PR93_PRODUCT_OBSERVATION_GATE_MARKER = "__pr93_product_observation_gate__"

# PR9.3 operation classification prefers explicit normalized product operations
# over coarse activity kinds derived from tool names. This matters for product
# operations such as calculator/weather that may travel through ``web.run``.
install_product_activity_kind_precedence()

# PR9.3 live characterization proved the revision-safe browser-owned search
# observation path. Install the provider-aware capability declaration alongside
# the observation runtime gate so legacy providers without that channel remain
# UNKNOWN instead of inheriting the production claim.
install_browser_owned_web_search_capability_gate()

# PR9.4 freezes the already-live-proven PR9.2 rich-input capability claims for the
# unchanged ProductModelProfileProvider write/RPC path. Custom/legacy providers
# remain conservative rather than inheriting image/file/multimodal authority from
# the browser-owned transport identity alone.
install_browser_owned_rich_input_capability_gate()


def gate_product_runtime_send_text_observed(
    send_text_observed: Callable[..., ProductRuntimeExecution],
) -> Callable[..., ProductRuntimeExecution]:
    """Attach runtime-owned typed observations to observed product executions.

    The wrapped runtime remains the sole owner of product write/provenance/finality.
    This gate only listens to the already-standardized ``on_event`` stream and
    replaces the returned execution's observation tuple with collector-owned,
    privacy-filtered values. A transport cannot acquire typed-observation authority
    by pre-populating ``ProductRuntimeExecution.observations`` itself.

    PR10.0 extends the collector with explicit connector/required-action lifecycle
    events. Those observations remain evidence only: they cannot authorize a
    connector, approve an action, mutate a workspace, retry a write, or change
    canonical finality. The bounded api_tool router-shape diagnostic stays only on
    the caller event stream and is recognized without becoming public observation
    authority or being counted as an unexplained dropped event.
    """

    if getattr(send_text_observed, _PR93_PRODUCT_OBSERVATION_GATE_MARKER, False):
        return send_text_observed

    @wraps(send_text_observed)
    def gated(
        self: Any,
        text: str,
        *args: Any,
        **kwargs: Any,
    ) -> ProductRuntimeExecution:
        # PR9.3 canonical provenance uses the same already-performed browser-owned
        # canonical readback payload. The installer only adds observation taps
        # around that path; it does not add reads, change finality, or acquire
        # write/retry authority.
        from .canonical_product_observation_gate_pr9_3 import (
            install_canonical_product_observation_gate,
        )

        install_canonical_product_observation_gate()

        caller_on_event = kwargs.get("on_event")
        collector = ProductConnectorRouterCharacterizationCollector()

        def collect_and_forward(event: dict[str, Any]) -> None:
            try:
                collector.consume(event)
            except Exception:
                # Structured observation is explicitly non-authoritative. A
                # collector defect cannot invalidate or replay a delegated write.
                collector.dropped_event_count += 1
            if caller_on_event is not None:
                caller_on_event(event)

        kwargs["on_event"] = collect_and_forward
        execution = send_text_observed(self, text, *args, **kwargs)
        if not isinstance(execution, ProductRuntimeExecution):
            raise TypeError(
                "ChatGPTProductRuntime.send_text_observed() must return ProductRuntimeExecution"
            )

        return replace(
            execution,
            observations=collector.observations,
            dropped_observation_event_count=collector.dropped_event_count,
        )

    setattr(gated, _PR93_PRODUCT_OBSERVATION_GATE_MARKER, True)
    return gated
