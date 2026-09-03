from __future__ import annotations

from typing import Any


def install_product_ui_liveness_runtime_surface(runtime_class: type[Any]) -> None:
    """Compatibility validator for the now first-class liveness surface.

    PR12.2 preserves the historical installer name for import compatibility only.
    The function does not assign methods or replace ``governance()``.
    """

    required = (
        "observe_ui_liveness",
        "governance",
    )
    missing = [
        name for name in required if not callable(getattr(runtime_class, name, None))
    ]
    if missing:
        joined = ", ".join(missing)
        raise TypeError(
            f"runtime class is missing first-class liveness methods: {joined}"
        )


__all__ = ["install_product_ui_liveness_runtime_surface"]
