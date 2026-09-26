from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from .browser_native_provider import (
    BrowserNativeBridgeStatus,
    BrowserNativeTurnProvider,
)
from .exceptions import RequestError

GOOGLE_TRANSLATE_WEB_PRODUCT_ID = "google-translate-web"
GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID = "translate_text"
GOOGLE_TRANSLATE_WEB_SUPPORT_TIER = "EXPERIMENTAL"
GOOGLE_TRANSLATE_WEB_FINALITY = "PAGE_DOM_STABLE_TRANSLATION"

_LANGUAGE_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,19}$")


@dataclass(frozen=True)
class GoogleTranslateTextResult:
    translated_text: str
    source_language: str
    target_language: str
    final_url: str
    tab_id: int | None
    elapsed_ms: int | None
    finality_evidence: str
    canonical_completion_proven: bool
    automatic_retry: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_id": GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
            "capability_id": GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
            "translated_text": self.translated_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "final_url": self.final_url,
            "tab_id": self.tab_id,
            "elapsed_ms": self.elapsed_ms,
            "finality_evidence": self.finality_evidence,
            "canonical_completion_proven": self.canonical_completion_proven,
            "automatic_retry": self.automatic_retry,
        }


class GoogleTranslateOutcomeAmbiguousError(RequestError):
    """Hosted translation outcome that must not authorize automatic replay."""

    reconciliation_required = True
    automatic_retry_allowed = False


class GoogleTranslateWebCapability:
    """Experimental non-chat text-translation capability over the browser bridge."""

    product_id = GOOGLE_TRANSLATE_WEB_PRODUCT_ID
    capability_id = GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID
    support_tier = GOOGLE_TRANSLATE_WEB_SUPPORT_TIER

    def __init__(
        self,
        *,
        bridge: BrowserNativeTurnProvider | None = None,
        connect_timeout: float = 3.0,
        operation_timeout: float = 30.0,
    ) -> None:
        if operation_timeout <= 0:
            raise ValueError("operation_timeout must be positive")
        self.bridge = bridge or BrowserNativeTurnProvider(
            connect_timeout=connect_timeout,
            turn_timeout=operation_timeout,
        )
        self.operation_timeout = float(operation_timeout)

    @staticmethod
    def _source_language(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("source_language is required")
        normalized = value.strip()
        if normalized.lower() == "auto":
            return "auto"
        if _LANGUAGE_CODE_RE.fullmatch(normalized) is None:
            raise ValueError("source_language must be a bounded language code")
        return normalized

    @staticmethod
    def _target_language(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("target_language is required")
        normalized = value.strip()
        if normalized.lower() == "auto":
            raise ValueError("target_language cannot be auto")
        if _LANGUAGE_CODE_RE.fullmatch(normalized) is None:
            raise ValueError("target_language must be a bounded language code")
        return normalized

    def health(self) -> BrowserNativeBridgeStatus:
        return self.bridge.status()

    def translate_text(
        self,
        text: str,
        *,
        source_language: str = "auto",
        target_language: str,
        timeout: float | None = None,
    ) -> GoogleTranslateTextResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 5000:
            raise ValueError("text is too large for Google Translate Web spike")

        source = self._source_language(source_language)
        target = self._target_language(target_language)
        total_timeout = self.operation_timeout if timeout is None else float(timeout)
        if total_timeout < 3.0:
            raise ValueError("timeout must be at least 3 seconds")
        payload = {
            "type": GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
            "request_id": uuid.uuid4().hex,
            "productId": GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
            "text": text,
            "sourceLanguage": source,
            "targetLanguage": target,
            "timeoutMs": 1,
        }

        try:
            # PR16.2 intentionally reuses the proven low-level local bridge without
            # pretending this operation is a ProductWriteTransport chat turn.
            response = self.bridge._rpc(  # noqa: SLF001
                payload,
                timeout=total_timeout,
                delegated_timeout_ms_key="timeoutMs",
                delegated_response_margin=1.0,
            )
        except RequestError as error:
            if str(error).startswith(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION:"
            ):
                raise GoogleTranslateOutcomeAmbiguousError(
                    f"GOOGLE_TRANSLATE_TEXT_FAILED: {error}",
                    request_stage="google_translate_text",
                ) from error
            raise

        if response.get("ok") is not True:
            error = str(response.get("error") or "unknown error")
            if error.startswith(
                "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ) or error in {
                "BROWSER_NATIVE_EXTENSION_TIMEOUT",
                "BROWSER_NATIVE_HOST_SHUTDOWN",
            }:
                raise GoogleTranslateOutcomeAmbiguousError(
                    f"GOOGLE_TRANSLATE_TEXT_FAILED: {error}",
                    request_stage="google_translate_text",
                )
            raise RequestError(
                f"GOOGLE_TRANSLATE_TEXT_FAILED: {error}",
                request_stage="google_translate_text",
            )

        if response.get("productId") != GOOGLE_TRANSLATE_WEB_PRODUCT_ID:
            raise RequestError(
                "GOOGLE_TRANSLATE_PRODUCT_ID_MISMATCH",
                request_stage="google_translate_text",
            )
        if response.get("capabilityId") != GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID:
            raise RequestError(
                "GOOGLE_TRANSLATE_CAPABILITY_ID_MISMATCH",
                request_stage="google_translate_text",
            )

        translated_text = response.get("translatedText")
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise RequestError(
                "GOOGLE_TRANSLATE_RESULT_TEXT_MISSING",
                request_stage="google_translate_text",
            )

        final_url = response.get("finalUrl")
        if not isinstance(final_url, str) or not (
            final_url == "https://translate.google.com"
            or final_url.startswith("https://translate.google.com/")
        ):
            raise RequestError(
                "GOOGLE_TRANSLATE_FINAL_ROUTE_INVALID",
                request_stage="google_translate_text",
            )

        if response.get("sourceLanguage") != source:
            raise RequestError(
                "GOOGLE_TRANSLATE_SOURCE_LANGUAGE_MISMATCH",
                request_stage="google_translate_text",
            )
        if response.get("targetLanguage") != target:
            raise RequestError(
                "GOOGLE_TRANSLATE_TARGET_LANGUAGE_MISMATCH",
                request_stage="google_translate_text",
            )
        if response.get("finalityEvidence") != GOOGLE_TRANSLATE_WEB_FINALITY:
            raise RequestError(
                "GOOGLE_TRANSLATE_FINALITY_UNPROVEN",
                request_stage="google_translate_text",
            )
        if response.get("canonicalCompletionProven") is not False:
            raise RequestError(
                "GOOGLE_TRANSLATE_CANONICAL_COMPLETION_MUST_REMAIN_UNPROVEN",
                request_stage="google_translate_text",
            )
        if response.get("automaticRetry") is not False:
            raise RequestError(
                "GOOGLE_TRANSLATE_AUTOMATIC_RETRY_FORBIDDEN",
                request_stage="google_translate_text",
            )

        return GoogleTranslateTextResult(
            translated_text=translated_text.strip(),
            source_language=source,
            target_language=target,
            final_url=final_url,
            tab_id=response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None,
            elapsed_ms=response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None,
            finality_evidence=GOOGLE_TRANSLATE_WEB_FINALITY,
            canonical_completion_proven=False,
            automatic_retry=False,
        )
