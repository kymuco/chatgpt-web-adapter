from __future__ import annotations

import json
import uuid

from .exceptions import RequestError
from .google_translate_web import (
    GOOGLE_TRANSLATE_TEXT_CAPABILITY_ID,
    GOOGLE_TRANSLATE_WEB_FINALITY,
    GOOGLE_TRANSLATE_WEB_PRODUCT_ID,
    GOOGLE_TRANSLATE_WEB_SUPPORT_TIER,
    GoogleTranslateOutcomeAmbiguousError,
    GoogleTranslateWebCapability,
)


def main() -> int:
    capability = GoogleTranslateWebCapability(operation_timeout=30.0)
    health = capability.health()
    if not health.available or not health.extension_connected:
        raise RuntimeError("GOOGLE_TRANSLATE_LIVE_GATE_BROWSER_BRIDGE_UNAVAILABLE")

    try:
        result = capability.translate_text(
            "hello",
            source_language="en",
            target_language="es",
        )
    except GoogleTranslateOutcomeAmbiguousError as error:
        try:
            characterization = capability.bridge._rpc(  # noqa: SLF001
                {
                    "type": "characterize_translate_result",
                    "request_id": uuid.uuid4().hex,
                    "timeoutMs": 10_000,
                },
                timeout=10.0,
            )
        except RequestError as characterization_error:
            characterization = {
                "ok": False,
                "error": str(characterization_error),
            }

        payload = {
            "result": "AMBIGUOUS_WITH_IMMEDIATE_READ_ONLY_CHARACTERIZATION",
            "translation_error": str(error),
            "characterization": {
                "ok": characterization.get("ok"),
                "error": characterization.get("error"),
                "url": characterization.get("url"),
                "candidate_count": characterization.get("candidateCount"),
                "candidates": characterization.get("candidates"),
                "output_region": characterization.get("outputRegion"),
                "diagnostic_count": characterization.get("diagnosticCount"),
                "diagnostic_candidates": characterization.get(
                    "diagnosticCandidates"
                ),
            },
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 2

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
