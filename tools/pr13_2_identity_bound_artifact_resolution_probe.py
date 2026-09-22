from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any, Callable
from urllib.parse import quote

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
else:
    from pr13_1_conversation_files_identity_probe import (
        CHATGPT_ORIGIN,
        _conversation_id,
        _safe_filename,
        probe_conversation_files,
    )
    from pr13_1_conversation_files_live_gate import conversation_id_from_selector
    from pr13_1_conversation_files_stability_gate import _target_record

RESOLUTION_SCHEMA = "CWA_PR13_2_IDENTITY_BOUND_ARTIFACT_RESOLUTION_PROBE_V1"
_RESOLUTION_LOCATOR_KEYS = ("download_url", "url", "href")
_FILENAME_KEYS = ("file_name", "filename", "name")
_SIZE_KEYS = ("file_size_bytes", "size_bytes", "size")


def _git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _safe_size(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _first_safe_filename(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    for key in _FILENAME_KEYS:
        filename = _safe_filename(payload.get(key))
        if filename is not None:
            return key, filename
    return None, None


def _first_safe_size(payload: dict[str, Any]) -> tuple[str | None, int | None]:
    for key in _SIZE_KEYS:
        size = _safe_size(payload.get(key))
        if size is not None:
            return key, size
    return None, None


def summarize_resolution_payload(payload: Any) -> dict[str, Any]:
    """Return locator-free evidence from one file-resolution response payload."""

    if not isinstance(payload, dict):
        return {
            "response_shape": type(payload).__name__,
            "locator_field_present": False,
            "locator_value_exported": False,
            "filename_key": None,
            "filename": None,
            "size_key": None,
            "size_bytes": None,
            "resolution_payload_recognized": False,
        }

    locator_field_present = any(
        isinstance(payload.get(key), str) and bool(payload.get(key).strip())
        for key in _RESOLUTION_LOCATOR_KEYS
    )
    filename_key, filename = _first_safe_filename(payload)
    size_key, size_bytes = _first_safe_size(payload)
    return {
        "response_shape": "dict",
        "locator_field_present": locator_field_present,
        "locator_value_exported": False,
        "filename_key": filename_key,
        "filename": filename,
        "size_key": size_key,
        "size_bytes": size_bytes,
        "resolution_payload_recognized": locator_field_present,
    }


def _negative_control_identity(identity: str) -> str:
    """Produce one deterministic nonmatching opaque identity without exporting it."""

    if not identity:
        raise ValueError("EXPLICIT_FILE_ID_REQUIRED")
    replacement = "0" if identity[-1] != "0" else "1"
    control = f"{identity[:-1]}{replacement}"
    if control == identity:
        raise ValueError("NEGATIVE_CONTROL_IDENTITY_REQUIRED")
    return control


def _resolution_endpoint(conversation_id: str, file_id: str) -> str:
    return (
        f"{CHATGPT_ORIGIN}/backend-api/files/download/{quote(file_id, safe='')}"
        f"?conversation_id={quote(conversation_id, safe='')}&inline=false"
    )


def probe_resolution_request(
    client: Any,
    *,
    conversation_id: str,
    file_id: str,
) -> dict[str, Any]:
    """Perform exactly one authenticated GET against the generated-file resolver."""

    conversation_id = _conversation_id(conversation_id)
    endpoint = _resolution_endpoint(conversation_id, file_id)
    headers = client._build_headers(
        {
            "accept": "application/json",
            "referer": f"{CHATGPT_ORIGIN}/c/{conversation_id}",
        }
    )
    status, payload = client._json_request("GET", endpoint, None, headers)
    report: dict[str, Any] = {
        "method": "GET",
        "request_count": 1,
        "status_code": status,
        "response_body_exported": False,
        "locator_value_exported": False,
        "download_attempted": False,
        "write_attempted": False,
    }
    if status >= 400:
        report.update(
            {
                "response_shape": type(payload).__name__,
                "locator_field_present": False,
                "resolution_payload_recognized": False,
            }
        )
        return report
    report.update(summarize_resolution_payload(payload))
    return report


def characterize_resolution_pair(
    real: dict[str, Any],
    control: dict[str, Any] | None,
) -> dict[str, Any]:
    """Characterize one real-ID resolution and one nonmatching-ID control."""

    real_status = real.get("status_code")
    real_resolved = (
        isinstance(real_status, int)
        and 200 <= real_status < 300
        and real.get("resolution_payload_recognized") is True
        and real.get("locator_field_present") is True
    )
    base: dict[str, Any] = {
        "real_status_code": real_status,
        "real_locator_field_present": real.get("locator_field_present") is True,
        "real_resolution_payload_recognized": real.get("resolution_payload_recognized")
        is True,
        "control_performed": control is not None,
        "control_status_code": None if control is None else control.get("status_code"),
        "control_locator_field_present": False
        if control is None
        else control.get("locator_field_present") is True,
        "identity_bound_resolution_surface_proven": False,
        "stable_product_identity_proven": False,
        "artifact_bytes_proven": False,
        "download_authority_granted": False,
        "download_attempted": False,
        "write_attempted": False,
        "identity_values_exported": False,
        "locator_values_exported": False,
    }

    if not real_resolved:
        base["characterization"] = "REAL_ID_RESOLUTION_NOT_PROVEN"
        return base
    if control is None:
        base["characterization"] = "NEGATIVE_CONTROL_NOT_PERFORMED"
        return base

    control_status = control.get("status_code")
    if not isinstance(control_status, int):
        base["characterization"] = "NEGATIVE_CONTROL_STATUS_UNRECOGNIZED"
        return base
    if 200 <= control_status < 300:
        base["characterization"] = "NEGATIVE_CONTROL_UNEXPECTEDLY_RESOLVED"
        return base
    if control_status >= 500 or control_status == 429:
        base["characterization"] = "NEGATIVE_CONTROL_INCONCLUSIVE"
        return base

    base.update(
        {
            "identity_bound_resolution_surface_proven": True,
            "characterization": "IDENTITY_BOUND_RESOLUTION_SURFACE_OBSERVED",
        }
    )
    return base


def _new_client(timeout: float) -> ChatGPTWebClient:
    return ChatGPTWebClient(
        auto_login=False,
        auto_sentinel=False,
        timeout=timeout,
    )


def run_resolution_gate(
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
        "schema": RESOLUTION_SCHEMA,
        "head": head,
        "expected_head": expected_head,
        "head_matches": head == expected_head,
        "tracked_clean": tracked_clean,
        "expected_filename": filename,
        "request_count": 0,
        "identity_discovery_request_count": 0,
        "resolution_request_count": 0,
        "negative_control_request_count": 0,
        "identity_values_exported": False,
        "locator_values_exported": False,
        "response_body_exported": False,
        "identity_bound_resolution_surface_proven": False,
        "stable_product_identity_proven": False,
        "artifact_bytes_proven": False,
        "download_authority_granted": False,
        "download_attempted": False,
        "write_attempted": False,
    }
    if head != expected_head or not tracked_clean:
        preflight["characterization"] = "EXACT_HEAD_OR_TRACKED_CLEAN_GATE_FAILED"
        return preflight

    client = client_factory(timeout)
    try:
        discovery = probe_conversation_files(client, conversation_id)
    except Exception as exc:
        preflight.update(
            {
                "request_count": 1,
                "identity_discovery_request_count": 1,
                "characterization": "IDENTITY_DISCOVERY_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return preflight

    preflight["request_count"] = 1
    preflight["identity_discovery_request_count"] = 1
    preflight["identity_discovery_characterization"] = discovery.get("characterization")
    target = _target_record(discovery, filename)
    if target is None:
        preflight["characterization"] = "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN"
        return preflight

    file_id = target["explicit_identity"]
    identity_key = target["explicit_identity_key"]
    preflight["identity_key"] = identity_key
    preflight["target_record_present"] = True

    try:
        real = probe_resolution_request(
            client,
            conversation_id=conversation_id,
            file_id=file_id,
        )
    except Exception as exc:
        preflight.update(
            {
                "request_count": 2,
                "resolution_request_count": 1,
                "characterization": "REAL_ID_RESOLUTION_REQUEST_FAILED",
                "error_type": type(exc).__name__,
            }
        )
        return preflight

    preflight["request_count"] = 2
    preflight["resolution_request_count"] = 1
    real_status = real.get("status_code")
    real_resolved = (
        isinstance(real_status, int)
        and 200 <= real_status < 300
        and real.get("resolution_payload_recognized") is True
        and real.get("locator_field_present") is True
    )
    if not real_resolved:
        result = characterize_resolution_pair(real, None)
        result.update(preflight)
        result["characterization"] = "REAL_ID_RESOLUTION_NOT_PROVEN"
        result["real_status_code"] = real_status
        result["real_locator_field_present"] = real.get("locator_field_present") is True
        return result

    control_id = _negative_control_identity(file_id)
    try:
        control = probe_resolution_request(
            client,
            conversation_id=conversation_id,
            file_id=control_id,
        )
    except Exception as exc:
        preflight.update(
            {
                "request_count": 3,
                "resolution_request_count": 1,
                "negative_control_request_count": 1,
                "characterization": "NEGATIVE_CONTROL_REQUEST_FAILED",
                "control_error_type": type(exc).__name__,
            }
        )
        return preflight

    result = characterize_resolution_pair(real, control)
    result.update(
        {
            **preflight,
            "request_count": 3,
            "resolution_request_count": 1,
            "negative_control_request_count": 1,
            "real_status_code": real.get("status_code"),
            "real_locator_field_present": real.get("locator_field_present") is True,
            "real_resolution_payload_recognized": real.get(
                "resolution_payload_recognized"
            )
            is True,
            "real_filename": real.get("filename"),
            "real_size_bytes": real.get("size_bytes"),
            "control_status_code": control.get("status_code"),
            "control_locator_field_present": control.get("locator_field_present")
            is True,
            "identity_bound_resolution_surface_proven": result.get(
                "identity_bound_resolution_surface_proven"
            )
            is True,
            "characterization": result.get("characterization"),
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve one product-owned conversation file_id through the generated-file "
            "resolver and compare it with one nonmatching identity control."
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
        report = run_resolution_gate(
            conversation_id=conversation_id,
            expected_filename=args.expected_filename,
            expected_head=args.expected_head,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    completed = {
        "IDENTITY_BOUND_RESOLUTION_SURFACE_OBSERVED",
        "REAL_ID_RESOLUTION_NOT_PROVEN",
        "NEGATIVE_CONTROL_UNEXPECTEDLY_RESOLVED",
        "NEGATIVE_CONTROL_INCONCLUSIVE",
        "TARGET_EXPLICIT_IDENTITY_NOT_PROVEN",
    }
    return 0 if report.get("characterization") in completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
