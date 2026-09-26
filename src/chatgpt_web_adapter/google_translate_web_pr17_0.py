from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError


GOOGLE_TRANSLATE_PRODUCT_ID = "google-translate"
GOOGLE_TRANSLATE_WEB_TRANSPORT = "google-translate-web"
GOOGLE_TRANSLATE_TEXT_CAPABILITY = "translate_text"
GOOGLE_TRANSLATE_PRODUCT_SEMANTICS = "google-translate-web-text"


@dataclass(frozen=True)
class GoogleTranslateWebHealth:
    ready: bool
    reason: str
    bridge_available: bool
    extension_connected: bool
    transport: str = GOOGLE_TRANSLATE_WEB_TRANSPORT

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GoogleTranslateTextResult:
    text: str
    source_language: str
    target_language: str
    final_url: str
    tab_id: int | None
    elapsed_ms: int | None
    finality_evidence: str
    canonical_result_proven: bool
    automatic_write_retry: bool
    fallback_transport: str | None
    conversation_semantics: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GoogleTranslateOutcomeAmbiguousError(RequestError):
    """Outcome after source-page mutation may have executed.

    PR17.0 deliberately preserves the same no-replay discipline proven by the
    chat providers without claiming that translation is a conversation turn.
    """

    reconciliation_required = True
    automatic_retry_allowed = False


class GoogleTranslateWebRuntime:
    """Experimental non-chat Google Translate Web capability.

    This runtime intentionally does not implement ProductWriteTransport and is
    not accepted by ProductProviderBoundary schema 2. PR17.0 exists to test
    whether a useful hosted capability can reuse the browser-owned safety model
    without pretending to have chat/conversation semantics.
    """

    product_id = GOOGLE_TRANSLATE_PRODUCT_ID
    product_semantics = GOOGLE_TRANSLATE_PRODUCT_SEMANTICS
    transport = GOOGLE_TRANSLATE_WEB_TRANSPORT
    capability = GOOGLE_TRANSLATE_TEXT_CAPABILITY
    support_tier = "EXPERIMENTAL"

    def __init__(
        self,
        *,
        state_dir: str | None = None,
        connect_timeout: float = 3.0,
        operation_timeout: float = 45.0,
        bridge: BrowserNativeTurnProvider | None = None,
    ) -> None:
        if operation_timeout <= 0:
            raise ValueError("operation_timeout must be positive")
        self._bridge = bridge or BrowserNativeTurnProvider(
            state_dir=state_dir,
            connect_timeout=connect_timeout,
            turn_timeout=operation_timeout,
        )
        self.operation_timeout = float(operation_timeout)

    def health(self) -> GoogleTranslateWebHealth:
        status = self._bridge.status()
        ready = bool(status.available and status.extension_connected)
        return GoogleTranslateWebHealth(
            ready=ready,
            reason="READY" if ready else "BROWSER_NATIVE_EXTENSION_UNAVAILABLE",
            bridge_available=bool(status.available),
            extension_connected=bool(status.extension_connected),
        )

    @staticmethod
    def _normalize_language(value: str, *, source: bool) -> str:
        if not isinstance(value, str):
            raise TypeError("language must be a string")
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("language must not be empty")
        if normalized == "auto":
            if source:
                return normalized
            raise ValueError("target_language cannot be auto")
        pieces = normalized.split("-")
        if not all(
            piece.isalnum() and 2 <= len(piece) <= 8
            for piece in pieces
        ):
            raise ValueError(f"invalid language code: {value!r}")
        return normalized

    def translate(
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
            raise ValueError("Google Translate Web text input is limited to 5000 characters")

        source = self._normalize_language(source_language, source=True)
        target = self._normalize_language(target_language, source=False)
        total_timeout = self.operation_timeout if timeout is None else float(timeout)
        if total_timeout <= 0:
            raise ValueError("timeout must be positive")

        try:
            response = self._bridge._rpc(  # noqa: SLF001 - PR17.0 research boundary
                {
                    "type": "translate_text",
                    "request_id": uuid.uuid4().hex,
                    "text": text,
                    "sourceLanguage": source,
                    "targetLanguage": target,
                    "timeoutMs": int(total_timeout * 1000),
                },
                timeout=total_timeout,
            )
        except RequestError as error:
            if str(error).startswith(
                "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION:"
            ):
                raise GoogleTranslateOutcomeAmbiguousError(
                    f"GOOGLE_TRANSLATE_OPERATION_FAILED: {error}",
                    request_stage="google_translate_web",
                ) from error
            raise

        if response.get("ok") is not True:
            error = str(response.get("error") or "unknown error")
            if error.startswith(
                "GOOGLE_TRANSLATE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ):
                raise GoogleTranslateOutcomeAmbiguousError(
                    f"GOOGLE_TRANSLATE_OPERATION_FAILED: {error}",
                    request_stage="google_translate_web",
                )
            raise RequestError(
                f"GOOGLE_TRANSLATE_OPERATION_FAILED: {error}",
                request_stage="google_translate_web",
            )

        if response.get("productId") != GOOGLE_TRANSLATE_PRODUCT_ID:
            raise RequestError(
                "GOOGLE_TRANSLATE_PRODUCT_ID_MISMATCH",
                request_stage="google_translate_web",
            )
        if response.get("capability") != GOOGLE_TRANSLATE_TEXT_CAPABILITY:
            raise RequestError(
                "GOOGLE_TRANSLATE_CAPABILITY_MISMATCH",
                request_stage="google_translate_web",
            )

        translated = response.get("translatedText")
        final_url = response.get("finalUrl")
        if not isinstance(translated, str) or not translated.strip():
            raise RequestError(
                "GOOGLE_TRANSLATE_RESULT_TEXT_MISSING",
                request_stage="google_translate_web",
            )
        if not isinstance(final_url, str) or not final_url.startswith(
            "https://translate.google.com/"
        ):
            raise RequestError(
                "GOOGLE_TRANSLATE_FINAL_ROUTE_INVALID",
                request_stage="google_translate_web",
            )
        if response.get("sourceLanguage") != source:
            raise RequestError(
                "GOOGLE_TRANSLATE_SOURCE_LANGUAGE_MISMATCH",
                request_stage="google_translate_web",
            )
        if response.get("targetLanguage") != target:
            raise RequestError(
                "GOOGLE_TRANSLATE_TARGET_LANGUAGE_MISMATCH",
                request_stage="google_translate_web",
            )
        if response.get("finalityEvidence") != "PAGE_DOM_STABLE_RESULT":
            raise RequestError(
                "GOOGLE_TRANSLATE_RESULT_FINALITY_UNPROVEN",
                request_stage="google_translate_web",
            )
        if response.get("canonicalResultProven") is not False:
            raise RequestError(
                "GOOGLE_TRANSLATE_CANONICAL_RESULT_MUST_REMAIN_UNPROVEN",
                request_stage="google_translate_web",
            )
        if response.get("automaticWriteRetry") is not False:
            raise RequestError(
                "GOOGLE_TRANSLATE_AUTOMATIC_RETRY_FORBIDDEN",
                request_stage="google_translate_web",
            )
        if response.get("fallbackTransport") is not None:
            raise RequestError(
                "GOOGLE_TRANSLATE_FALLBACK_TRANSPORT_FORBIDDEN",
                request_stage="google_translate_web",
            )
        if response.get("conversationSemantics") is not False:
            raise RequestError(
                "GOOGLE_TRANSLATE_CONVERSATION_SEMANTICS_FORBIDDEN",
                request_stage="google_translate_web",
            )

        return GoogleTranslateTextResult(
            text=translated.strip(),
            source_language=source,
            target_language=target,
            final_url=final_url,
            tab_id=response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None,
            elapsed_ms=(
                response.get("elapsedMs")
                if isinstance(response.get("elapsedMs"), int)
                else None
            ),
            finality_evidence="PAGE_DOM_STABLE_RESULT",
            canonical_result_proven=False,
            automatic_write_retry=False,
            fallback_transport=None,
            conversation_semantics=False,
        )

    def governance(self) -> dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_semantics": self.product_semantics,
            "transport": self.transport,
            "capability": self.capability,
            "support_tier": self.support_tier,
            "product_provider_boundary_schema": None,
            "implements_product_write_transport": False,
            "conversation_semantics": False,
            "canonical_result_interface": None,
            "canonical_result_proven": False,
            "finality_evidence": "PAGE_DOM_STABLE_RESULT",
            "automatic_write_retry": False,
            "fallback_transport": None,
            "ambiguous_operation_requires_reconciliation": True,
            "browser_owned": True,
            "official_api_used": False,
            "private_http_protocol_used": False,
        }
