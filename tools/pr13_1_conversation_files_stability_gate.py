from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from typing import Any, Callable

from chatgpt_web_adapter import ChatGPTWebClient

if __package__:
    from .pr13_1_conversation_files_identity_probe import (
        _conversation_id,
        _safe_filename,
        probe_conversation_files,
    )
    from .pr13_1_conversation_files_live_gate import conversation_id_from_selector
else:
    from pr13_1_conversation_files_identity_probe import (
        _conversation_id,
        _safe_filename,
        probe_conversation_files,
    )
    from pr13_1_conversation_files_live_gate import conversation_id_from_selector

STABILITY_SCHEMA = "CWA_PR13_1_CONVERSATION_FILES_STABILITY_GATE_V1"


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _identity_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _target_record(
    report: dict[str, Any], expected_filename: str
) -> dict[str, Any] | None:
    records = report.get("records")
    if not isinstance(records, list):
        return None
    matches = [
        record
        for record in records
        if isinstance(record, dict) and record.get("filename") == expected_filename
    ]
    if len(matches) != 1:
        return None
    record = matches[0]
    identity = record.get("explicit_identity")
    identity_key = record.get("explicit_identity_key")
    if not isinstance(identity, str) or not identity:
        return None
    if not isinstance(identity_key, str) or not identity_key:
        return None
    return record


def characterize_independent_reads(
    first: dict[str, Any],
    second: dict[str, Any],
    *,
    expected_filename: str,
) -> dict[str, Any]:
    """Compare one exact generated-file target across two sanitized read reports."""

    first_record = _target_record(first, expected_filename)
    second_record = _target_record(second, expected_filename)
    base: dict[str, Any] = {
        "schema": STABILITY_SCHEMA,
        "request_count": 2,
        "fresh_client_count": 2,
        "expected_filename": expected_filename,
        "first_characterization": first.get("characterization"),
        "second_characterization": second.get("characterization"),
        "first_target_record_present": first_record is not None,
        "second_target_record_present": second_record is not None,
        "same_explicit_identity": False,
        "same_identity_key": False,
        "short_term_identity_stability_proven": False,
        "stable_product_identity_proven": False,
        "resolution_surface_proven": False,
        "download_authority_granted": False,
        "download_attempted": False,
        "write_attempted": False,
        "identity_values_exported": False,
    }

    if first_record is None:
        base["characterization"] = "FIRST_READ_TARGET_IDENTITY_NOT_PROVEN"
        return base
    if second_record is None:
        base["characterization"] = "SECOND_READ_TARGET_IDENTITY_NOT_PROVEN"
        return base

    first_identity = first_record["explicit_identity"]
    second_identity = second_record["explicit_identity"]
    first_key = first_record["explicit_identity_key"]
    second_key = second_record["explicit_identity_key"]
    same_identity = first_identity == second_identity
    same_key = first_key == second_key

    base.update(
        {
            "first_identity_key": first_key,
            "second_identity_key": second_key,
            "first_identity_fingerprint": _identity_fingerprint(first_identity),
            "second_identity_fingerprint": _identity_fingerprint(second_identity),
            "same_explicit_identity": same_identity,
            "same_identity_key": same_key,
            "short_term_identity_stability_proven": same_identity and same_key,
            "characterization": (
                "SAME_EXPLICIT_IDENTITY_ACROSS_INDEPENDENT_READS"
                if same_identity and same_key
                else "EXPLICIT_IDENTITY_CHANGED_ACROSS_INDEPENDENT_READS"
            ),
        }
    )
    return base


def _new_client(timeout: float) -> ChatGPTWebClient:
    return ChatGPTWebClient(
        auto_login=False,
        auto_sentinel=False,
        timeout=timeout,
    )


def run_stability_gate(
    *,
    conversation_id: str,
    expected_filename: str,
    expected_head: str,
    timeout: float,
    client_factory: Callable[[float], Any] = _new_client,
) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    conversation_id = _conversation_id(conversation_id)
    filename = _safe_filename(expected_filename)
    if filename is None:
        raise ValueError("EXPECTED_FILENAME_REQUIRED")

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _git_output("status", "--porcelain", "--untracked-files=no") == ""
    preflight: dict[str, Any] = {
        "schema": STABILITY_SCHEMA,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head == expected_head,
        "tracked_clean": tracked_clean,
        "request_count": 0,
        "fresh_client_count": 0,
        "expected_filename": filename,
        "short_term_identity_stability_proven": False,
        "stable_product_identity_proven": False,
        "resolution_surface_proven": False,
        "download_authority_granted": False,
        "download_attempted": False,
        "write_attempted": False,
        "identity_values_exported": False,
    }
    if head != expected_head or not tracked_clean:
        preflight["characterization"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return preflight

    try:
        first_client = client_factory(timeout)
        first = probe_conversation_files(first_client, conversation_id)
    except Exception as exc:
        preflight.update(
            {
                "request_count": 1,
                "fresh_client_count": 1,
                "characterization": "FIRST_READ_FAILED",
                "first_error_type": type(exc).__name__,
            }
        )
        return preflight

    try:
        second_client = client_factory(timeout)
        second = probe_conversation_files(second_client, conversation_id)
    except Exception as exc:
        preflight.update(
            {
                "request_count": 2,
                "fresh_client_count": 2,
                "first_characterization": first.get("characterization"),
                "characterization": "SECOND_READ_FAILED",
                "second_error_type": type(exc).__name__,
            }
        )
        return preflight

    result = characterize_independent_reads(
        first,
        second,
        expected_filename=filename,
    )
    result.update(
        {
            "head": head,
            "expected_head": expected_head,
            "head_matches": True,
            "tracked_clean": True,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Perform two independent read-only authenticated conversation-files reads "
            "through fresh clients and compare one filename-anchored explicit identity."
        )
    )
    parser.add_argument(
        "--conversation",
        required=True,
        help="Raw conversation id or https://chatgpt.com/.../c/<conversation-id> URL.",
    )
    parser.add_argument("--expected-filename", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    try:
        conversation_id = conversation_id_from_selector(args.conversation)
        report = run_stability_gate(
            conversation_id=conversation_id,
            expected_filename=args.expected_filename,
            expected_head=args.expected_head,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return (
        0
        if report.get("characterization")
        == "SAME_EXPLICIT_IDENTITY_ACROSS_INDEPENDENT_READS"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
