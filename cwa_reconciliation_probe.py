"""CWA crash/restart reconciliation probe (gate B).

Phase `write`: EXACTLY ONE ordinary-text product write through the production
browser-owned runtime (PR12.3 request-bound SSE identity authority). The
durable ACK/journal (identity + correlation evidence) is fsync-persisted
BEFORE any finality attempt, then the process hard-crashes (os._exit) to
simulate losing the final response. No canonical read, no retry, no
await_final.

Phase `reconcile`: a brand-new process loads the durable journal and recovers
the conversation/turn/finality via canonical reads ONLY. The original write is
never resent. PASS requires: durable write count == 1, exactly one matching
user message (no duplicate), exact marker recovered with finish stop, request
message-id correlation, and a clean lifecycle snapshot.

Journals store only sanitized identity/correlation facts (no raw SSE bodies,
cookies, tokens, or auth).
"""

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chatgpt_web_adapter import assemble_product_runtime, ConversationRef
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.product_model_profile_pr8_10 import (
    ProductModelProfileProvider,
)

JOURNAL = Path("cwa_reconciliation_journal.json")
MARKER = "SOC_BRAIN_CWA_RECON4_OK"
PROMPT = f"Chỉ trả lời chính xác chuỗi sau, không thêm nội dung khác: {MARKER}"
WRITE_TIMEOUT = 240.0
KEEP_EVENT_TYPES = {
    "browser_native_turn_started",
    "assistant_text_snapshot",
    "assistant_text_delta",
    "browser_native_write_completed",
}
READ_ATTEMPTS = 3
READ_WAIT_S = (15.0, 30.0, 30.0)


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


class _ReconTeeProvider(ProductModelProfileProvider):
    """Production provider; tees raw `_rpc` responses for durable evidence.

    No behavior change: every response is returned untouched.
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

    def turn_response(self) -> dict[str, Any] | None:
        for entry in reversed(self.captured_responses):
            if entry.get("payloadType") != "turn":
                continue
            response = entry.get("response")
            if isinstance(response, dict):
                return response
        return None


def _authority_fields(turn_response: dict[str, Any] | None) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if not isinstance(turn_response, dict):
        return fields
    for key, value in turn_response.items():
        if key == "cwaIdentityCaptureDiag":
            continue
        if key.startswith("sse") or key in ("conversationId", "routeConversationIdentityAuthoritative"):
            fields[key] = value
    return fields


def _write_phase() -> int:
    journal: dict[str, Any] = {
        "schema": 1,
        "probe": "CWA_CRASH_RESTART_RECONCILIATION",
        "phase": "write",
        "startedAt": now(),
        "prompt": PROMPT,
        "expectedReply": MARKER,
        "writeBudget": 1,
        "state": "STARTING",
        "automaticRetry": False,
    }
    persist(journal)

    provider = _ReconTeeProvider()
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
        journal["diagnosticCapture"] = provider.turn_response().get(
            "cwaIdentityCaptureDiag"
        ) if provider.turn_response() else None
        journal["finishedAt"] = now()
        persist(journal)
        print("=== SUBMIT ERROR - DO NOT RETRY ===")
        print(type(error).__name__)
        print(str(error))
        return 2

    ack_dict = ack.to_dict() if hasattr(ack, "to_dict") else {}
    turn_response = provider.turn_response()
    diag = turn_response.get("cwaIdentityCaptureDiag") if turn_response else None
    writes = (
        diag.get("conversationWriteRequests")
        if isinstance(diag, dict) and isinstance(diag.get("conversationWriteRequests"), list)
        else []
    )

    # Durable ACK/journal persists BEFORE any finality attempt.
    journal["state"] = "WRITE_ACKNOWLEDGED_PRE_CRASH"
    journal["writeAcknowledgedAt"] = now()
    journal["ack"] = ack_dict
    journal["events"] = [
        event for event in events if event.get("type") in KEEP_EVENT_TYPES
    ]
    journal["diagnosticCapture"] = diag
    journal["sseAuthorityFields"] = _authority_fields(turn_response)
    journal["durableWriteCount"] = len(writes)
    journal["submissionCount"] = 1
    journal["crashPlannedAt"] = now()
    persist(journal)

    print("=== DURABLE ACK PERSISTED; HARD CRASH NOW (NO FINALITY, NO RETRY) ===")
    print(json.dumps(ack_dict, ensure_ascii=False, indent=2))
    print(f"durableWriteCount={len(writes)}")
    # Simulate process death after durable ACK, before finality. No cleanup,
    # no await_final, no canonical read, no retry.
    os._exit(75)


def _assistant_messages(messages_result: Any) -> list[dict[str, Any]]:
    items = messages_result if isinstance(messages_result, list) else []
    return [
        item.to_dict() if hasattr(item, "to_dict") else item
        for item in items
        if hasattr(item, "to_dict") or isinstance(item, dict)
    ]


def _reconcile_phase() -> int:
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    recon: dict[str, Any] = {
        "phase": "reconcile",
        "reconcileStartedAt": now(),
        "freshProcess": True,
        "writePerformedByReconciler": False,
    }
    journal["reconciliation"] = recon

    failed: list[str] = []
    if journal.get("state") != "WRITE_ACKNOWLEDGED_PRE_CRASH":
        failed.append(f"durable_state={journal.get('state')}")
    if journal.get("durableWriteCount") != 1:
        failed.append(f"durableWriteCount={journal.get('durableWriteCount')}")
    if journal.get("submissionCount") != 1:
        failed.append(f"submissionCount={journal.get('submissionCount')}")
    ack = journal.get("ack") or {}
    conversation_id = ack.get("conversation_id")
    client_message_id = None
    diag = journal.get("diagnosticCapture") or {}
    for request in diag.get("conversationWriteRequests", []) if isinstance(diag, dict) else []:
        body = request.get("requestBodyIdentity") or {}
        ids = body.get("userMessageIds")
        if body.get("resolved") is True and isinstance(ids, list) and ids:
            client_message_id = ids[0]
    if not conversation_id:
        failed.append("durable_conversation_id_missing")
    if not client_message_id:
        failed.append("durable_client_message_id_missing")
    if failed:
        recon["verdict"] = "RECONCILIATION_FAILED"
        recon["failures"] = failed
        recon["reconcileFinishedAt"] = now()
        persist(journal)
        print("RECONCILIATION_FAILED (durable evidence incomplete)")
        print(json.dumps(failed, indent=2))
        return 4

    authority = journal.get("sseAuthorityFields") or {}
    expected_assistant_message_id = None
    for event in reversed(journal.get("events", [])):
        if event.get("type") == "assistant_text_delta" and event.get("delta") == "_OK":
            expected_assistant_message_id = event.get("message_id")
            break
    if expected_assistant_message_id is None:
        for event in reversed(journal.get("events", [])):
            if event.get("type") in ("assistant_text_snapshot", "assistant_text_delta"):
                expected_assistant_message_id = event.get("message_id")
                break

    runtime = assemble_product_runtime(transport="browser-owned")
    conversation = ConversationRef(conversation_id)

    recon["authorityFields"] = authority
    recon["durableConversationId"] = conversation_id
    recon["durableClientMessageId"] = client_message_id
    recon["durableExpectedAssistantMessageId"] = expected_assistant_message_id

    messages: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, READ_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(READ_WAIT_S[attempt - 1])
        else:
            time.sleep(READ_WAIT_S[0])
        started = now()
        try:
            status = runtime.get_status(conversation)
            status_dict = status.to_dict() if hasattr(status, "to_dict") else status
        except Exception as error:  # noqa: BLE001 - evidence boundary
            status_dict = {"errorType": type(error).__name__, "error": str(error)}
        try:
            messages = _assistant_messages(runtime.get_messages(conversation))
            messages_error = None
        except Exception as error:  # noqa: BLE001 - evidence boundary
            messages = []
            messages_error = f"{type(error).__name__}: {error}"
        matching_users = [
            item for item in messages
            if item.get("role") == "user" and item.get("text") == PROMPT
        ]
        matching_assistants = [
            item for item in messages
            if item.get("role") == "assistant" and item.get("text") == MARKER
        ]
        attempts.append(
            {
                "attempt": attempt,
                "readAt": started,
                "status": status_dict,
                "messageCount": len(messages),
                "matchingUserMessageCount": len(matching_users),
                "matchingUserMessageIds": [
                    item.get("message_id") for item in matching_users
                ],
                "matchingAssistantMessages": [
                    {
                        "message_id": item.get("message_id"),
                        "finish_reason": item.get("finish_reason"),
                        "metadata_preview": item.get("metadata_preview"),
                    }
                    for item in matching_assistants
                ],
                "messagesError": messages_error,
            }
        )
        recon["canonicalReadAttempts"] = attempts
        if status_dict.get("errorType") is None and matching_assistants:
            recovered = matching_assistants[-1]
            finished = (
                recovered.get("finish_reason") == "stop"
                and (recovered.get("metadata_preview") or {}).get("is_complete") is True
            )
            if finished:
                break

    final_attempt = attempts[-1] if attempts else {}
    user_unique = final_attempt.get("matchingUserMessageCount") == 1
    status_dict = final_attempt.get("status") or {}
    recovered = (final_attempt.get("matchingAssistantMessages") or [{}])[-1]
    finality_recovered = bool(
        final_attempt.get("matchingAssistantMessages")
        and recovered.get("finish_reason") == "stop"
        and (recovered.get("metadata_preview") or {}).get("is_complete") is True
    )
    status_match = (
        status_dict.get("ok") is True
        and status_dict.get("result", {}).get("message_id") == client_message_id
    )
    messages_match = client_message_id in (
        final_attempt.get("matchingUserMessageIds") or []
    )
    correlation_ok = status_match or messages_match
    assistant_binding_ok = expected_assistant_message_id is None or (
        recovered.get("message_id") == expected_assistant_message_id
    )
    snapshot = runtime.submission_lifecycle_snapshot()
    no_new_submission = (
        snapshot.get("pending") is False
        and snapshot.get("dispatch_reserved") is False
        and snapshot.get("submission_id") is None
    )

    checks = {
        "write_count_durable_1": journal.get("durableWriteCount") == 1,
        "submission_count_1": journal.get("submissionCount") == 1
        and journal.get("ack", {}).get("submission_id") is not None,
        "recovered_canonical_conversation_matches_durable": bool(messages)
        and status_dict.get("errorType") is None,
        "recovered_canonical_turn_bound": correlation_ok and assistant_binding_ok,
        "finality_recovered": finality_recovered,
        "no_duplicate_write": user_unique,
        "no_new_submission_by_reconciler": no_new_submission,
    }
    recon.update(
        {
            "lifecycleSnapshotFreshProcess": snapshot,
            "checks": checks,
            "verdict": (
                "RECONCILED" if all(checks.values()) else "RECONCILIATION_FAILED"
            ),
            "failures": [k for k, v in checks.items() if not v],
            "reconcileFinishedAt": now(),
        }
    )
    journal["state"] = "RECONCILED" if all(checks.values()) else "RECONCILIATION_FAILED"
    persist(journal)

    print(json.dumps(recon, ensure_ascii=False, indent=2, default=str))
    return 0 if all(checks.values()) else 4


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase == "write":
        return _write_phase()
    if phase == "reconcile":
        return _reconcile_phase()
    print("usage: cwa_reconciliation_probe.py write|reconcile", file=sys.stderr)
    return 64


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - crash journal
        try:
            persist(
                {
                    "schema": 1,
                    "probe": "CWA_CRASH_RESTART_RECONCILIATION",
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
