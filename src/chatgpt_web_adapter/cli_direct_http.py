"""Explicit Direct HTTP path for the installed cwa send entrypoint.

This is not the historical product-runtime browserless-request transport.
No implicit browser fallback, write retries, or canonical finality claims.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

from .browserless_http import BrowserlessHTTPClient
from .exceptions import RequestError

DIRECT_HTTP_TRANSPORT = "direct-http"


class DirectHTTPReconciliationRequired(RequestError):
    """A Direct HTTP send attempt ended without known product finality.

    This is deliberately conservative: a timeout may happen before or after
    conversation admission, and the CLI cannot prove which without readback.
    """

    reconciliation_required = True
    write_may_have_been_submitted = True


_PROFILE_REQUESTS: dict[str, tuple[str, str | None]] = {
    "FAST": ("gpt-6-instant", None),
    "BALANCED": ("gpt-6", "medium"),
    "DEEP": ("gpt-6", "high"),
}


def _direct_http_payload(response: Any) -> dict[str, Any]:
    """Preserve CLI fields without fabricating product-runtime provenance."""
    return {
        "transport": DIRECT_HTTP_TRANSPORT,
        "ok": True,
        "text": response.text,
        "title": response.title,
        "conversation_id": response.conversation.conversation_id,
        "message_id": response.conversation.message_id,
        "finish_reason": response.conversation.finish_reason,
        "observed_model": response.request.observed_model,
        "temporary": response.request.temporary,
        "backend_status": response.metrics.backend_status,
        "runtime_observation": None,
        "provenance": None,
    }


def send_direct_http(args: Any) -> int:
    """One user-authorized SDK send; never replay an uncertain write."""
    if args.temporary and args.conversation:
        raise ValueError("--temporary cannot be combined with --conversation")
    if args.timings:
        raise ValueError(
            "--timings is browser-owned only; not available for direct-http"
        )
    if args.final_only and not args.stream:
        raise ValueError("--final-only requires --stream")
    if args.poll_interval != 0.5:
        raise ValueError("--poll-interval applies only to browser-owned transport")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("--timeout must be a finite positive number")
    if not args.text.strip():
        raise ValueError("text must be nonempty")

    media: list[Path] = []
    for item in args.files:
        file = Path(item)
        if not file.is_file():
            raise ValueError(f"--file must name an existing regular file: {file}")
        media.append(file)

    model, reasoning_effort = _PROFILE_REQUESTS[args.profile]
    if args.model:
        model = args.model

    client = BrowserlessHTTPClient(
        auth_file=args.auth_file,
        timeout=math.ceil(args.timeout),
    )
    chunks: list[str] = []

    def on_token(token: str) -> None:
        if not token:
            return
        chunks.append(token)
        sys.stdout.write(token)
        sys.stdout.flush()

    try:
        response = client.send(
            args.text,
            model=model,
            reasoning_effort=reasoning_effort,
            conversation=args.conversation,
            temporary=args.temporary,
            media=media or None,
            on_token=on_token if args.stream and not args.final_only else None,
        )
    except RequestError as error:
        # Some SSE curl failures arrive from the inherited stream reader as
        # unstructured "curl failed: ..." transport errors. A stream can fail
        # after ChatGPT has admitted the message, even without an HTTP status.
        # Likewise, a nonzero curl exit after HTTP 200 does not prove the
        # response body or conversation outcome was received completely.
        stream_curl_failure = (
            error.request_stage == "transport"
            and error.endpoint is None
            and str(error).startswith("curl failed:")
        )
        accepted_headers_partial = (
            error.request_stage == "transport" and error.status_code == 200
        )
        if not (
            error.request_stage == "transport_timeout"
            or accepted_headers_partial
            or stream_curl_failure
        ):
            raise
        raise DirectHTTPReconciliationRequired(
            "Direct HTTP send outcome unknown after transport failure; "
            "inspect canonical conversation history before any new send",
            status_code=error.status_code,
            request_stage=error.request_stage,
            endpoint="conversation_write" if stream_curl_failure else error.endpoint,
        ) from error

    if args.json:
        print(json.dumps(_direct_http_payload(response), indent=2, ensure_ascii=False))
    elif args.stream and not args.final_only and chunks:
        # Stream chunks are provisional; the send return is the SDK's final text.
        streamed = "".join(chunks)
        if streamed != response.text:
            sys.stdout.write("\n[final response]\n" + (response.text or "") + "\n")
        elif not streamed.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        print(response.text or "")
    return 0
