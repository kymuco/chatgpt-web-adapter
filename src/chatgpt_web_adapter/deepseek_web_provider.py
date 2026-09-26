from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .browser_native_provider import BrowserNativeTurnProvider
from .exceptions import RequestError
from .types import ChatConversation, ConversationRef

DEEPSEEK_WEB_PROVIDER_ID = "deepseek"


@dataclass(frozen=True)
class DeepSeekWebTurnResult:
    conversation_id: str
    assistant_text: str
    final_url: str
    tab_id: int | None
    tab_was_active: bool
    elapsed_ms: int | None
    submit_strategy: str | None
    submit_button_selector: str | None
    completion_proof: str
    stable_for_ms: int | None


class DeepSeekWebWriteOutcomeAmbiguousError(RequestError):
    """Post-delegation DeepSeek outcome that must never be replayed automatically."""

    reconciliation_required = True
    automatic_retry_allowed = False


class DeepSeekWebTurnProvider(BrowserNativeTurnProvider):
    """Drive DeepSeek Web through the existing Native Messaging browser bridge."""

    provider_id = DEEPSEEK_WEB_PROVIDER_ID

    @staticmethod
    def _conversation_id(
        conversation: ConversationRef
        | ChatConversation
        | dict[str, Any]
        | str
        | None,
    ) -> str | None:
        if conversation is None:
            return None
        return ConversationRef.from_any(conversation).conversation_id

    def send_text(
        self,
        text: str,
        *,
        conversation: ConversationRef
        | ChatConversation
        | dict[str, Any]
        | str
        | None = None,
        timeout: float | None = None,
    ) -> DeepSeekWebTurnResult:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if len(text) > 200_000:
            raise ValueError("text is too large for DeepSeek Web turn")

        conversation_id = self._conversation_id(conversation)
        total_timeout = self.turn_timeout if timeout is None else float(timeout)
        if total_timeout <= 0:
            raise ValueError("timeout must be positive")

        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "providerId": self.provider_id,
                "conversationId": conversation_id,
                "text": text,
                "timeoutMs": int(total_timeout * 1000),
            },
            timeout=total_timeout + self.connect_timeout,
        )
        if response.get("request_id") != request_id:
            raise RequestError(
                "DEEPSEEK_WEB_RESPONSE_MISMATCH",
                request_stage="deepseek_web_turn",
            )
        if response.get("ok") is not True:
            error = str(response.get("error") or "DEEPSEEK_WEB_TURN_FAILED")
            if error.startswith(
                "DEEPSEEK_WRITE_OUTCOME_AMBIGUOUS_RECONCILIATION_REQUIRED:"
            ):
                raise DeepSeekWebWriteOutcomeAmbiguousError(
                    error,
                    request_stage="deepseek_web_turn",
                )
            raise RequestError(error, request_stage="deepseek_web_turn")

        if response.get("providerId") != self.provider_id:
            raise RequestError(
                "DEEPSEEK_WEB_PROVIDER_ID_MISMATCH",
                request_stage="deepseek_web_turn",
            )

        resolved_conversation_id = response.get("conversationId")
        assistant_text = response.get("assistantText")
        final_url = response.get("finalUrl")
        completion_proof = response.get("completionProof")
        if (
            not isinstance(resolved_conversation_id, str)
            or not resolved_conversation_id.strip()
        ):
            raise RequestError(
                "DEEPSEEK_WEB_CONVERSATION_ID_MISSING",
                request_stage="deepseek_web_turn",
            )
        if not isinstance(assistant_text, str) or not assistant_text.strip():
            raise RequestError(
                "DEEPSEEK_WEB_ASSISTANT_TEXT_MISSING",
                request_stage="deepseek_web_turn",
            )
        if (
            not isinstance(final_url, str)
            or not final_url.startswith("https://chat.deepseek.com/")
        ):
            raise RequestError(
                "DEEPSEEK_WEB_FINAL_URL_INVALID",
                request_stage="deepseek_web_turn",
            )
        if completion_proof != "stable_assistant_dom":
            raise RequestError(
                "DEEPSEEK_WEB_COMPLETION_PROOF_INVALID",
                request_stage="deepseek_web_turn",
            )

        return DeepSeekWebTurnResult(
            conversation_id=resolved_conversation_id.strip(),
            assistant_text=assistant_text.strip(),
            final_url=final_url,
            tab_id=response.get("tabId")
            if isinstance(response.get("tabId"), int)
            else None,
            tab_was_active=bool(response.get("tabWasActive")),
            elapsed_ms=response.get("elapsedMs")
            if isinstance(response.get("elapsedMs"), int)
            else None,
            submit_strategy=response.get("submitStrategy")
            if isinstance(response.get("submitStrategy"), str)
            else None,
            submit_button_selector=response.get("submitButtonSelector")
            if isinstance(response.get("submitButtonSelector"), str)
            else None,
            completion_proof=completion_proof,
            stable_for_ms=response.get("stableForMs")
            if isinstance(response.get("stableForMs"), int)
            else None,
        )
