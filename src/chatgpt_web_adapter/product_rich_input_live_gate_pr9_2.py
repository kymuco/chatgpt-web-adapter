from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import tempfile
from typing import Any, Iterable
import uuid

from .client import ChatGPTWebClient
from .product_model_profile_pr8_10 import ProductModelProfileProvider
from .product_provenance import CompletionSource, ProductExecutionProvenance
from .product_runtime import assemble_product_runtime

SCHEMA = 1
PRODUCT_WRITE_BUDGET = 3

_IMAGE_REPLY = "SDK_PR9_2_IMAGE_NEW_CHAT_OK"
_FILE_REPLY = "SDK_PR9_2_FILE_NEW_CHAT_OK"
_CONTINUATION_REPLY = "SDK_PR9_2_MULTIMODAL_CONTINUATION_OK"

# Deterministic 1x1 PNG transport fixture. The fixture has no semantic role; it
# exists only to exercise the product image-upload path.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z93sAAAAASUVORK5CYII="
)


class ProductRichInputLiveProvider(ProductModelProfileProvider):
    """Production provider plus a PR9.2 no-write overlay-presence probe."""

    def rich_input_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        request_id = str(uuid.uuid4())
        response = self._rpc(
            {
                "type": "turn",
                "request_id": request_id,
                "characterizeRichInputSupport": True,
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        if response.get("request_id") != request_id:
            raise RuntimeError("PR9_2_RICH_INPUT_SUPPORT_RESPONSE_MISMATCH")
        if response.get("ok") is not True:
            raise RuntimeError(
                f"PR9_2_RICH_INPUT_SUPPORT_FAILED:{response.get('error') or 'unknown'}"
            )
        return {
            "supported": response.get("richInputSupported") is True,
            "schema": response.get("richInputSchemaVersion"),
            "staging_primitive": response.get("stagingPrimitive"),
            "max_attachment_count": response.get("maxAttachmentCount"),
            "native_messaging_carries_attachment_bytes": response.get(
                "nativeMessagingCarriesAttachmentBytes"
            ),
            "official_page_owns_upload": response.get("officialPageOwnsUpload"),
            "official_page_owns_protected_write": response.get(
                "officialPageOwnsProtectedWrite"
            ),
            "automatic_write_retry": response.get("automaticWriteRetry"),
            "fallback_transport": response.get("fallbackTransport"),
            "write_performed": response.get("writePerformed"),
        }


def _validate_support(support: dict[str, Any]) -> None:
    if support.get("supported") is not True or support.get("schema") != SCHEMA:
        raise RuntimeError("PR9_2_RICH_INPUT_SUPPORT_NOT_PROVEN")
    if support.get("staging_primitive") != "DOM.setFileInputFiles":
        raise RuntimeError("PR9_2_RICH_INPUT_STAGING_PRIMITIVE_MISMATCH")
    maximum = support.get("max_attachment_count")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        raise RuntimeError("PR9_2_RICH_INPUT_ATTACHMENT_LIMIT_INVALID")
    if support.get("native_messaging_carries_attachment_bytes") is not False:
        raise RuntimeError("PR9_2_NATIVE_MESSAGING_BYTE_BOUNDARY_NOT_PROVEN")
    if support.get("official_page_owns_upload") is not True:
        raise RuntimeError("PR9_2_OFFICIAL_PAGE_UPLOAD_OWNERSHIP_NOT_PROVEN")
    if support.get("official_page_owns_protected_write") is not True:
        raise RuntimeError("PR9_2_OFFICIAL_PAGE_WRITE_OWNERSHIP_NOT_PROVEN")
    if support.get("automatic_write_retry") is not False:
        raise RuntimeError("PR9_2_AUTOMATIC_WRITE_RETRY_MUST_BE_FALSE")
    if support.get("fallback_transport") is not None:
        raise RuntimeError("PR9_2_FALLBACK_TRANSPORT_MUST_BE_NONE")
    if support.get("write_performed") is not False:
        raise RuntimeError("PR9_2_SUPPORT_PROBE_MUST_BE_NO_WRITE")


def _events_of_type(events: Iterable[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [
        dict(event)
        for event in events
        if isinstance(event, dict) and event.get("type") == event_type
    ]


def _validate_execution(
    *,
    label: str,
    execution: Any,
    events: list[dict[str, Any]],
    expected_text: str,
    expected_attachment_count: int,
    expected_conversation_id: str | None = None,
) -> dict[str, Any]:
    response = execution.response
    actual_text = response.text.strip()
    if actual_text != expected_text:
        raise RuntimeError(
            f"PR9_2_{label}:UNEXPECTED_RESPONSE expected={expected_text!r} actual={actual_text!r}"
        )

    write_events = _events_of_type(events, "browser_native_write_completed")
    readback_events = _events_of_type(events, "browser_native_readback_completed")
    if len(write_events) != 1:
        raise RuntimeError(f"PR9_2_{label}:WRITE_EVENT_COUNT:{len(write_events)}")
    if len(readback_events) != 1:
        raise RuntimeError(f"PR9_2_{label}:READBACK_EVENT_COUNT:{len(readback_events)}")
    if write_events[0].get("attachment_count") != expected_attachment_count:
        raise RuntimeError(f"PR9_2_{label}:WRITE_ATTACHMENT_COUNT_MISMATCH")
    if readback_events[0].get("attachment_count") != expected_attachment_count:
        raise RuntimeError(f"PR9_2_{label}:READBACK_ATTACHMENT_COUNT_MISMATCH")

    observation = execution.observation
    if getattr(observation, "write_event_observed", None) is not True:
        raise RuntimeError(f"PR9_2_{label}:WRITE_OBSERVATION_NOT_PROVEN")

    provenance = execution.provenance
    if not isinstance(provenance, ProductExecutionProvenance):
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_MISSING")
    completion = provenance.completion
    if (
        completion.completed is not True
        or completion.source is not CompletionSource.CANONICAL_READBACK
        or completion.canonical_completion_proven is not True
    ):
        raise RuntimeError(f"PR9_2_{label}:CANONICAL_FINALITY_NOT_PROVEN")

    conversation_id = response.conversation.conversation_id
    message_id = response.conversation.message_id
    if provenance.identity.conversation_id != conversation_id:
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_CONVERSATION_ID_MISMATCH")
    if provenance.identity.message_id != message_id:
        raise RuntimeError(f"PR9_2_{label}:PROVENANCE_MESSAGE_ID_MISMATCH")
    if expected_conversation_id is not None and conversation_id != expected_conversation_id:
        raise RuntimeError(f"PR9_2_{label}:CONTINUATION_CONVERSATION_ID_MISMATCH")

    return {
        "label": label,
        "response": actual_text,
        "conversation_id": conversation_id,
        "message_id": message_id,
        "observed_model": provenance.identity.observed_model,
        "attachment_count": expected_attachment_count,
        "write_event_count": len(write_events),
        "readback_event_count": len(readback_events),
        "browser_authority_lease_id": write_events[0].get(
            "browser_authority_lease_id"
        ),
        "canonical_completion_proven": True,
        "completion_source": completion.source.value,
    }


def _write_fixtures(root: Path) -> tuple[Path, Path]:
    image = root / "pr9_2_transport_fixture.png"
    text_file = root / "pr9_2_transport_fixture.txt"
    image.write_bytes(_PNG_1X1)
    text_file.write_text(
        "PR9.2 deterministic general-file transport fixture.\n",
        encoding="utf-8",
    )
    return image, text_file


def _prompt(expected: str, *, fixture_kind: str) -> str:
    return (
        f"Reply with exactly: {expected}\n"
        f"The attached {fixture_kind} is only a transport fixture. Do not describe it."
    )


def run_live_gate(*, timeout: float = 150.0) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    provider = ProductRichInputLiveProvider()
    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    support = provider.rich_input_support(timeout=min(10.0, timeout))
    _validate_support(support)

    report: dict[str, Any] = {
        "ok": False,
        "pr": "PR9.2",
        "schema": SCHEMA,
        "product_write_budget": PRODUCT_WRITE_BUDGET,
        "write_attempts": 0,
        "write_completions": 0,
        "automatic_write_retry": False,
        "fallback_transport": None,
        "support": support,
        "turns": [],
    }

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-live-") as temp_dir:
        image_path, file_path = _write_fixtures(Path(temp_dir))

        image_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        image_execution = runtime.send_text_observed(
            _prompt(_IMAGE_REPLY, fixture_kind="PNG image"),
            media=[image_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=image_events.append,
        )
        report["write_completions"] += 1
        image_turn = _validate_execution(
            label="IMAGE_NEW_CHAT",
            execution=image_execution,
            events=image_events,
            expected_text=_IMAGE_REPLY,
            expected_attachment_count=1,
        )
        report["turns"].append(image_turn)

        file_events: list[dict[str, Any]] = []
        report["write_attempts"] += 1
        file_execution = runtime.send_text_observed(
            _prompt(_FILE_REPLY, fixture_kind="text file"),
            media=[file_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=file_events.append,
        )
        report["write_completions"] += 1
        file_turn = _validate_execution(
            label="FILE_NEW_CHAT",
            execution=file_execution,
            events=file_events,
            expected_text=_FILE_REPLY,
            expected_attachment_count=1,
        )
        report["turns"].append(file_turn)

        continuation_events: list[dict[str, Any]] = []
        continuation_id = image_execution.response.conversation.conversation_id
        report["write_attempts"] += 1
        continuation_execution = runtime.send_text_observed(
            _prompt(_CONTINUATION_REPLY, fixture_kind="text file"),
            conversation=image_execution.response.conversation,
            media=[file_path],
            timeout=timeout,
            conversation_mode="normal",
            on_event=continuation_events.append,
        )
        report["write_completions"] += 1
        continuation_turn = _validate_execution(
            label="MULTIMODAL_CONTINUATION",
            execution=continuation_execution,
            events=continuation_events,
            expected_text=_CONTINUATION_REPLY,
            expected_attachment_count=1,
            expected_conversation_id=continuation_id,
        )
        report["turns"].append(continuation_turn)

    if report["write_attempts"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_WRITE_BUDGET_MISMATCH")
    if report["write_completions"] != PRODUCT_WRITE_BUDGET:
        raise RuntimeError("PR9_2_WRITE_COMPLETION_COUNT_MISMATCH")

    report["ok"] = True
    report["summary"] = {
        "image_new_chat_proven": True,
        "general_file_new_chat_proven": True,
        "multimodal_continuation_proven": True,
        "canonical_finality_after_every_write": True,
        "exact_attachment_count_after_every_write": True,
        "native_messaging_attachment_bytes": False,
        "official_page_owned_upload_and_write": True,
        "automatic_write_retry": False,
        "fallback_transport": None,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PR9.2 bounded authenticated rich-input production live gate"
    )
    parser.add_argument("--acknowledge-live-writes", action="store_true")
    parser.add_argument("--timeout", type=float, default=150.0)
    args = parser.parse_args()
    if not args.acknowledge_live_writes:
        parser.error(
            "--acknowledge-live-writes is required; this gate performs exactly three product writes"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    report = run_live_gate(timeout=args.timeout)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
