from __future__ import annotations

import json

from .google_translate_web import GoogleTranslateWebRuntime


def _normalized(value: str) -> str:
    return " ".join(value.lower().replace(".", " ").replace(",", " ").split())


def main() -> int:
    runtime = GoogleTranslateWebRuntime(operation_timeout=45.0)
    health = runtime.health()
    if not health.ready:
        raise RuntimeError(f"GOOGLE_TRANSLATE_WEB_NOT_READY: {health.reason}")

    first = runtime.translate(
        "The house is blue.",
        source_language="en",
        target_language="es",
    )
    first_normalized = _normalized(first.text)
    if "casa" not in first_normalized or "azul" not in first_normalized:
        raise RuntimeError(
            f"GOOGLE_TRANSLATE_FIRST_SEMANTIC_CHECK_FAILED: {first.text!r}"
        )

    second = runtime.translate(
        "One two three.",
        source_language="en",
        target_language="de",
    )
    second_normalized = _normalized(second.text)
    for token in ("eins", "zwei", "drei"):
        if token not in second_normalized:
            raise RuntimeError(
                f"GOOGLE_TRANSLATE_SECOND_SEMANTIC_CHECK_FAILED: {second.text!r}"
            )

    report = {
        "result": "PASS",
        "health": health.to_dict(),
        "governance": runtime.governance(),
        "first": first.to_dict(),
        "second": second.to_dict(),
        "non_chat_proof": {
            "conversation_semantics": False,
            "product_provider_boundary_schema": None,
            "implements_product_write_transport": False,
            "structured_parameters": [
                "text",
                "source_language",
                "target_language",
            ],
            "same_runtime_two_independent_operations": True,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
