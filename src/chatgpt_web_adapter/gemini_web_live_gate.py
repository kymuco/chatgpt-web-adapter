from __future__ import annotations

import json
import uuid

from .gemini_web import GeminiWebRuntime
from .product_provider import product_provider_boundary


def run_live_gate(*, timeout: float = 150.0) -> dict[str, object]:
    runtime = GeminiWebRuntime()
    boundary = product_provider_boundary(runtime)
    health = runtime.health()
    if not health.ready:
        raise RuntimeError(
            "GEMINI_WEB_LIVE_GATE_NOT_READY: install/reload the browser-native "
            "extension, keep its Native Messaging host running, and sign in to "
            "https://gemini.google.com in that Chrome profile"
        )

    first_marker = f"GM-FIRST-{uuid.uuid4().hex[:12]}"
    second_marker = f"GM-CONT-{uuid.uuid4().hex[:12]}"

    first = runtime.send_text(
        f"Reply with exactly this token and nothing else: {first_marker}",
        timeout=timeout,
    )
    conversation_id = first.conversation.conversation_id
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError("GEMINI_WEB_LIVE_GATE_NEW_CHAT_IDENTITY_MISSING")
    if first_marker not in first.text:
        raise RuntimeError("GEMINI_WEB_LIVE_GATE_NEW_CHAT_TEXT_MISMATCH")

    second = runtime.send_text(
        f"Reply with exactly this token and nothing else: {second_marker}",
        conversation=conversation_id,
        timeout=timeout,
    )
    if second.conversation.conversation_id != conversation_id:
        raise RuntimeError("GEMINI_WEB_LIVE_GATE_CONTINUATION_IDENTITY_CHANGED")
    if second_marker not in second.text:
        raise RuntimeError("GEMINI_WEB_LIVE_GATE_CONTINUATION_TEXT_MISMATCH")

    return {
        "provider_boundary": boundary.to_dict(),
        "health": health.to_dict(),
        "new_chat": {
            "conversation_id_present": True,
            "marker_match": True,
            "text_length": len(first.text),
        },
        "continuation": {
            "same_conversation_id": True,
            "marker_match": True,
            "text_length": len(second.text),
        },
        "automatic_write_retry": False,
        "fallback_transport": None,
        "canonical_completion_proven": False,
        "result": "PASS",
    }


def main() -> int:
    try:
        report = run_live_gate()
    except Exception as error:
        print(
            json.dumps(
                {
                    "result": "FAIL",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
