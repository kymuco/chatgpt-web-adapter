from __future__ import annotations

import argparse
import json
import uuid

from chatgpt_web_adapter import (
    CapabilityState,
    DeepSeekWebRuntime,
    product_provider_boundary,
)
from chatgpt_web_adapter.product_capabilities import CONTINUATION, NEW_CHAT, TEXT_TURNS


def _marker(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR15.53 live gate for minimal DeepSeek Web new-chat + continuation."
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")

    runtime = DeepSeekWebRuntime()
    boundary = product_provider_boundary(runtime)
    health = runtime.health()
    if not health.ready:
        raise RuntimeError(
            "DeepSeek Web bridge is not ready; reload the unpacked extension and "
            "ensure the Native Messaging host is running"
        )

    capabilities = runtime.capabilities()
    for capability in (TEXT_TURNS, NEW_CHAT, CONTINUATION):
        if capabilities.state(capability) is not CapabilityState.AVAILABLE:
            raise RuntimeError(f"required capability not available: {capability}")

    first_marker = _marker("DS_PR15_53_FIRST")
    first = runtime.send_text_observed(
        f"Reply with exactly this token and nothing else: {first_marker}",
        timeout=args.timeout,
    )
    first_conversation_id = first.response.conversation.conversation_id
    if not first_conversation_id:
        raise RuntimeError("first turn returned no conversation identity")
    if first_marker not in first.response.text:
        raise RuntimeError("first turn did not return the requested marker")

    second_marker = _marker("DS_PR15_53_SECOND")
    second = runtime.send_text_observed(
        f"Reply with exactly this token and nothing else: {second_marker}",
        conversation=first_conversation_id,
        timeout=args.timeout,
    )
    if second.response.conversation.conversation_id != first_conversation_id:
        raise RuntimeError("continuation changed the local conversation identity")
    if second_marker not in second.response.text:
        raise RuntimeError("continuation did not return the requested marker")

    for execution in (first, second):
        provenance = execution.provenance
        if provenance is None:
            raise RuntimeError("DeepSeek execution returned no provenance")
        if provenance.completion.canonical_completion_proven:
            raise RuntimeError("DeepSeek proof fabricated canonical server finality")
        if execution.observation.get("completion_proof") != "stable_assistant_dom":
            raise RuntimeError("DeepSeek completion proof is not stable_assistant_dom")

    print(
        json.dumps(
            {
                "provider_boundary": boundary.to_dict(),
                "health": health.to_dict(),
                "conversation_id": first_conversation_id,
                "new_chat": {
                    "marker_observed": True,
                    "response_chars": len(first.response.text),
                    "completion_proof": first.observation.get("completion_proof"),
                    "stable_for_ms": first.observation.get("stable_for_ms"),
                },
                "continuation": {
                    "same_conversation_id": True,
                    "marker_observed": True,
                    "response_chars": len(second.response.text),
                    "completion_proof": second.observation.get("completion_proof"),
                    "stable_for_ms": second.observation.get("stable_for_ms"),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
