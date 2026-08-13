from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SUPPORTED_BROWSERLESS_PRODUCT_WRITE_VERDICT = (
    "SUPPORTED_BROWSERLESS_PRODUCT_WRITE_NOT_FOUND"
)

CAPABILITY_MATRIX: tuple[dict[str, str], ...] = (
    {
        "gate": "B0",
        "capability": "canonical_conversation_read",
        "verdict": "PASS",
        "boundary": "existing SDK HTTP/curl read path; no browser runtime required",
    },
    {
        "gate": "B1",
        "capability": "saved_session_reuse",
        "verdict": "PASS_WITH_PRECONDITION",
        "boundary": "requires still-valid saved authorization; no interactive repair",
    },
    {
        "gate": "B2",
        "capability": "interactive_auth_bootstrap",
        "verdict": "BROWSER_REQUIRED",
        "boundary": "current adapter login bootstrap is browser-owned",
    },
    {
        "gate": "B3",
        "capability": "supported_consumer_chatgpt_turn_api",
        "verdict": SUPPORTED_BROWSERLESS_PRODUCT_WRITE_VERDICT,
        "boundary": "no supported browser-independent ordinary ChatGPT product write surface identified",
    },
    {
        "gate": "B4",
        "capability": "sign_in_with_chatgpt",
        "verdict": "IDENTITY_ONLY",
        "boundary": "does not provide ordinary ChatGPT conversation or memory access",
    },
    {
        "gate": "B5",
        "capability": "apps_sdk_mcp",
        "verdict": "REVERSE_DIRECTION",
        "boundary": "connects tools/data into ChatGPT rather than exposing ChatGPT as a client turn API",
    },
    {
        "gate": "B6",
        "capability": "openai_api",
        "verdict": "SEPARATE_PRODUCT",
        "boundary": "browserless model API, but not the consumer ChatGPT subscription/session surface",
    },
    {
        "gate": "B7",
        "capability": "minimum_supported_product_write_runtime",
        "verdict": "BROWSER_NATIVE_BASELINE",
        "boundary": "PR8.1/PR8.1.1 official-page-owned write remains the minimum proven substrate",
    },
)


@dataclass(frozen=True)
class BrowserlessReadProbeResult:
    attempted: bool
    ok: bool
    conversation_id: str
    status: str | None
    sampled_message_count: int
    last_message_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capability_matrix() -> list[dict[str, str]]:
    return [dict(item) for item in CAPABILITY_MATRIX]


def base_feasibility_report() -> dict[str, Any]:
    return {
        "verdict": SUPPORTED_BROWSERLESS_PRODUCT_WRITE_VERDICT,
        "supported_browserless_product_write_available": False,
        "capabilities": capability_matrix(),
        "governance": {
            "read_only_probe": True,
            "direct_product_write_probe": False,
            "challenge_solver_expansion": False,
            "browser_protection_emulation": False,
        },
    }


def run_browserless_read_probe(
    client: Any,
    conversation: Any,
    *,
    sample_limit: int = 5,
) -> BrowserlessReadProbeResult:
    if isinstance(sample_limit, bool) or not isinstance(sample_limit, int):
        raise TypeError("sample_limit must be an int")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    status = client.get_status(conversation)
    messages = client.get_messages(
        conversation,
        limit=sample_limit,
        include_empty=True,
    )
    conversation_id = getattr(status, "conversation_id", None)
    if not isinstance(conversation_id, str) or not conversation_id:
        from .types import ConversationRef

        conversation_id = ConversationRef.from_any(conversation).conversation_id

    last_message_id = None
    if messages:
        candidate = getattr(messages[-1], "message_id", None)
        if isinstance(candidate, str) and candidate:
            last_message_id = candidate

    status_value = getattr(status, "status", None)
    if not isinstance(status_value, str):
        status_value = None

    return BrowserlessReadProbeResult(
        attempted=True,
        ok=True,
        conversation_id=conversation_id,
        status=status_value,
        sampled_message_count=len(messages),
        last_message_id=last_message_id,
    )
