from __future__ import annotations

from functools import wraps
import threading
from typing import Any, Callable

from .browser_owned_product_transport import BrowserOwnedProductTransport
from .browser_owned_submission_lifecycle import BrowserOwnedSubmissionLifecycle

_PR114_DISPATCH_GUARD_MARKER = "__pr114_submission_dispatch_guard__"
_PR114_LIFECYCLE_INIT_MARKER = "__pr114_submission_lifecycle_init__"


def _install_structural_lifecycle_init() -> None:
    current = BrowserOwnedSubmissionLifecycle.__init__
    if getattr(current, _PR114_LIFECYCLE_INIT_MARKER, False):
        return

    def structural_init(self: BrowserOwnedSubmissionLifecycle, runtime: Any) -> None:
        # Preserve the long-standing BrowserOwnedProductTransport test/injection
        # seam: construction is structural, not coupled to the concrete lower
        # runtime class. Split-lifecycle operations themselves still fail closed
        # if their required lower-runtime methods are absent.
        self.runtime = runtime
        self._lock = threading.RLock()
        self._pending = None

    setattr(structural_init, _PR114_LIFECYCLE_INIT_MARKER, True)
    BrowserOwnedSubmissionLifecycle.__init__ = structural_init


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

    _install_structural_lifecycle_init()
    for name in (
        "send_text",
        "send_text_observed",
        "submit_text",
        "await_final",
        "end_temporary_lifecycle",
    ):
        current = getattr(BrowserOwnedProductTransport, name)
        setattr(BrowserOwnedProductTransport, name, _guard_method(current))
