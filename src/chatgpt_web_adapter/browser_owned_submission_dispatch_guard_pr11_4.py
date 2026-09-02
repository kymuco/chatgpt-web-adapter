from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .browser_owned_product_transport import BrowserOwnedProductTransport

_PR114_DISPATCH_GUARD_MARKER = "__pr114_submission_dispatch_guard__"


def _guard_method(method: Callable[..., Any]) -> Callable[..., Any]:
    if getattr(method, _PR114_DISPATCH_GUARD_MARKER, False):
        return method

    @wraps(method)
    def guarded(self: BrowserOwnedProductTransport, *args: Any, **kwargs: Any) -> Any:
        lifecycle = getattr(self, "_submission_lifecycle", None)
        lock = getattr(lifecycle, "_lock", None)
        if lock is None:
            raise RuntimeError("PR11_4_SUBMISSION_DISPATCH_LOCK_MISSING")
        # Hold the same re-entrant lifecycle lock from preflight through the
        # protected write/finality operation. A competing operation therefore
        # cannot observe an empty pending slot and delegate a second write before
        # the first submit has atomically published its acknowledgement state.
        with lock:
            return method(self, *args, **kwargs)

    setattr(guarded, _PR114_DISPATCH_GUARD_MARKER, True)
    return guarded


def install_browser_owned_submission_dispatch_guard() -> None:
    """Serialize every browser-owned write/lifecycle operation at its outer boundary."""

    for name in (
        "send_text",
        "send_text_observed",
        "submit_text",
        "await_final",
        "end_temporary_lifecycle",
    ):
        current = getattr(BrowserOwnedProductTransport, name)
        setattr(BrowserOwnedProductTransport, name, _guard_method(current))
