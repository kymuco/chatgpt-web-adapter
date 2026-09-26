from __future__ import annotations

import json

from .google_translate_web import (
    GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
    GOOGLE_TRANSLATE_WEB_FINALITY,
    GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
    GOOGLE_TRANSLATE_WEB_SUPPORT_TIER,
    GoogleTranslateWebCapability,
)


def main() -> int:
    capability = GoogleTranslateWebCapability(operation_timeout=30.0)
    health = capability.health()
    if not health.available or not health.extension_connected:
        raise RuntimeError("GOOGLE_TRANSLATE_LIVE_GATE_BROWSER_BRIDGE_UNAVAILABLE")

    result = capability.translate_text(
        "hello",
        source_language="en",
        target_language="es",
    )
    if "hola" not in result.translated_text.casefold():
        raise RuntimeError(
            "GOOGLE_TRANSLATE_LIVE_GATE_UNEXPECTED_TRANSLATION:"
            f"{result.translated_text!r}"
        )

    payload = {
        "result": "PASS",
        "product_id": GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
        "capability_id": GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
        "support_tier": GOOGLE_TRANSLATE_WEB_SUPPORT_TIER,
        "input": {
            "text": "hello",
            "source_language": "en",
            "target_language": "es",
        },
        "translated_text": result.translated_text,
        "finality_evidence": result.finality_evidence,
        "canonical_completion_proven": result.canonical_completion_proven,
        "automatic_retry": result.automatic_retry,
        "conversation_semantics": False,
        "finality_expected": GOOGLE_TRANSLATE_WEB_FINALITY,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
