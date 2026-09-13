from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import chatgpt_web_adapter.generated_artifact_handoff as handoff


class _Client:
    def __init__(self) -> None:
        self.base_headers = {
            "user-agent": "cwa-test",
            "authorization": "must-not-cross-origin",
            "cookie": "must-not-cross-origin",
        }

    def _build_headers(self, additions: dict[str, str]) -> dict[str, str]:
        headers = dict(self.base_headers)
        headers.update(additions)
        return headers


def _discovery_payload(*, size: int | None = None) -> dict:
    record = {
        "file_id": "file-product-owned-1",
        "filename": "artifact.txt",
    }
    if size is not None:
        record["size_bytes"] = size
    return {"files": [record]}


def _install_read_chain(
    monkeypatch: pytest.MonkeyPatch,
    *,
    artifact_bytes: bytes = b"artifact-bytes",
    locator: str = "https://chatgpt.com/backend-api/estuary/content?id=opaque",
    discovery_payload: dict | None = None,
    before_publish=None,
):
    calls: list[tuple[str, object]] = []

    def fake_json_get(client, *, url, headers, stage):
        calls.append((stage, url))
        if stage == "discovery":
            return 200, discovery_payload or _discovery_payload(size=len(artifact_bytes))
        if stage == "resolution":
            return 200, {"download_url": locator}
        raise AssertionError(stage)

    def fake_curl(
        client,
        *,
        url,
        headers,
        output_path=None,
        max_bytes=None,
    ):
        calls.append(("retrieval", dict(headers)))
        assert output_path is not None
        assert max_bytes is not None
        output_path.write_bytes(artifact_bytes)
        if before_publish is not None:
            before_publish()
        return 200, b""

    monkeypatch.setattr(handoff, "_json_get", fake_json_get)
    monkeypatch.setattr(handoff, "_run_read_curl", fake_curl)
    return calls


def test_handoff_materializes_verified_bytes_without_exposing_product_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_bytes = b"verified generated artifact\n"
    _install_read_chain(monkeypatch, artifact_bytes=artifact_bytes)
    destination = tmp_path / "saved.txt"

    result = handoff.handoff_generated_artifact(
        _Client(),
        "conversation-1",
        "artifact.txt",
        destination,
    )

    assert destination.read_bytes() == artifact_bytes
    assert result.destination == destination.absolute()
    assert result.source_filename == "artifact.txt"
    assert result.size_bytes == len(artifact_bytes)
    assert result.sha256 == hashlib.sha256(artifact_bytes).hexdigest()
    assert result.overwritten is False
    assert result.integrity_verified is True

    stable = result.to_dict()
    assert stable["schema"] == handoff.GENERATED_ARTIFACT_HANDOFF_SCHEMA
    assert stable["integrity_verified"] is True
    serialized = repr(stable)
    assert "file-product-owned-1" not in serialized
    assert "estuary" not in serialized
    assert not list(tmp_path.glob(".*.cwa-*.part"))


def test_existing_destination_requires_explicit_overwrite_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "saved.txt"
    destination.write_text("keep", encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("network read must not start without destination authority")

    monkeypatch.setattr(handoff, "_json_get", forbidden)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
        )

    assert exc_info.value.reason == "DESTINATION_EXISTS"
    assert exc_info.value.stage == "authority"
    assert exc_info.value.destination_state == "unchanged"
    assert destination.read_text(encoding="utf-8") == "keep"


def test_explicit_overwrite_atomically_replaces_regular_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "saved.txt"
    destination.write_bytes(b"old")
    artifact_bytes = b"new artifact bytes"
    _install_read_chain(monkeypatch, artifact_bytes=artifact_bytes)

    result = handoff.handoff_generated_artifact(
        _Client(),
        "conversation-1",
        "artifact.txt",
        destination,
        overwrite=True,
    )

    assert destination.read_bytes() == artifact_bytes
    assert result.overwritten is True
    assert result.sha256 == hashlib.sha256(artifact_bytes).hexdigest()


def test_no_overwrite_publish_fails_closed_on_destination_race(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "saved.txt"

    def race() -> None:
        destination.write_bytes(b"other-writer")

    _install_read_chain(monkeypatch, before_publish=race)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
        )

    assert exc_info.value.reason == "DESTINATION_EXISTS"
    assert exc_info.value.stage == "publish"
    assert exc_info.value.destination_state == "unchanged"
    assert destination.read_bytes() == b"other-writer"
    assert not list(tmp_path.glob(".*.cwa-*.part"))


def test_duplicate_filename_selector_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "files": [
            {"file_id": "file-1", "filename": "artifact.txt"},
            {"file_id": "file-2", "filename": "artifact.txt"},
        ]
    }
    _install_read_chain(monkeypatch, discovery_payload=payload)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            tmp_path / "saved.txt",
        )

    assert exc_info.value.reason == "ARTIFACT_SELECTOR_AMBIGUOUS"
    assert exc_info.value.stage == "discovery"
    assert not (tmp_path / "saved.txt").exists()


def test_production_identity_requires_explicit_file_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {
        "files": [
            {
                "artifact_id": "research-fallback-not-production-authority",
                "filename": "artifact.txt",
            }
        ]
    }
    _install_read_chain(monkeypatch, discovery_payload=payload)

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            tmp_path / "saved.txt",
        )

    assert exc_info.value.reason == "PRODUCT_FILE_ID_REQUIRED"
    assert not (tmp_path / "saved.txt").exists()


def test_unrecognized_locator_origin_is_rejected_before_artifact_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _install_read_chain(
        monkeypatch,
        locator="https://example.com/artifact.txt",
    )

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            tmp_path / "saved.txt",
        )

    assert exc_info.value.reason == "LOCATOR_REJECTED"
    assert exc_info.value.stage == "resolution"
    assert [stage for stage, _ in calls] == ["discovery", "resolution"]
    assert not (tmp_path / "saved.txt").exists()


def test_oaiusercontent_fetch_never_receives_chatgpt_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = _install_read_chain(
        monkeypatch,
        locator="https://files.oaiusercontent.com/object/opaque",
    )

    handoff.handoff_generated_artifact(
        _Client(),
        "conversation-1",
        "artifact.txt",
        tmp_path / "saved.txt",
    )

    retrieval_headers = [value for stage, value in calls if stage == "retrieval"][0]
    assert isinstance(retrieval_headers, dict)
    lowered = {key.lower(): value for key, value in retrieval_headers.items()}
    assert "authorization" not in lowered
    assert "cookie" not in lowered
    assert lowered["user-agent"] == "cwa-test"


def test_source_size_mismatch_never_publishes_destination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_read_chain(
        monkeypatch,
        artifact_bytes=b"actual",
        discovery_payload=_discovery_payload(size=999),
    )
    destination = tmp_path / "saved.txt"

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
        )

    assert exc_info.value.reason == "SOURCE_SIZE_MISMATCH"
    assert exc_info.value.stage == "verification"
    assert exc_info.value.destination_state == "unchanged"
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.cwa-*.part"))


def test_symlink_destination_is_never_overwrite_authority(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.txt"
    target.write_bytes(b"target")
    destination = tmp_path / "link.txt"
    try:
        destination.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
            overwrite=True,
        )

    assert exc_info.value.reason == "DESTINATION_SYMLINK_REJECTED"
    assert target.read_bytes() == b"target"


def test_error_projection_does_not_expose_identity_or_locator() -> None:
    error = handoff.GeneratedArtifactHandoffError(
        "LOCATOR_REJECTED",
        stage="resolution",
        status_code=403,
    )

    assert error.to_dict() == {
        "reason": "LOCATOR_REJECTED",
        "stage": "resolution",
        "status_code": 403,
        "destination_state": "unchanged",
    }
    assert "file_id" not in repr(error.to_dict())
    assert "http" not in str(error)
