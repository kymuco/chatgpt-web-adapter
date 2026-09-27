from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .browser_native_provider import (
    BrowserNativeBridgeStatus,
    BrowserNativeTurnProvider,
)
from .exceptions import RequestError

GEMINI_NOTEBOOK_WEB_PRODUCT_ID = "gemini-notebook-web"
GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID = "add_url_source"
GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION = "gemini_notebook_add_url_source"
GEMINI_NOTEBOOK_WEB_SUPPORT_TIER = "EXPERIMENTAL"
GEMINI_NOTEBOOK_WEB_FINALITY = "PAGE_DOM_DURABLE_SOURCE_ADMISSION"

_NOTEBOOK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,200}$")
_NOTEBOOK_HOSTS = {"notebook.google.com", "notebooklm.google.com"}


@dataclass(frozen=True)
class GeminiNotebookUrlSourceResult:
    notebook_url: str
    source_url: str
    source_title: str
    observed_row_ref: str
    source_row_count_before: int
    source_row_count_after: int
    tab_id: int | None
    elapsed_ms: int | None
    finality_evidence: str
    canonical_completion_proven: bool
    automatic_retry: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
            "capability_id": GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID,
            "notebook_url": self.notebook_url,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "observed_row_ref": self.observed_row_ref,
            "source_row_count_before": self.source_row_count_before,
            "source_row_count_after": self.source_row_count_after,
            "tab_id": self.tab_id,
            "elapsed_ms": self.elapsed_ms,
            "finality_evidence": self.finality_evidence,
            "canonical_completion_proven": self.canonical_completion_proven,
            "automatic_retry": self.automatic_retry,
        }


class GeminiNotebookOutcomeAmbiguousError(RequestError):
    """Durable source mutation whose outcome requires reconciliation."""

    reconciliation_required = True
    automatic_retry_allowed = False


class GeminiNotebookWebCapability:
    """Experimental persistent-workspace source admission over Gemini Notebook Web."""

    product_id = GEMINI_NOTEBOOK_WEB_PRODUCT_ID
    capability_id = GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID
    support_tier = GEMINI_NOTEBOOK_WEB_SUPPORT_TIER

    def __init__(
        self,
        *,
        bridge: BrowserNativeTurnProvider | None = None,
        connect_timeout: float = 3.0,
        operation_timeout: float = 60.0,
    ) -> None:
        if operation_timeout <= 0:
            raise ValueError("operation_timeout must be positive")
        self.bridge = bridge or BrowserNativeTurnProvider(
            connect_timeout=connect_timeout,
            turn_timeout=operation_timeout,
        )
        self.operation_timeout = float(operation_timeout)

    @staticmethod
    def _notebook_url(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("notebook is required")
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _NOTEBOOK_HOSTS
            or parsed.username
            or parsed.password
        ):
            raise ValueError("notebook must be an exact Gemini Notebook https URL")
        parts = [part for part in parsed.path.split("/") if part]
        if (
            len(parts) != 2
            or parts[0] != "notebook"
            or _NOTEBOOK_ID_RE.fullmatch(parts[1]) is None
        ):
            raise ValueError("notebook must identify exactly one Gemini Notebook")
        return urlunsplit(("https", parsed.netloc, f"/notebook/{parts[1]}", "", ""))

    @staticmethod
    def _source_url(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("source_url is required")
        normalized = value.strip()
        if len(normalized) > 2048:
            raise ValueError("source_url is too large")
        parsed = urlsplit(normalized)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("source_url must be an absolute http(s) URL")
        return urlunsplit(parsed)

    def health(self) -> BrowserNativeBridgeStatus:
        return self.bridge.status()

    def add_url_source(
        self,
        *,
        notebook: str,
        source_url: str,
        timeout: float | None = None,
    ) -> GeminiNotebookUrlSourceResult:
        notebook_url = self._notebook_url(notebook)
        normalized_source_url = self._source_url(source_url)
        total_timeout = self.operation_timeout if timeout is None else float(timeout)
        if total_timeout < 5.0:
            raise ValueError("timeout must be at least 5 seconds")

        payload = {
            "type": GEMINI_NOTEBOOK_ADD_URL_SOURCE_OPERATION,
            "request_id": uuid.uuid4().hex,
            "productId": GEMINI_NOTEBOOK_WEB_PRODUCT_ID,
            "capabilityId": GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID,
            "notebookUrl": notebook_url,
            "sourceUrl": normalized_source_url,
            "timeoutMs": 1,
        }

        try:
            response = self.bridge._rpc(  # noqa: SLF001
                payload,
                timeout=total_timeout,
                delegated_timeout_ms_key="timeoutMs",
                delegated_response_margin=2.0,
            )
        except RequestError as error:
            if str(error).startswith(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION:"
            ):
                raise GeminiNotebookOutcomeAmbiguousError(
                    f"GEMINI_NOTEBOOK_ADD_URL_SOURCE_FAILED: {error}",
                    request_stage="gemini_notebook_add_url_source",
                ) from error
            raise

        if response.get("ok") is not True:
            error = str(response.get("error") or "unknown error")
            if error.startswith(
                "GEMINI_NOTEBOOK_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ) or error in {
                "BROWSER_NATIVE_EXTENSION_TIMEOUT",
                "BROWSER_NATIVE_HOST_SHUTDOWN",
            }:
                raise GeminiNotebookOutcomeAmbiguousError(
                    f"GEMINI_NOTEBOOK_ADD_URL_SOURCE_FAILED: {error}",
                    request_stage="gemini_notebook_add_url_source",
                )
            raise RequestError(
                f"GEMINI_NOTEBOOK_ADD_URL_SOURCE_FAILED: {error}",
                request_stage="gemini_notebook_add_url_source",
            )

        if response.get("productId") != GEMINI_NOTEBOOK_WEB_PRODUCT_ID:
            raise RequestError(
                "GEMINI_NOTEBOOK_PRODUCT_ID_MISMATCH",
                request_stage="gemini_notebook_add_url_source",
            )
        if (
            response.get("capabilityId")
            != GEMINI_NOTEBOOK_ADD_URL_SOURCE_CAPABILITY_ID
        ):
            raise RequestError(
                "GEMINI_NOTEBOOK_CAPABILITY_ID_MISMATCH",
                request_stage="gemini_notebook_add_url_source",
            )
        if response.get("notebookUrl") != notebook_url:
            raise RequestError(
                "GEMINI_NOTEBOOK_FINAL_NOTEBOOK_IDENTITY_MISMATCH",
                request_stage="gemini_notebook_add_url_source",
            )
        if response.get("sourceUrl") != normalized_source_url:
            raise RequestError(
                "GEMINI_NOTEBOOK_SOURCE_URL_IDENTITY_MISMATCH",
                request_stage="gemini_notebook_add_url_source",
            )
        if response.get("finalityEvidence") != GEMINI_NOTEBOOK_WEB_FINALITY:
            raise RequestError(
                "GEMINI_NOTEBOOK_FINALITY_UNPROVEN",
                request_stage="gemini_notebook_add_url_source",
            )
        if response.get("canonicalCompletionProven") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_CANONICAL_COMPLETION_MUST_REMAIN_UNPROVEN",
                request_stage="gemini_notebook_add_url_source",
            )
        if response.get("automaticRetry") is not False:
            raise RequestError(
                "GEMINI_NOTEBOOK_AUTOMATIC_RETRY_FORBIDDEN",
                request_stage="gemini_notebook_add_url_source",
            )

        source_title = response.get("sourceTitle")
        observed_row_ref = response.get("observedRowRef")
        before_count = response.get("sourceRowCountBefore")
        after_count = response.get("sourceRowCountAfter")
        if not isinstance(source_title, str) or not source_title.strip():
            raise RequestError(
                "GEMINI_NOTEBOOK_SOURCE_TITLE_MISSING",
                request_stage="gemini_notebook_add_url_source",
            )
        if not isinstance(observed_row_ref, str) or not observed_row_ref.strip():
            raise RequestError(
                "GEMINI_NOTEBOOK_SOURCE_ROW_REF_MISSING",
                request_stage="gemini_notebook_add_url_source",
            )
        if (
            not isinstance(before_count, int)
            or isinstance(before_count, bool)
            or not isinstance(after_count, int)
            or isinstance(after_count, bool)
            or after_count != before_count + 1
        ):
            raise RequestError(
                "GEMINI_NOTEBOOK_SOURCE_ROW_DELTA_INVALID",
                request_stage="gemini_notebook_add_url_source",
            )

        return GeminiNotebookUrlSourceResult(
            notebook_url=notebook_url,
            source_url=normalized_source_url,
            source_title=source_title.strip(),
            observed_row_ref=observed_row_ref.strip(),
            source_row_count_before=before_count,
            source_row_count_after=after_count,
            tab_id=response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None,
            elapsed_ms=response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None,
            finality_evidence=GEMINI_NOTEBOOK_WEB_FINALITY,
            canonical_completion_proven=False,
            automatic_retry=False,
        )
