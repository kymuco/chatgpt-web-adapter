from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import chatgpt_web_adapter.cli_v02 as cli
import chatgpt_web_adapter.doctor as doctor
from chatgpt_web_adapter.doctor import (
    DoctorCheck,
    DoctorCheckStatus,
    DoctorReport,
    run_doctor,
    verify_artifact_manifest,
)


def _check(
    check_id: str,
    status: DoctorCheckStatus,
    *,
    required: bool = True,
    remediation: str | None = None,
) -> DoctorCheck:
    return DoctorCheck(
        id=check_id,
        section="test",
        status=status,
        summary=check_id,
        required=required,
        evidence={"marker": check_id},
        remediation=remediation,
    )


def _write_manifest(tmp_path: Path, payload: dict, name: str = "artifact.manifest.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def _export_manifest(file_name: str, raw: bytes) -> dict:
    return {
        "schema": 1,
        "artifact_kind": "conversation_export",
        "contract": "normalized_current_branch_export_v1",
        "conversation_id": "conversation-1",
        "index": 1,
        "format": "jsonl",
        "files": [
            {
                "role": "export",
                "path": file_name,
                "media_type": "application/x-ndjson; charset=utf-8",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
    }


def test_doctor_report_warn_and_skip_do_not_fail() -> None:
    report = DoctorReport(
        (
            _check("pass", DoctorCheckStatus.PASS),
            _check("warn", DoctorCheckStatus.WARN, required=False),
            _check("skip", DoctorCheckStatus.SKIP, required=False),
        )
    )

    assert report.ok is True
    assert report.summary == {"pass": 1, "warn": 1, "fail": 0, "skip": 1}
    payload = report.to_dict()
    assert payload["schema"] == 1
    assert payload["command"] == "doctor"
    assert payload["ok"] is True


def test_doctor_report_required_fail_is_not_ok() -> None:
    report = DoctorReport((_check("failure", DoctorCheckStatus.FAIL),))

    assert report.ok is False
    assert report.summary["fail"] == 1


def test_verify_export_manifest_checks_exact_bytes(tmp_path: Path) -> None:
    raw = b'{"role":"user","text":"hello"}\n'
    export = tmp_path / "project_chat_export_1.jsonl"
    export.write_bytes(raw)
    manifest = _write_manifest(tmp_path, _export_manifest(export.name, raw))

    check = verify_artifact_manifest(manifest)

    assert check.status is DoctorCheckStatus.PASS
    assert check.evidence["artifact_kind"] == "conversation_export"
    assert check.evidence["files_verified"] == [
        {
            "role": "export",
            "path": export.name,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    ]


def test_verify_context_only_snapshot_manifest(tmp_path: Path) -> None:
    raw = b"## USER\n\nHello\n"
    context = tmp_path / "project_chat_context_1.md"
    context.write_bytes(raw)
    manifest = _write_manifest(
        tmp_path,
        {
            "schema": 1,
            "artifact_kind": "conversation_snapshot",
            "contract": "curated_current_branch_context_v1",
            "conversation_id": "conversation-1",
            "index": 1,
            "format": None,
            "files": [
                {
                    "role": "context",
                    "path": context.name,
                    "media_type": "text/markdown; charset=utf-8",
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            ],
        },
        "project_chat_snapshot_1.manifest.json",
    )

    check = verify_artifact_manifest(manifest)

    assert check.status is DoctorCheckStatus.PASS
    assert check.evidence["format"] is None


def test_verify_artifact_detects_hash_mismatch(tmp_path: Path) -> None:
    original = b"original\n"
    export = tmp_path / "project_chat_export_1.jsonl"
    export.write_bytes(b"changed\n")
    manifest = _write_manifest(tmp_path, _export_manifest(export.name, original))

    check = verify_artifact_manifest(manifest)

    assert check.status is DoctorCheckStatus.FAIL
    assert any("sha256 mismatch" in error for error in check.evidence["errors"])


def test_verify_artifact_rejects_parent_path(tmp_path: Path) -> None:
    raw = b"outside\n"
    outside = tmp_path.parent / "escape.jsonl"
    outside.write_bytes(raw)
    payload = _export_manifest("../escape.jsonl", raw)
    manifest = _write_manifest(tmp_path, payload)

    check = verify_artifact_manifest(manifest)

    assert check.status is DoctorCheckStatus.FAIL
    assert any("manifest-relative basename" in error for error in check.evidence["errors"])


def test_verify_artifact_rejects_wrong_contract(tmp_path: Path) -> None:
    raw = b"{}\n"
    export = tmp_path / "project_chat_export_1.jsonl"
    export.write_bytes(raw)
    payload = _export_manifest(export.name, raw)
    payload["contract"] = "wrong_v1"
    manifest = _write_manifest(tmp_path, payload)

    check = verify_artifact_manifest(manifest)

    assert check.status is DoctorCheckStatus.FAIL
    assert any("contract mismatch" in error for error in check.evidence["errors"])


def test_auth_checks_never_export_token_or_cookie_values(monkeypatch, tmp_path: Path) -> None:
    auth_file = tmp_path / "auth.json"
    auth_file.write_text("{}", encoding="utf-8")
    profile = tmp_path / "profile"
    profile.mkdir()
    monkeypatch.setattr(
        doctor,
        "get_auth_status",
        lambda *args, **kwargs: SimpleNamespace(
            auth_file=auth_file,
            file_exists=True,
            access_token_present=True,
            access_token_expires_at=None,
            access_token_needs_refresh=False,
            session_cookie_present=True,
            session_expires_at=None,
            browser_cookie_count=3,
            browser_profile_dir=profile,
            browser_profile_exists=True,
        ),
    )

    payload = json.dumps([check.to_dict() for check in doctor._auth_checks(auth_file, profile_dir=profile)])

    assert "access_token" not in payload.lower() or "access_token_present" in payload
    assert "session_cookie_present" in payload
    assert "secret-token-value" not in payload
    assert "cookie-value" not in payload


def test_install_checks_validate_packaged_extension_and_host(monkeypatch, tmp_path: Path) -> None:
    extension_dir = tmp_path / "extension"
    extension_dir.mkdir()
    (extension_dir / "manifest.json").write_text("{}", encoding="utf-8")
    executable = tmp_path / "chatgpt-web-adapter-native-host.exe"
    executable.write_bytes(b"host")
    host_manifest = tmp_path / "native-host.json"
    host_manifest.write_text(
        json.dumps(
            {
                "name": doctor.HOST_NAME,
                "path": str(executable),
                "type": "stdio",
                "allowed_origins": [f"chrome-extension://{doctor.EXTENSION_ID}/"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(doctor, "browser_native_extension_dir", lambda: extension_dir)
    monkeypatch.setattr(doctor, "_user_native_manifest_path", lambda: host_manifest)
    monkeypatch.setattr(
        doctor,
        "_native_registration_evidence",
        lambda path: (True, {"registered_path": str(path)}),
    )

    checks = doctor._install_checks()

    assert [check.status for check in checks] == [
        DoctorCheckStatus.PASS,
        DoctorCheckStatus.PASS,
        DoctorCheckStatus.PASS,
    ]


def test_bridge_checks_do_not_perform_turn(monkeypatch) -> None:
    class Provider:
        def status(self):
            return SimpleNamespace(
                available=True,
                extension_connected=True,
                host_pid=42,
                extension_id=doctor.EXTENSION_ID,
                runtime_tab_id=None,
            )

        def send_text(self, *args, **kwargs):
            raise AssertionError("doctor must not perform a product turn")

    monkeypatch.setattr(doctor, "BrowserNativeTurnProvider", Provider)

    checks = doctor._bridge_checks()

    assert [check.status for check in checks] == [
        DoctorCheckStatus.PASS,
        DoctorCheckStatus.PASS,
    ]


def test_runtime_checks_use_health_and_capabilities_only(monkeypatch) -> None:
    required = {
        name: {"state": "AVAILABLE"}
        for name in doctor._REQUIRED_CAPABILITIES
    }

    class Runtime:
        def health(self, conversation):
            assert conversation == "conversation-1"
            return SimpleNamespace(
                ready=True,
                automatic_write_retry=False,
                fallback_transport=None,
                to_dict=lambda: {
                    "ready": True,
                    "automatic_write_retry": False,
                    "fallback_transport": None,
                },
            )

        def capabilities(self):
            return SimpleNamespace(
                to_dict=lambda: {"capabilities": required}
            )

        def send_text(self, *args, **kwargs):
            raise AssertionError("doctor must not send")

        send = send_text
        send_text_observed = send_text

    monkeypatch.setattr(doctor, "assemble_product_runtime", lambda **kwargs: Runtime())

    checks = doctor._runtime_checks(
        transport="browser-owned",
        auth_file="auth.json",
        conversation="conversation-1",
    )

    assert [check.id for check in checks] == [
        "runtime.health",
        "runtime.fail_closed_policy",
        "runtime.required_capabilities",
    ]
    assert all(check.status is DoctorCheckStatus.PASS for check in checks)


def test_runtime_checks_fail_on_retry_or_fallback(monkeypatch) -> None:
    required = {
        name: {"state": "AVAILABLE"}
        for name in doctor._REQUIRED_CAPABILITIES
    }
    runtime = SimpleNamespace(
        health=lambda conversation: SimpleNamespace(
            ready=True,
            automatic_write_retry=True,
            fallback_transport="other",
            to_dict=lambda: {"ready": True},
        ),
        capabilities=lambda: SimpleNamespace(
            to_dict=lambda: {"capabilities": required}
        ),
    )
    monkeypatch.setattr(doctor, "assemble_product_runtime", lambda **kwargs: runtime)

    checks = doctor._runtime_checks(
        transport="browser-owned",
        auth_file="auth.json",
        conversation=None,
    )

    by_id = {check.id: check for check in checks}
    assert by_id["runtime.fail_closed_policy"].status is DoctorCheckStatus.FAIL


def test_run_doctor_aggregates_sections_and_skips_unrequested_artifacts(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "_environment_checks", lambda: [_check("environment", DoctorCheckStatus.PASS)])
    monkeypatch.setattr(doctor, "_auth_checks", lambda *args, **kwargs: [_check("auth", DoctorCheckStatus.PASS)])
    monkeypatch.setattr(doctor, "_install_checks", lambda: [_check("install", DoctorCheckStatus.PASS)])
    monkeypatch.setattr(doctor, "_bridge_checks", lambda: [_check("bridge", DoctorCheckStatus.PASS)])
    monkeypatch.setattr(doctor, "_runtime_checks", lambda **kwargs: [_check("runtime", DoctorCheckStatus.PASS)])

    report = run_doctor()

    assert report.ok is True
    assert [check.id for check in report.checks[:-1]] == [
        "environment",
        "auth",
        "install",
        "bridge",
        "runtime",
    ]
    assert report.checks[-1].id == "artifact.manifest"
    assert report.checks[-1].status is DoctorCheckStatus.SKIP


def test_doctor_cli_json_success_forwards_optional_inputs(monkeypatch, capsys, tmp_path: Path) -> None:
    captured = {}
    report = DoctorReport((_check("ready", DoctorCheckStatus.PASS),))

    def fake_run_doctor(**kwargs):
        captured.update(kwargs)
        return report

    monkeypatch.setattr(cli, "run_doctor", fake_run_doctor)
    manifest = tmp_path / "artifact.manifest.json"

    code = cli.main(
        [
            "doctor",
            "--conversation",
            "conversation-1",
            "--profile-dir",
            str(tmp_path / "profile"),
            "--artifact",
            str(manifest),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_OK
    assert payload["command"] == "doctor"
    assert payload["ok"] is True
    assert captured["conversation"] == "conversation-1"
    assert captured["artifacts"] == [manifest]
    assert captured["profile_dir"] == tmp_path / "profile"


def test_doctor_cli_failure_uses_existing_unavailable_exit_code(monkeypatch, capsys) -> None:
    report = DoctorReport(
        (
            _check(
                "bridge.available",
                DoctorCheckStatus.FAIL,
                remediation="Reload extension.",
            ),
        )
    )
    monkeypatch.setattr(cli, "run_doctor", lambda **kwargs: report)

    code = cli.main(["doctor"])

    output = capsys.readouterr().out
    assert code == cli.EXIT_UNAVAILABLE == 1
    assert "CWA doctor: FAIL" in output
    assert "[FAIL] bridge.available" in output
    assert "remediation: Reload extension." in output
