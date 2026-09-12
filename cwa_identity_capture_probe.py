"""CWA identity-capture live probe (ordinary-text `WEB:*` promotion evidence).

Performs EXACTLY ONE ordinary-text product write through the production
browser-owned runtime with the identity-capture diagnostic service worker
loaded, then reads canonical status/messages for every observed identity
candidate VERBATIM (never stripped, never inferred).

Evidence rules enforced here:
- automatic write retry is forbidden; one submit attempt total;
- no `WEB:` prefix stripping, no UUID inference, no route/tab identity promotion;
- the journal stores only sanitized identity/correlation facts produced by the
  diagnostic service worker (no raw SSE bodies, cookies, tokens, or auth).
"""

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatgpt_web_adapter import assemble_product_runtime
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.product_model_profile_pr8_10 import (
    ProductModelProfileProvider,
)
from chatgpt_web_adapter.types import ConversationRef

JOURNAL = Path("cwa_identity_capture_journal_3.json")
PROMPT = (
    "Chỉ trả lời chính xác chuỗi sau, không thêm nội dung khác: "
    "SOC_BRAIN_CWA_IDCAP3_OK"
)
EXPECTED_REPLY = "SOC_BRAIN_CWA_IDCAP3_OK"
# Probe-level budget via the public submit timeout parameter only (SW clamps at
# 300s). The run-1 finding — ordinary-turn RPC deadline can expire before native
# completion due to pre-turn tab reconciliation + post-network tail — is NOT
# patched anywhere in production code during this experiment.
WRITE_TIMEOUT = 240.0
WRITE_BUDGET = 1


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def persist(data: dict[str, Any]) -> None:
    tmp = JOURNAL.with_suffix(".tmp")
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, JOURNAL)


class _IdentityCaptureProvider(ProductModelProfileProvider):
    """Production provider; tees raw `_rpc` responses for diagnostic capture.

    No behavior change: every response is returned untouched. The raw turn
    response carries the service worker's sanitized `cwaIdentityCaptureDiag`
    record alongside the standard turn fields.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.captured_responses: list[dict[str, Any]] = []

    def _rpc(self, payload: dict[str, Any], *, timeout: float, on_event=None) -> dict[str, Any]:
        response = super()._rpc(payload, timeout=timeout, on_event=on_event)
        try:
            self.captured_responses.append(
                {"payloadType": payload.get("type"), "response": json.loads(
                    json.dumps(response, ensure_ascii=False, default=str)
                )}
            )
        except Exception:
            pass
        return response

    def turn_capture(self) -> dict[str, Any] | None:
        for entry in reversed(self.captured_responses):
            if entry.get("payloadType") != "turn":
                continue
            response = entry.get("response")
            if isinstance(response, dict):
                capture = response.get("cwaIdentityCaptureDiag")
                if isinstance(capture, dict):
                    return capture
        return None


def _identity_candidates(ack_dict: dict[str, Any], capture: dict[str, Any] | None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def add(value: Any, source: str, extra: dict[str, Any] | None = None) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        if len(candidates) >= 16:
            return
        identity = value.strip()
        if any(item["identity"] == identity for item in candidates):
            return
        candidates.append(
            {
                "identity": identity,
                "source": source,
                "webPrefixed": identity.startswith("WEB:"),
                **(extra or {}),
            }
        )

    add(ack_dict.get("conversation_id"), "ack_promoted")
    result = capture.get("result") if isinstance(capture, dict) else None
    if isinstance(result, dict):
        add(result.get("promotedConversationId"), "turn_result_promoted")
        add(result.get("routeConversationId"), "route_diagnostic_only")
    if isinstance(capture, dict):
        parses = capture.get("identityParses")
        if isinstance(parses, list):
            for index, parse in enumerate(parses):
                if not isinstance(parse, dict):
                    continue
                add(
                    parse.get("conversationId"),
                    "request_bound_response_parse",
                    {
                        "associatedRequestId": parse.get("associatedRequestId"),
                        "parseIndex": index,
                        "turnExchangeId": parse.get("turnExchangeId"),
                    },
                )
        requests = capture.get("conversationWriteRequests")
        if isinstance(requests, list):
            for index, request in enumerate(requests):
                if not isinstance(request, dict):
                    continue
                body = request.get("requestBodyIdentity")
                if isinstance(body, dict) and body.get("resolved") is True:
                    add(
                        body.get("conversationId"),
                        "request_body_slot",
                        {"requestId": request.get("requestId")},
                    )
                sse_events = request.get("sseIdentityEvents")
                if isinstance(sse_events, list):
                    for event in sse_events:
                        if not isinstance(event, dict):
                            continue
                        fields = event.get("identityFields")
                        if not isinstance(fields, list):
                            continue
                        for field in fields:
                            if not isinstance(field, dict):
                                continue
                            add(
                                field.get("value"),
                                "sse_bound_response_parse",
                                {
                                    "requestId": event.get("requestId"),
                                    "fieldPath": field.get("path"),
                                    "eventType": event.get("eventType"),
                                    "sseOrderIndex": event.get("orderIndex"),
                                },
                            )
    return candidates


def _safe_call(label: str, func, *args, **kwargs) -> dict[str, Any]:
    try:
        value = func(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 - diagnostic boundary
        return {
            "target": label,
            "ok": False,
            "errorType": type(error).__name__,
            "error": str(error),
        }
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    elif isinstance(value, list):
        value = [
            item.to_dict() if hasattr(item, "to_dict") else item for item in value
        ]
    return {"target": label, "ok": True, "result": value}


def _assistant_texts(messages_result: dict[str, Any], limit: int = 3) -> list[str]:
    if messages_result.get("ok") is not True:
        return []
    value = messages_result.get("result")
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for item in reversed(value):
        if isinstance(item, dict) and item.get("role") == "assistant":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
            if len(texts) >= limit:
                break
    return list(reversed(texts))


def main() -> int:
    journal: dict[str, Any] = {
        "schema": 2,
        "probe": "CWA_IDENTITY_CAPTURE_ORDINARY_TEXT",
        "startedAt": now(),
        "prompt": PROMPT,
        "expectedReply": EXPECTED_REPLY,
        "writeBudget": WRITE_BUDGET,
        "state": "STARTING",
        "automaticRetry": False,
    }
    persist(journal)

    provider = _IdentityCaptureProvider()
    client = ChatGPTWebClient(auto_login=False, auto_sentinel=False)
    runtime = assemble_product_runtime(client=client, provider=provider)

    events: list[dict[str, Any]] = []
    journal["state"] = "SUBMITTING"
    journal["submitStartedAt"] = now()
    persist(journal)

    try:
        ack = runtime.submit(
            PROMPT,
            timeout=WRITE_TIMEOUT,
            poll_interval=0.5,
            on_event=events.append,
        )
    except Exception as error:  # noqa: BLE001 - durable failure journal
        journal["state"] = "SUBMIT_ERROR"
        journal["submitErrorAt"] = now()
        journal["submitErrorType"] = type(error).__name__
        journal["submitError"] = str(error)
        journal["diagnosticCapture"] = provider.turn_capture()
        journal["events"] = events
        try:
            journal["lifecycleSnapshot"] = runtime.submission_lifecycle_snapshot()
        except Exception as snapshot_error:  # noqa: BLE001
            journal["snapshotError"] = str(snapshot_error)
        journal["finishedAt"] = now()
        persist(journal)

        print("=== SUBMIT ERROR - DO NOT RETRY ===")
        print(type(error).__name__)
        print(str(error))
        print(f"Journal: {JOURNAL.resolve()}")
        return 2

    # Durable ACK persists BEFORE any canonical readback attempt.
    ack_dict = ack.to_dict() if hasattr(ack, "to_dict") else {}
    capture = provider.turn_capture()
    journal["state"] = "WRITE_ACKNOWLEDGED"
    journal["writeAcknowledgedAt"] = now()
    journal["ack"] = ack_dict
    journal["events"] = events
    journal["diagnosticCapture"] = capture
    journal["identityCandidates"] = _identity_candidates(ack_dict, capture)
    # Exact response evidence from the revision-safe stream (streamTextObservations).
    journal["streamedAssistantText"] = "".join(
        str(event.get("text", "")) if event.get("type") == "assistant_text_snapshot"
        else str(event.get("delta", "")) if event.get("type") == "assistant_text_delta"
        else ""
        for event in events
        if event.get("type") in ("assistant_text_snapshot", "assistant_text_delta")
    )
    persist(journal)

    print("=== WRITE ACK PERSISTED (NO RETRY) ===")
    print(json.dumps(ack_dict, ensure_ascii=False, indent=2))

    # Canonical readability per candidate, VERBATIM identity only.
    canonical_results: list[dict[str, Any]] = []
    for candidate in journal["identityCandidates"]:
        identity = candidate["identity"]
        conversation = ConversationRef(identity)
        status_result = _safe_call(
            f"get_status[{candidate['source']}]",
            runtime.get_status,
            conversation,
        )
        messages_result = _safe_call(
            f"get_messages[{candidate['source']}]",
            runtime.get_messages,
            conversation,
        )
        canonical_results.append(
            {
                "identity": identity,
                "source": candidate["source"],
                "webPrefixed": candidate["webPrefixed"],
                "status": status_result,
                "messages": messages_result,
                "assistantTexts": _assistant_texts(messages_result),
                "exactReplyRecovered": EXPECTED_REPLY
                in _assistant_texts(messages_result),
            }
        )
    journal["state"] = "CANONICAL_PROBED"
    journal["canonicalResults"] = canonical_results
    journal["canonicalProbedAt"] = now()
    persist(journal)

    # Finality attempt on the promoted identity; failure is evidence, never retried.
    try:
        response = runtime.await_final(ack)
        journal["finality"] = {
            "ok": True,
            "response": response.to_dict() if hasattr(response, "to_dict") else str(response),
        }
        journal["state"] = "FINAL"
    except Exception as error:  # noqa: BLE001 - durable failure journal
        journal["finality"] = {
            "ok": False,
            "errorType": type(error).__name__,
            "error": str(error),
        }
        journal["state"] = "FINALITY_UNRESOLVED"
        try:
            journal["lifecycleSnapshot"] = runtime.submission_lifecycle_snapshot()
        except Exception as snapshot_error:  # noqa: BLE001
            journal["snapshotError"] = str(snapshot_error)
    journal["finishedAt"] = now()
    persist(journal)

    print("\n=== CANONICAL RESULTS (VERBATIM IDENTITIES) ===")
    for item in canonical_results:
        print(
            f"- {item['source']}: {item['identity']} "
            f"webPrefixed={item['webPrefixed']} "
            f"statusOk={item['status'].get('ok')} "
            f"messagesOk={item['messages'].get('ok')} "
            f"exactReplyRecovered={item['exactReplyRecovered']}"
        )
    print(f"\nJournal: {JOURNAL.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - crash journal
        try:
            persist(
                {
                    "schema": 2,
                    "probe": "CWA_IDENTITY_CAPTURE_ORDINARY_TEXT",
                    "state": "PROBE_CRASHED",
                    "crashAt": now(),
                    "crash": traceback.format_exc(),
                }
            )
        except Exception:
            pass
        print("PROBE_CRASHED", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(3)
