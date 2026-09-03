from __future__ import annotations

from typing import Any

from .product_submission_runtime import ProductSubmissionLifecycleUnavailableError


def install_product_submission_runtime_surface(runtime_class: type[Any]) -> None:
    """Compatibility validator for the now first-class runtime surface.

    PR12.2 keeps this historical import callable so older internal composition code
    does not become import-order-sensitive. It no longer mutates ``runtime_class``.
    """

    required = (
        "submit",
        "await_final",
        "submission_lifecycle_snapshot",
    )
    missing = [
        name for name in required if not callable(getattr(runtime_class, name, None))
    ]
    if missing:
        joined = ", ".join(missing)
        raise TypeError(
            f"runtime class is missing first-class submission methods: {joined}"
        )


__all__ = [
    "ProductSubmissionLifecycleUnavailableError",
    "install_product_submission_runtime_surface",
]
