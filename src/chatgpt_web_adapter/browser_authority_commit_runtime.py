from __future__ import annotations

from typing import Any

from .browser_owned_write_runtime import (
    WRITE_OUTCOME_UNKNOWN,
    BrowserOwnedProductWriteRuntime,
    BrowserOwnedWriteRuntimeError,
)

WRITE_NOT_SUBMITTED = "BROWSER_OWNED_WRITE_NOT_SUBMITTED"


class CommitBoundBrowserOwnedProductWriteRuntime(BrowserOwnedProductWriteRuntime):
    """Refine write ambiguity only when the provider proves no delegation occurred."""

    def send_text(self, *args: Any, **kwargs: Any):
        try:
            return super().send_text(*args, **kwargs)
        except BrowserOwnedWriteRuntimeError as error:
            boundary_check = getattr(
                self.provider,
                "_browser_authority_write_boundary_entered",
                None,
            )
            lease = error.browser_authority_lease
            if (
                error.failure_kind == WRITE_OUTCOME_UNKNOWN
                and error.write_may_have_been_submitted
                and error.reconciliation_required
                and lease is not None
                and callable(boundary_check)
                and boundary_check(lease.lease_id) is False
            ):
                cause = error.cause if error.cause is not None else error
                raise BrowserOwnedWriteRuntimeError(
                    str(cause),
                    failure_kind=WRITE_NOT_SUBMITTED,
                    automatic_retry_allowed=False,
                    manual_retry_safe_after_repair=True,
                    write_may_have_been_submitted=False,
                    reconciliation_required=False,
                    cause=cause,
                    request_stage="browser_owned_write_prewrite",
                    conversation_id=error.conversation_id,
                    reason_code=error.reason_code,
                    status_code=error.status_code,
                    content_type=error.content_type,
                    browser_authority_lease=None,
                    turn_lifecycle=None,
                ) from error
            raise


__all__ = [
    "CommitBoundBrowserOwnedProductWriteRuntime",
    "WRITE_NOT_SUBMITTED",
]
