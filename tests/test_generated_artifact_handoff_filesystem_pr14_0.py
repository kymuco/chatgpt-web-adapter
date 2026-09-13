from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import chatgpt_web_adapter.generated_artifact_handoff as handoff


class _Client:
    def __init__(self) -> None:
        self.base_headers = {"user-agent": "cwa-test"}

    def _build_headers(self, additions: dict[str, str]) -> dict[str, str]:
        headers = dict(self.base_headers)
        headers.update(additions)
        return headers


def _install_read_chain(
    monkeypatch: pytest.MonkeyPatch,
    *,
    artifact_bytes: bytes = b"abc",
) -> None:
    def fake_json_get(client, *, url, headers, stage):
        if stage == "discovery":
            return 200, {
                "files": [
                    {
                        "file_id": "file-product-owned-1",
                        "filename": "artifact.txt",
                        "size_bytes": len(artifact_bytes),
                    }
                ]
            }
        if stage == "resolution":
            return 200, {
                "download_url": "https://chatgpt.com/backend-api/estuary/opaque"
            }
        raise AssertionError(stage)

    def fake_curl(
        client,
        *,
        url,
        headers,
        output_path=None,
        max_bytes=None,
    ):
        assert output_path is not None
        output_path.write_bytes(artifact_bytes)
        return 200, b""

    monkeypatch.setattr(handoff, "_json_get", fake_json_get)
    monkeypatch.setattr(handoff, "_run_read_curl", fake_curl)


def test_staging_verification_failure_leaves_destination_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_read_chain(monkeypatch)
    destination = tmp_path / "saved.txt"

    def fail_fsync(path: Path) -> None:
        raise OSError("simulated staging sync failure")

    monkeypatch.setattr(handoff, "_fsync_file", fail_fsync)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
        )

    error = exc_info.value
    assert error.reason == "STAGING_VERIFICATION_FAILED"
    assert error.stage == "verification"
    assert error.destination_state == "unchanged"
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.cwa-*.part"))


def test_post_publish_read_failure_is_reported_as_published_unverified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_bytes = b"abc"
    expected_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    _install_read_chain(monkeypatch, artifact_bytes=artifact_bytes)
    destination = tmp_path / "saved.txt"

    monkeypatch.setattr(handoff, "_fsync_file", lambda path: None)
    calls = 0

    def integrity(path: Path) -> tuple[int, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return len(artifact_bytes), expected_sha256
        raise OSError("simulated destination read failure")

    monkeypatch.setattr(handoff, "_file_integrity", integrity)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
        )

    error = exc_info.value
    assert error.reason == "POST_WRITE_INTEGRITY_UNAVAILABLE"
    assert error.stage == "verification"
    assert error.destination_state == "published_unverified"
    assert destination.read_bytes() == artifact_bytes
    assert calls == 2
    assert not list(tmp_path.glob(".*.cwa-*.part"))
