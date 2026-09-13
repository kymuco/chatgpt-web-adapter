from __future__ import annotations

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


def test_known_oversized_artifact_fails_before_resolution_or_retrieval(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fake_json_get(client, *, url, headers, stage):
        calls.append(stage)
        if stage != "discovery":
            raise AssertionError("oversized metadata must stop before resolver")
        return 200, {
            "files": [
                {
                    "file_id": "file-product-owned-1",
                    "filename": "artifact.txt",
                    "size_bytes": 11,
                }
            ]
        }

    def forbidden_retrieval(*args, **kwargs):
        raise AssertionError("oversized metadata must stop before artifact retrieval")

    monkeypatch.setattr(handoff, "_json_get", fake_json_get)
    monkeypatch.setattr(handoff, "_run_read_curl", forbidden_retrieval)
    destination = tmp_path / "saved.txt"

    with pytest.raises(handoff.GeneratedArtifactHandoffError) as exc_info:
        handoff.handoff_generated_artifact(
            _Client(),
            "conversation-1",
            "artifact.txt",
            destination,
            max_bytes=10,
        )

    error = exc_info.value
    assert error.reason == "ARTIFACT_SIZE_LIMIT_EXCEEDED"
    assert error.stage == "discovery"
    assert error.destination_state == "unchanged"
    assert calls == ["discovery"]
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.cwa-*.part"))
