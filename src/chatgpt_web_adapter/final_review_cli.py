"""CWA final-review transport CLI (the Soc_brain wiring surface).

Subcommands (JSON on stdout, stable exit codes: 0 ok, 4 fail-closed):

- ``submit``: bind + one protected write + canonical recovery of the GPT
  reply. Idempotent per canonical request identity: an existing terminal
  journal returns the stored result with zero writes; a WRITE_ACKNOWLEDGED
  journal continues via reconcile (never a resend); only a fresh identity
  binds and writes.
- ``reconcile``: read-only recovery from the durable journal.

The prompt travels via ``--prompt-file`` (size + shell safety); the journal
stores it verbatim as the committed request text (sanitized by construction:
the caller owns the prompt contents).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from chatgpt_web_adapter import assemble_product_runtime
from chatgpt_web_adapter.final_review_binding_contract import (
    FinalReviewBindingError,
)
from chatgpt_web_adapter.final_review_transport import (
    CwaFinalReviewTransport,
    FinalReviewTransportError,
)


def _transport(args: argparse.Namespace) -> CwaFinalReviewTransport:
    return CwaFinalReviewTransport(
        expected_repository=args.repo,
        expected_issue_number=args.issue,
        expected_pull_request_number=args.pr,
        runtime_factory=assemble_product_runtime,
        durable_store=Path(args.store),
    )


def _emit(payload: dict, code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, default=str))
    return code


def _failure(error: Exception) -> tuple[dict, int]:
    message = str(error)
    reason = message.rsplit(":", 1)[-1] if ":" in message else message
    return {"ok": False, "code": reason, "detail": message}, 4


def cmd_submit(args: argparse.Namespace) -> int:
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    evidence_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    transport = _transport(args)
    try:
        try:
            result = transport.submit_final_review_request(
                prompt=prompt,
                repository=args.repo,
                issue_number=args.issue,
                pull_request_number=args.pr,
                head_sha=args.head_sha,
                evidence_digest=evidence_digest,
                current_head_sha=args.current_head_sha,
            )
        except (FinalReviewTransportError, FinalReviewBindingError) as error:
            message = str(error)
            if message.rsplit(":", 1)[-1] != "REPLAY":
                raise
            # Same identity already bound: continue from durable evidence
            # (terminal journal -> stored result; acknowledged -> reconcile).
            digest = hashlib.sha256(
                json.dumps(
                    {
                        "repository": args.repo,
                        "issueNumber": args.issue,
                        "pullRequestNumber": args.pr,
                        "headSha": args.head_sha,
                        "evidenceDigest": evidence_digest,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            result = transport.reconcile_final_review(digest)
    except (FinalReviewTransportError, FinalReviewBindingError) as error:
        payload, code = _failure(error)
        return _emit(payload, code)
    return _emit({"ok": True, **result.to_dict()}, 0)


def cmd_reconcile(args: argparse.Namespace) -> int:
    transport = _transport(args)
    try:
        result = transport.reconcile_final_review(args.request_id)
    except (FinalReviewTransportError, FinalReviewBindingError) as error:
        payload, code = _failure(error)
        return _emit(payload, code)
    return _emit({"ok": True, **result.to_dict()}, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cwa-final-review")
    sub = parser.add_subparsers(dest="command", required=True)

    submit = sub.add_parser("submit")
    submit.add_argument("--store", required=True)
    submit.add_argument("--prompt-file", required=True)
    submit.add_argument("--repo", required=True)
    submit.add_argument("--issue", type=int, required=True)
    submit.add_argument("--pr", type=int, required=True)
    submit.add_argument("--head-sha", required=True)
    submit.add_argument("--current-head-sha", required=True)
    submit.set_defaults(func=cmd_submit)

    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--store", required=True)
    reconcile.add_argument("--request-id", required=True)
    reconcile.set_defaults(func=cmd_reconcile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
