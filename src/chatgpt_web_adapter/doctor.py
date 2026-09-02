from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .artifact_manifest import (
    ARTIFACT_MANIFEST_SCHEMA,
    EXPORT_ARTIFACT_KIND,
    EXPORT_CONTRACT,
    SNAPSHOT_ARTIFACT_KIND,
    SNAPSHOT_CONTRACT,
)
from .auth import DEFAULT_AUTH_FILE
from .auth_status import get_auth_status
from .browser_native_install import (
    EXTENSION_ID,
    _user_native_manifest_path,
    browser_native_extension_dir,
    extension_id_from_public_key,
)
from .browser_native_protocol import HOST_NAME
from .browser_native_provider import BrowserNativeTurnProvider
from .product_runtime import (
    DEFAULT_PRODUCT_TRANSPORT,
    assemble_product_runtime,
)

DOCTOR_SCHEMA = 1
MINIMUM_PYTHON = (3, 10)
_PACKAGE_NAME = "chatgpt-web-adapter"
_REQUIRED_CAPABILITIES: tuple[str, ...] = (
    "text_turns",
    "new_chat",
    "continuation",
    "conversation_read",
    "conversation_status",
    "model_selection",
    "streaming",
    "temporary_chat",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DoctorCheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    section: str
    status: DoctorCheckStatus
    summary: str
    required: bool = True
    evidence: dict[str, Any] | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "section": self.section,
            "status": self.status.value,
            "summary": self.summary,
            "required": self.required,
            "evidence": dict(self.evidence or {}),
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]
    schema: int = DOCTOR_SCHEMA

    @property
    def ok(self) -> bool:
        return not any(
            check.required and check.status is DoctorCheckStatus.FAIL
            for check in self.checks
        )

    @property
    def summary(self) -> dict[str, int]:
        counts = {status.value.lower(): 0 for status in DoctorCheckStatus}
        for check in self.checks:
            counts[check.status.value.lower()] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "command": "doctor",
            "ok": self.ok,
            "summary": self.summary,
            "checks": [check.to_dict() for check in self.checks],
        }


def _pass(
    check_id: str,
    section: str,
    summary: str,
    *,
    required: bool = True,
    evidence: dict[str, Any] | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=check_id,
        section=section,
        status=DoctorCheckStatus.PASS,
        summary=summary,
        required=required,
        evidence=evidence,
    )


def _warn(
    check_id: str,
    section: str,
    summary: str,
    *,
    evidence: dict[str, Any] | None = None,
    remediation: str | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=check_id,
        section=section,
        status=DoctorCheckStatus.WARN,
        summary=summary,
        required=False,
        evidence=evidence,
        remediation=remediation,
    )


def _fail(
    check_id: str,
    section: str,
    summary: str,
    *,
    evidence: dict[str, Any] | None = None,
    remediation: str | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=check_id,
        section=section,
        status=DoctorCheckStatus.FAIL,
        summary=summary,
        required=True,
        evidence=evidence,
        remediation=remediation,
    )


def _skip(check_id: str, section: str, summary: str) -> DoctorCheck:
    return DoctorCheck(
        id=check_id,
        section=section,
        status=DoctorCheckStatus.SKIP,
        summary=summary,
        required=False,
        evidence={},
    )


def _safe_error(error: BaseException) -> dict[str, str]:
    return {"type": type(error).__name__, "message": str(error)}


def _environment_checks() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    version = tuple(sys.version_info[:3])
    evidence = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "minimum": ".".join(str(part) for part in MINIMUM_PYTHON),
    }
    if version >= MINIMUM_PYTHON:
        checks.append(
            _pass(
                "environment.python",
                "environment",
                "Python version satisfies the package requirement",
                evidence=evidence,
            )
        )
    else:
        checks.append(
            _fail(
                "environment.python",
                "environment",
                "Python version is below the supported minimum",
                evidence=evidence,
                remediation="Use Python 3.10 or newer.",
            )
        )

    try:
        package_version = importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        checks.append(
            _warn(
                "environment.package_metadata",
                "environment",
                "Installed package metadata is unavailable",
                evidence={"package": _PACKAGE_NAME},
                remediation="Install the project with `python -m pip install -e .` or from a wheel.",
            )
        )
    else:
        checks.append(
            _pass(
                "environment.package_metadata",
                "environment",
                "Installed package metadata is available",
                required=False,
                evidence={"package": _PACKAGE_NAME, "version": package_version},
            )
        )

    derived_id = extension_id_from_public_key()
    id_evidence = {"configured": EXTENSION_ID, "derived": derived_id}
    if derived_id == EXTENSION_ID:
        checks.append(
            _pass(
                "environment.extension_id_integrity",
                "environment",
                "Packaged extension id matches the frozen public key",
                evidence=id_evidence,
            )
        )
    else:
        checks.append(
            _fail(
                "environment.extension_id_integrity",
                "environment",
                "Packaged extension id does not match the frozen public key",
                evidence=id_evidence,
                remediation="Reinstall a trusted CWA package before using browser-owned writes.",
            )
        )
    return checks


def _auth_checks(
    auth_file: str | Path,
    *,
    profile_dir: str | Path | None,
) -> list[DoctorCheck]:
    try:
        status = get_auth_status(auth_file, profile_dir=profile_dir)
    except Exception as error:
        return [
            _fail(
                "auth.status",
                "auth",
                "Authorization state could not be parsed",
                evidence=_safe_error(error),
                remediation="Run `cwa auth login` to create a fresh authorization file.",
            )
        ]

    evidence = {
        "auth_file": str(status.auth_file.resolve()),
        "file_exists": status.file_exists,
        "access_token_present": status.access_token_present,
        "access_token_expires_at": (
            status.access_token_expires_at.isoformat()
            if status.access_token_expires_at is not None
            else None
        ),
        "access_token_needs_refresh": status.access_token_needs_refresh,
        "session_cookie_present": status.session_cookie_present,
        "browser_cookie_count": status.browser_cookie_count,
        "browser_profile_dir": (
            str(status.browser_profile_dir.resolve())
            if status.browser_profile_dir is not None
            else None
        ),
        "browser_profile_exists": status.browser_profile_exists,
        "auth_source": getattr(status, "auth_source", None),
        "current_chrome_auth": bool(getattr(status, "current_chrome_auth", False)),
    }
    checks: list[DoctorCheck] = []
    if status.file_exists:
        checks.append(
            _pass(
                "auth.file",
                "auth",
                "Authorization file exists",
                evidence={"auth_file": evidence["auth_file"]},
            )
        )
    else:
        checks.append(
            _fail(
                "auth.file",
                "auth",
                "Authorization file is missing",
                evidence={"auth_file": evidence["auth_file"]},
                remediation="Run `cwa auth login`.",
            )
        )
        return checks

    if status.access_token_present or status.session_cookie_present:
        checks.append(
            _pass(
                "auth.material",
                "auth",
                "Reusable authorization material is present",
                evidence={
                    "access_token_present": status.access_token_present,
                    "session_cookie_present": status.session_cookie_present,
                    "browser_cookie_count": status.browser_cookie_count,
                },
            )
        )
    else:
        checks.append(
            _fail(
                "auth.material",
                "auth",
                "Authorization file contains no reusable session material",
                evidence={
                    "access_token_present": False,
                    "session_cookie_present": False,
                    "browser_cookie_count": status.browser_cookie_count,
                },
                remediation="Run `cwa auth login --force`.",
            )
        )

    if status.access_token_present and status.access_token_needs_refresh:
        checks.append(
            _warn(
                "auth.access_token_freshness",
                "auth",
                "Saved access token is due for refresh",
                evidence={
                    "access_token_expires_at": evidence["access_token_expires_at"],
                    "session_cookie_present": status.session_cookie_present,
                },
                remediation="Run `cwa auth refresh` if canonical reads fail or before long unattended use.",
            )
        )
    elif status.access_token_present:
        checks.append(
            _pass(
                "auth.access_token_freshness",
                "auth",
                "Saved access token is not due for refresh",
                required=False,
                evidence={"access_token_expires_at": evidence["access_token_expires_at"]},
            )
        )
    else:
        checks.append(
            _warn(
                "auth.access_token_freshness",
                "auth",
                "No saved access token is present",
                evidence={"session_cookie_present": status.session_cookie_present},
                remediation="Run `cwa auth refresh` or `cwa auth login` if canonical reads are unavailable.",
            )
        )

    if bool(getattr(status, "current_chrome_auth", False)):
        checks.append(
            _pass(
                "auth.browser_profile",
                "auth",
                "Current-Chrome authorization does not require an SDK browser profile",
                required=False,
                evidence={
                    "auth_source": evidence["auth_source"],
                    "current_chrome_auth": True,
                },
            )
        )
    elif status.browser_profile_exists:
        checks.append(
            _pass(
                "auth.browser_profile",
                "auth",
                "Persistent browser profile exists",
                required=False,
                evidence={"browser_profile_dir": evidence["browser_profile_dir"]},
            )
        )
    else:
        checks.append(
            _warn(
                "auth.browser_profile",
                "auth",
                "Persistent browser profile is absent",
                evidence={"browser_profile_dir": evidence["browser_profile_dir"]},
                remediation="Run `cwa auth login` if interactive reauthorization becomes necessary.",
            )
        )
    return checks


def _native_registration_evidence(manifest_path: Path) -> tuple[bool, dict[str, Any]]:
    if os.name != "nt":
        return manifest_path.is_file(), {
            "platform_registration": "manifest-path",
            "registered_path": str(manifest_path.resolve()),
        }

    try:
        import winreg

        key_path = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, None)
        registered = Path(str(value)).expanduser().resolve()
        expected = manifest_path.resolve()
        return registered == expected, {
            "platform_registration": "windows-registry",
            "registered_path": str(registered),
            "expected_path": str(expected),
        }
    except Exception as error:
        return False, {
            "platform_registration": "windows-registry",
            "expected_path": str(manifest_path.resolve()),
            "error": _safe_error(error),
        }


def _install_checks() -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    extension_dir = browser_native_extension_dir()
    extension_manifest = extension_dir / "manifest.json"
    package_evidence = {
        "extension_dir": str(extension_dir.resolve()),
        "manifest": str(extension_manifest.resolve()),
    }
    if extension_dir.is_dir() and extension_manifest.is_file():
        checks.append(
            _pass(
                "install.extension_package",
                "install",
                "Packaged browser extension files are present",
                evidence=package_evidence,
            )
        )
    else:
        checks.append(
            _fail(
                "install.extension_package",
                "install",
                "Packaged browser extension files are incomplete",
                evidence=package_evidence,
                remediation="Reinstall CWA from the expected package or checkout.",
            )
        )

    manifest_path = _user_native_manifest_path()
    if not manifest_path.is_file():
        checks.append(
            _fail(
                "install.native_host_manifest",
                "install",
                "Native Messaging host manifest is missing",
                evidence={"manifest": str(manifest_path.resolve())},
                remediation="Run `cwa browser-native install`.",
            )
        )
    else:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("expected JSON object")
            executable_value = payload.get("path")
            executable = (
                Path(executable_value).expanduser()
                if isinstance(executable_value, str) and executable_value.strip()
                else None
            )
            allowed = payload.get("allowed_origins")
            expected_origin = f"chrome-extension://{EXTENSION_ID}/"
            valid = (
                payload.get("name") == HOST_NAME
                and payload.get("type") == "stdio"
                and isinstance(allowed, list)
                and expected_origin in allowed
                and executable is not None
                and executable.is_file()
            )
            evidence = {
                "manifest": str(manifest_path.resolve()),
                "host_name": payload.get("name"),
                "type": payload.get("type"),
                "expected_origin_present": isinstance(allowed, list) and expected_origin in allowed,
                "host_executable": str(executable.resolve()) if executable is not None else None,
                "host_executable_exists": executable.is_file() if executable is not None else False,
            }
            if valid:
                checks.append(
                    _pass(
                        "install.native_host_manifest",
                        "install",
                        "Native Messaging host manifest is valid",
                        evidence=evidence,
                    )
                )
            else:
                checks.append(
                    _fail(
                        "install.native_host_manifest",
                        "install",
                        "Native Messaging host manifest is incomplete or stale",
                        evidence=evidence,
                        remediation="Run `cwa browser-native install`.",
                    )
                )
        except Exception as error:
            checks.append(
                _fail(
                    "install.native_host_manifest",
                    "install",
                    "Native Messaging host manifest could not be validated",
                    evidence={
                        "manifest": str(manifest_path.resolve()),
                        "error": _safe_error(error),
                    },
                    remediation="Run `cwa browser-native install`.",
                )
            )

    registered, registration_evidence = _native_registration_evidence(manifest_path)
    if registered:
        checks.append(
            _pass(
                "install.native_host_registration",
                "install",
                "Native Messaging host is registered for the current user",
                evidence=registration_evidence,
            )
        )
    else:
        checks.append(
            _fail(
                "install.native_host_registration",
                "install",
                "Native Messaging host registration is missing or stale",
                evidence=registration_evidence,
                remediation="Run `cwa browser-native install`.",
            )
        )
    return checks


def _bridge_checks() -> list[DoctorCheck]:
    try:
        status = BrowserNativeTurnProvider().status()
    except Exception as error:
        return [
            _fail(
                "bridge.available",
                "bridge",
                "Browser-native bridge status check failed",
                evidence=_safe_error(error),
                remediation="Verify the Native Messaging host and reload the unpacked CWA extension.",
            )
        ]

    evidence = {
        "available": status.available,
        "extension_connected": status.extension_connected,
        "host_pid": status.host_pid,
        "extension_id": status.extension_id,
        "runtime_tab_id": status.runtime_tab_id,
    }
    checks: list[DoctorCheck] = []
    if status.available:
        checks.append(
            _pass(
                "bridge.available",
                "bridge",
                "Native Messaging bridge is reachable",
                evidence=evidence,
            )
        )
    else:
        checks.append(
            _fail(
                "bridge.available",
                "bridge",
                "Native Messaging bridge is unavailable",
                evidence=evidence,
                remediation="Load/reload the CWA extension and verify `cwa browser-native install`.",
            )
        )

    if status.extension_connected:
        checks.append(
            _pass(
                "bridge.extension_connected",
                "bridge",
                "Browser extension is connected to the native host",
                evidence={
                    "extension_id": status.extension_id,
                    "runtime_tab_id": status.runtime_tab_id,
                },
            )
        )
    else:
        checks.append(
            _fail(
                "bridge.extension_connected",
                "bridge",
                "Browser extension is not connected to the native host",
                evidence={"extension_id": status.extension_id},
                remediation="Open `chrome://extensions`, load/reload the packaged CWA extension, and retry.",
            )
        )
    return checks


def _runtime_checks(
    *,
    transport: str,
    auth_file: str | Path,
    conversation: str | None,
) -> list[DoctorCheck]:
    try:
        runtime = assemble_product_runtime(
            transport=transport,
            auth_file=auth_file,
        )
    except Exception as error:
        return [
            _fail(
                "runtime.assembly",
                "runtime",
                "Product runtime could not be assembled",
                evidence=_safe_error(error),
                remediation="Resolve the preceding auth/install/bridge failures and retry.",
            )
        ]

    checks: list[DoctorCheck] = []
    try:
        health = runtime.health(conversation)
    except Exception as error:
        checks.append(
            _fail(
                "runtime.health",
                "runtime",
                "Product runtime health check failed",
                evidence=_safe_error(error),
                remediation="Run `cwa status --json` for the selected transport and resolve its reported failure.",
            )
        )
    else:
        health_payload = health.to_dict()
        if health.ready:
            checks.append(
                _pass(
                    "runtime.health",
                    "runtime",
                    "Product runtime is ready",
                    evidence=health_payload,
                )
            )
        else:
            checks.append(
                _fail(
                    "runtime.health",
                    "runtime",
                    "Product runtime is not ready",
                    evidence=health_payload,
                    remediation="Run `cwa status --json` and resolve the reported readiness reason.",
                )
            )

        safety_ok = (
            health.automatic_write_retry is False
            and health.fallback_transport is None
        )
        if safety_ok:
            checks.append(
                _pass(
                    "runtime.fail_closed_policy",
                    "runtime",
                    "Runtime retains no automatic write retry or fallback transport",
                    evidence={
                        "automatic_write_retry": health.automatic_write_retry,
                        "fallback_transport": health.fallback_transport,
                    },
                )
            )
        else:
            checks.append(
                _fail(
                    "runtime.fail_closed_policy",
                    "runtime",
                    "Runtime fail-closed retry/fallback policy is not satisfied",
                    evidence={
                        "automatic_write_retry": health.automatic_write_retry,
                        "fallback_transport": health.fallback_transport,
                    },
                    remediation="Do not use product writes until the transport governance mismatch is resolved.",
                )
            )

    try:
        capabilities = runtime.capabilities().to_dict()
        entries = capabilities.get("capabilities", {})
        states = {
            name: (
                entries.get(name, {}).get("state")
                if isinstance(entries.get(name), dict)
                else None
            )
            for name in _REQUIRED_CAPABILITIES
        }
        unavailable = sorted(
            name for name, state in states.items() if state != "AVAILABLE"
        )
        evidence = {
            "required": list(_REQUIRED_CAPABILITIES),
            "states": states,
            "unavailable": unavailable,
        }
        if not unavailable:
            checks.append(
                _pass(
                    "runtime.required_capabilities",
                    "runtime",
                    "Required CWA 0.2 product capabilities are available",
                    evidence=evidence,
                )
            )
        else:
            checks.append(
                _fail(
                    "runtime.required_capabilities",
                    "runtime",
                    "One or more required product capabilities are unavailable",
                    evidence=evidence,
                    remediation="Run `cwa capabilities --json` and verify the installed CWA revision.",
                )
            )
    except Exception as error:
        checks.append(
            _fail(
                "runtime.required_capabilities",
                "runtime",
                "Product capability inspection failed",
                evidence=_safe_error(error),
                remediation="Run `cwa capabilities --json` and resolve the reported error.",
            )
        )
    return checks


def verify_artifact_manifest(path: str | Path) -> DoctorCheck:
    manifest_path = Path(path)
    check_id = f"artifact.{manifest_path.name}"
    if not manifest_path.is_file():
        return _fail(
            check_id,
            "artifact",
            "Artifact manifest does not exist",
            evidence={"manifest": str(manifest_path.resolve())},
            remediation="Pass an existing PR8.15 `.manifest.json` file.",
        )

    errors: list[str] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as error:
        return _fail(
            check_id,
            "artifact",
            "Artifact manifest is not valid JSON",
            evidence={
                "manifest": str(manifest_path.resolve()),
                "error": _safe_error(error),
            },
            remediation="Regenerate the artifact with CWA instead of editing the manifest in place.",
        )

    if not isinstance(payload, dict):
        errors.append("manifest root must be an object")
        payload = {}

    schema = payload.get("schema")
    artifact_kind = payload.get("artifact_kind")
    contract = payload.get("contract")
    conversation_id = payload.get("conversation_id")
    index = payload.get("index")
    artifact_format = payload.get("format")
    files = payload.get("files")

    if schema != ARTIFACT_MANIFEST_SCHEMA:
        errors.append(f"unsupported schema: {schema!r}")
    expected_contract = {
        SNAPSHOT_ARTIFACT_KIND: SNAPSHOT_CONTRACT,
        EXPORT_ARTIFACT_KIND: EXPORT_CONTRACT,
    }.get(artifact_kind)
    if expected_contract is None:
        errors.append(f"unsupported artifact_kind: {artifact_kind!r}")
    elif contract != expected_contract:
        errors.append(
            f"contract mismatch for {artifact_kind}: {contract!r} != {expected_contract!r}"
        )
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        errors.append("conversation_id is required")
    if isinstance(index, bool) or not isinstance(index, int) or index <= 0:
        errors.append("index must be a positive integer")
    if artifact_kind == EXPORT_ARTIFACT_KIND and artifact_format not in {
        "markdown",
        "jsonl",
        "txt",
    }:
        errors.append(f"unsupported export format: {artifact_format!r}")
    if artifact_kind == SNAPSHOT_ARTIFACT_KIND and artifact_format is not None:
        errors.append("snapshot format must be null")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
        files = []

    verified_files: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    for position, entry in enumerate(files):
        if not isinstance(entry, dict):
            errors.append(f"files[{position}] must be an object")
            continue
        role = entry.get("role")
        relative = entry.get("path")
        media_type = entry.get("media_type")
        expected_bytes = entry.get("bytes")
        expected_sha = entry.get("sha256")
        prefix = f"files[{position}]"

        if not isinstance(role, str) or not role:
            errors.append(f"{prefix}.role is required")
        elif role in seen_roles:
            errors.append(f"duplicate file role: {role}")
        else:
            seen_roles.add(role)
        if not isinstance(relative, str) or not relative:
            errors.append(f"{prefix}.path is required")
            continue
        relative_path = Path(relative)
        if relative_path.name != relative or relative_path.is_absolute():
            errors.append(f"{prefix}.path must be a manifest-relative basename")
            continue
        if relative == manifest_path.name:
            errors.append(f"{prefix}.path must not reference the manifest itself")
            continue
        if not isinstance(media_type, str) or not media_type:
            errors.append(f"{prefix}.media_type is required")
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int) or expected_bytes < 0:
            errors.append(f"{prefix}.bytes must be a non-negative integer")
            continue
        if not isinstance(expected_sha, str) or _SHA256_RE.fullmatch(expected_sha) is None:
            errors.append(f"{prefix}.sha256 must be a lowercase SHA-256 digest")
            continue

        file_path = manifest_path.parent / relative
        if not file_path.is_file():
            errors.append(f"missing artifact file: {relative}")
            continue
        raw = file_path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        actual_bytes = len(raw)
        if actual_bytes != expected_bytes:
            errors.append(
                f"byte-count mismatch for {relative}: {actual_bytes} != {expected_bytes}"
            )
        if actual_sha != expected_sha:
            errors.append(f"sha256 mismatch for {relative}")
        verified_files.append(
            {
                "role": role,
                "path": relative,
                "bytes": actual_bytes,
                "sha256": actual_sha,
            }
        )

    if artifact_kind == EXPORT_ARTIFACT_KIND and seen_roles != {"export"}:
        errors.append("conversation_export must contain exactly the `export` role")
    if artifact_kind == SNAPSHOT_ARTIFACT_KIND:
        if "context" not in seen_roles:
            errors.append("conversation_snapshot must contain the `context` role")
        if not seen_roles.issubset({"context", "raw_payload"}):
            errors.append("conversation_snapshot contains an unsupported file role")

    evidence = {
        "manifest": str(manifest_path.resolve()),
        "schema": schema,
        "artifact_kind": artifact_kind,
        "contract": contract,
        "conversation_id": conversation_id,
        "index": index,
        "format": artifact_format,
        "files_verified": verified_files,
        "errors": errors,
    }
    if errors:
        return _fail(
            check_id,
            "artifact",
            "Artifact manifest or emitted bytes failed verification",
            evidence=evidence,
            remediation="Regenerate the artifact from canonical state; do not trust the current bundle.",
        )
    return _pass(
        check_id,
        "artifact",
        "Artifact manifest and emitted bytes are internally consistent",
        evidence=evidence,
    )


def run_doctor(
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    profile_dir: str | Path | None = None,
    transport: str = DEFAULT_PRODUCT_TRANSPORT,
    conversation: str | None = None,
    artifacts: Iterable[str | Path] = (),
) -> DoctorReport:
    """Run read-only CWA environment, bridge, runtime, and artifact diagnostics."""

    checks: list[DoctorCheck] = []
    checks.extend(_environment_checks())
    checks.extend(_auth_checks(auth_file, profile_dir=profile_dir))
    checks.extend(_install_checks())
    checks.extend(_bridge_checks())
    checks.extend(
        _runtime_checks(
            transport=transport,
            auth_file=auth_file,
            conversation=conversation,
        )
    )

    artifact_paths = tuple(artifacts)
    if artifact_paths:
        checks.extend(verify_artifact_manifest(path) for path in artifact_paths)
    else:
        checks.append(
            _skip(
                "artifact.manifest",
                "artifact",
                "No artifact manifest was requested for verification",
            )
        )
    return DoctorReport(tuple(checks))
