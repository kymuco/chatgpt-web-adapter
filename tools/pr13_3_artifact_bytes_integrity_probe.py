from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from typing import Any, Callable
from urllib.parse import urlparse

from chatgpt_web_adapter import ChatGPTWebClient

if __package__:
    from .pr13_1_conversation_files_identity_probe import (
        CHATGPT_ORIGIN,
        _conversation_id,
        _safe_filename,
        probe_conversation_files,
    )
    from .pr13_1_conversation_files_live_gate import conversation_id_from_selector
    from .pr13_1_conversation_files_stability_gate import _target_record
    from .pr13_2_identity_bound_artifact_resolution_probe import _resolution_endpoint
else:
    from pr13_1_conversation_files_identity_probe import (
        CHATGPT_ORIGIN,
        _conversation_id,
        _safe_filename,
        probe_conversation_files,
    )
    from pr13_1_conversation_files_live_gate import conversation_id_from_selector
    from pr13_1_conversation_files_stability_gate import _target_record
    from pr13_2_identity_bound_artifact_resolution_probe import _resolution_endpoint

INTEGRITY_SCHEMA = "CWA_PR13_3_ARTIFACT_BYTES_INTEGRITY_PROBE_V1"
_LOCATOR_KEYS = ("download_url", "url", "href")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_EXPECTED_BYTES = 1024 * 1024


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _normalized_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ValueError("EXPECTED_SHA256_REQUIRED")
    return normalized


def _safe_expected_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("EXPECTED_SIZE_REQUIRED")
    if value < 0 or value > _MAX_EXPECTED_BYTES:
        raise ValueError("EXPECTED_SIZE_OUT_OF_RANGE")
    return value


def _extract_resolution_locator(payload: Any) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None
    for key in _LOCATOR_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return key, value.strip()
    return None, None


def _locator_policy(locator: str) -> dict[str, Any]:
    parsed = urlparse(locator)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        port = -1

    basic_safe = (
        scheme == "https"
        and bool(hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
        and port in {None, 443}
    )
    if not basic_safe:
        return {
            "locator_allowed": False,
            "locator_origin_class": "REJECTED",
            "attach_chatgpt_auth": False,
        }
    if hostname == "chatgpt.com":
        return {
            "locator_allowed": True,
            "locator_origin_class": "CHATGPT_SAME_ORIGIN",
            "attach_chatgpt_auth": True,
        }
    if hostname == "oaiusercontent.com" or hostname.endswith(".oaiusercontent.com"):
        return {
            "locator_allowed": True,
            "locator_origin_class": "OAIUSERCONTENT",
            "attach_chatgpt_auth": False,
        }
    return {
        "locator_allowed": False,
        "locator_origin_class": "UNRECOGNIZED_HTTPS_ORIGIN",
        "attach_chatgpt_auth": False,
    }


def _resolver_payload(
    client: Any,
    *,
    conversation_id: str,
    file_id: str,
) -> tuple[int, Any]:
    endpoint = _resolution_endpoint(conversation_id, file_id)
    headers = client._build_headers(
        {
            "accept": "application/json",
            "referer": f"{CHATGPT_ORIGIN}/c/{conversation_id}",
        }
    )
    return client._json_request("GET", endpoint, None, headers)


def probe_locator_bytes(
    client: Any,
    *,
    conversation_id: str,
    locator: str,
) -> dict[str, Any]:
    """Fetch one approved locator into memory without exporting or persisting bytes."""

    policy = _locator_policy(locator)
    report: dict[str, Any] = {
        **policy,
        "method": "GET",
        "request_count": 0,
        "status_code": None,
        "byte_count": None,
        "sha256": None,
        "bytes_observed": False,
        "bytes_exported": False,
        "response_body_exported": False,
        "locator_value_exported": False,
        "artifact_disk_write_attempted": False,
        "materialization_attempted": False,
        "write_attempted": False,
    }
    if not policy["locator_allowed"]:
        report["characterization"] = "LOCATOR_ORIGIN_REJECTED"
        return report

    if policy["attach_chatgpt_auth"]:
        headers = client._build_headers(
            {
                "accept": "*/*",
                "referer": f"{CHATGPT_ORIGIN}/c/{conversation_id}",
            }
        )
    else:
        headers = {
            "accept": "*/*",
            "user-agent": client.base_headers.get("user-agent", ""),
        }

    status, raw_body, _header_text = client._run_curl(
        "GET",
        locator,
        headers,
        persist_cookies=False,
        follow_redirects=False,
    )
    report["request_count"] = 1
    report["status_code"] = status

    if 300 <= status < 400:
        report["characterization"] = "LOCATOR_REDIRECT_NOT_FOLLOWED"
        return report
    if not 200 <= status < 300:
        report["characterization"] = "LOCATOR_BYTE_FETCH_HTTP_ERROR"
        return report

    report.update(
        {
            "byte_count": len(raw_body),
            "sha256": hashlib.sha256(raw_body).hexdigest(),
            "bytes_observed": True,
            "characterization": "LOCATOR_BYTES_OBSERVED",
        }
    )
    return report


def characterize_integrity(
    byte_report: dict[str, Any],
    *,
    expected_size: int,
    expected_sha256: str,
) -> dict[str, Any]:
    observed_size = byte_report.get("byte_count")
    observed_sha256 = byte_report.get("sha256")
    size_matches = observed_size == expected_size
    sha256_matches = observed_sha256 == expected_sha256
    proven = (
        byte_report.get("bytes_observed") is True and size_matches and sha256_matches
    )
    return {
        "locator_origin_class": byte_report.get("locator_origin_class"),
        "locator_fetch_status_code": byte_report.get("status_code"),
        "observed_size_bytes": observed_size,
        "observed_sha256": observed_sha256,
        "expected_size_bytes": expected_size,
        "expected_sha256": expected_sha256,
        "size_matches": size_matches,
        "sha256_matches": sha256_matches,
        "artifact_bytes_proven": proven,
        "artifact_integrity_proven": proven,
        "identity_bound_byte_retrieval_proven": proven,
        "stable_product_identity_proven": False,
        "download_authority_granted": False,
        "download_attempted": byte_report.get("request_count") == 1,
        "artifact_disk_write_attempted": False,
        "materialization_attempted": False,
        "write_attempted": False,
        "identity_values_exported": False,
        "locator_values_exported": False,
        "artifact_bytes_exported": False,
        "response_body_exported": False,
        "characterization": (
            "IDENTITY_BOUND_ARTIFACT_BYTES_INTEGRITY_OBSERVED"
            if proven
            else "ARTIFACT_BYTES_OR_INTEGRITY_NOT_PROVEN"
        ),
    }


def _new_client(timeout: float) -> ChatGPTWebClient:
    return ChatGPTWebClient(
        auto_login=False,
        auto_sentinel=False,
        timeout=timeout,
    )


def run_integrity_gate(
    *,
    conversation_id: str,
    expected_filename: str,
    expected_size: int,
    expected_sha256: str,
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
    expected_size = _safe_expected_size(expected_size)
    expected_sha256 = _normalized_sha256(expected_sha256)

    head = _git_output("rev-parse", "HEAD")
    tracked_clean = _git_output("status", "--porcelain", "--untracked-files=no") == ""
    report: dict[str, Any] = {
        "schema": INTEGRITY_SCHEMA,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head == expected_head,
        "tracked_clean": tracked_clean,
        "expected_filename": filename,
        "expected_size_bytes": expected_size,
        "expected_sha256": expected_sha256,
        "request_count": 0,
        "identity_discovery_request_count": 0,
        "resolution_request_count": 0,
        "locator_fetch_request_count": 0,
        "identity_values_exported": False,
        "locator_values_exported": False,
        "artifact_bytes_exported": False,
        "response_body_exported": False,
        "artifact_bytes_proven": False,
        "artifact_integrity_proven": False,
        "identity_bound_byte_retrieval_proven": False,
        "stable_product_identity_proven": False,
        "download_authority_granted": False,
        "download_attempted": False,
        "artifact_disk_write_attempted": False,
        "materialization_attempted": False,
        "write_attempted": False,
    }
    if head != expected_head or not tracked_clean:
        report["characterization"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return report

    client = client_factory(timeout)
    try:
        discovery = probe_conversation_files(client, conversation_id)
    except Exception as exc:
        report.update(
            {
                "request_count": 1,
                "identity_discovery_request_count": 1,
                "characterization": "IDENTITY_DISCOVERY_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["request_count"] = 1
    report["identity_discovery_request_count"] = 1
    report["identity_discovery_characterization"] = discovery.get("characterization")
    target = _target_record(discovery, filename)
    if target is None:
        report["characterization"] = "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN"
        return report

    file_id = target["explicit_identity"]
    report["identity_key"] = target["explicit_identity_key"]
    report["target_record_present"] = True

    try:
        resolution_status, resolution_payload = _resolver_payload(
            client,
            conversation_id=conversation_id,
            file_id=file_id,
        )
    except Exception as exc:
        report.update(
            {
                "request_count": 2,
                "resolution_request_count": 1,
                "characterization": "RESOLUTION_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["request_count"] = 2
    report["resolution_request_count"] = 1
    report["resolution_status_code"] = resolution_status
    if not 200 <= resolution_status < 300:
        report["characterization"] = "RESOLUTION_LOCATOR_NOT_PROVEN"
        return report

    locator_key, locator = _extract_resolution_locator(resolution_payload)
    report["resolution_locator_field_present"] = locator is not None
    report["resolution_locator_key"] = locator_key
    if locator is None:
        report["characterization"] = "RESOLUTION_LOCATOR_NOT_PROVEN"
        return report

    try:
        byte_report = probe_locator_bytes(
            client,
            conversation_id=conversation_id,
            locator=locator,
        )
    except Exception as exc:
        report.update(
            {
                "request_count": 3,
                "locator_fetch_request_count": 1,
                "download_attempted": True,
                "characterization": "LOCATOR_BYTE_FETCH_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return report

    report["locator_origin_class"] = byte_report.get("locator_origin_class")
    if byte_report.get("request_count") != 1:
        report["characterization"] = byte_report.get(
            "characterization",
            "LOCATOR_BYTE_FETCH_NOT_PROVEN",
        )
        return report

    integrity = characterize_integrity(
        byte_report,
        expected_size=expected_size,
        expected_sha256=expected_sha256,
    )
    report.update(integrity)
    report["request_count"] = 3
    report["locator_fetch_request_count"] = 1
    report["resolution_locator_field_present"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one product-owned conversation file_id, fetch its approved "
            "locator once into memory, and verify exact byte size plus SHA-256."
        )
    )
    parser.add_argument(
        "--conversation",
        required=True,
        help="Raw conversation id or https://chatgpt.com/.../c/<conversation-id> URL.",
    )
    parser.add_argument("--expected-filename", required=True)
    parser.add_argument("--expected-size", required=True, type=int)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    try:
        conversation_id = conversation_id_from_selector(args.conversation)
        report = run_integrity_gate(
            conversation_id=conversation_id,
            expected_filename=args.expected_filename,
            expected_size=args.expected_size,
            expected_sha256=args.expected_sha256,
            expected_head=args.expected_head,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    completed = {
        "IDENTITY_BOUND_ARTIFACT_BYTES_INTEGRITY_OBSERVED",
        "ARTIFACT_BYTES_OR_INTEGRITY_NOT_PROVEN",
        "RESOLUTION_LOCATOR_NOT_PROVEN",
        "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN",
        "LOCATOR_ORIGIN_REJECTED",
        "LOCATOR_REDIRECT_NOT_FOLLOWED",
        "LOCATOR_BYTE_FETCH_HTTP_ERROR",
    }
    return 0 if report.get("characterization") in completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
