from __future__ import annotations

from typing import Any

from .product_connector_lifecycle_pr10_0 import (
    PR100StructuredProductObservation,
    ProductConnectorLifecycleCollector,
)

PRODUCT_CONNECTOR_ROUTER_SHAPE_OBSERVED = "product_connector_router_shape_observed"


class ProductConnectorRouterCharacterizationCollector(ProductConnectorLifecycleCollector):
    """PR10.0 collector that recognizes a raw-event-only router diagnostic.

    ``product_connector_router_shape_observed`` exists only to characterize the
    bounded product envelope used by ``api_tool.call_tool``. It is intentionally
    not promoted into ``ProductRuntimeExecution.observations``: public structured
    observations remain connector/activity/source/citation evidence, while the
    live gate may inspect this diagnostic through the caller-owned ``on_event``
    stream.

    Recognizing the event here is important for safety accounting. A known,
    deliberately non-public diagnostic is not a dropped observation event and
    therefore must not make canonical-finality checks look unhealthy.
    """

    def consume(self, event: dict[str, Any]) -> PR100StructuredProductObservation | None:
        if isinstance(event, dict) and event.get("type") == PRODUCT_CONNECTOR_ROUTER_SHAPE_OBSERVED:
            return None
        return super().consume(event)
