from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
import chatgpt_web_adapter.generated_artifact_handoff as handoff


def _result(tmp_path: Path) -> adapter.GeneratedArtifactHandoffResult:
    return adapter.GeneratedArtifactHandoffResult(
        conversation_id="conversation-1",
        source_filename="artifact.txt",
        destination=tmp_path / "artifact.txt",
        size_bytes=3,
        sha256="a" * 64,
        overwritten=False,
    )


def test_web_client_exposes_governed_generated_artifact_handoff() -> None:
    assert (
        adapter.ChatGPTWebClient.handoff_generated_artifact
        is handoff.handoff_generated_artifact
    )


def test_runtime_forwards_additive_handoff_capability(tmp_path: Path) -> None:
    expected = _result(tmp_path)

    class _Canonical:
        def handoff_generated_artifact(
            self,
            conversation,
            filename,
            destination,
            *,
            overwrite=False,
            max_bytes=adapter.DEFAULT_GENERATED_ARTIFACT_MAX_BYTES,
        ):
            assert conversation == "conversation-1"
            assert filename == "artifact.txt"
            assert destination == tmp_path / "saved.txt"
            assert overwrite is True
            assert max_bytes == 123
            return expected

    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = _Canonical()

    result = runtime.handoff_generated_artifact(
        "conversation-1",
        "artifact.txt",
        tmp_path / "saved.txt",
        overwrite=True,
        max_bytes=123,
    )

    assert result is expected


def test_runtime_fails_explicitly_for_legacy_canonical_client(tmp_path: Path) -> None:
    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = object()

    with pytest.raises(TypeError, match="handoff_generated_artifact"):
        runtime.handoff_generated_artifact(
            "conversation-1",
            "artifact.txt",
            tmp_path / "saved.txt",
        )


def test_runtime_rejects_wrong_handoff_return_type(tmp_path: Path) -> None:
    class _Canonical:
        def handoff_generated_artifact(self, *args, **kwargs):
            return {"looks": "successful"}

    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = _Canonical()

    with pytest.raises(TypeError, match="GeneratedArtifactHandoffResult"):
        runtime.handoff_generated_artifact(
            "conversation-1",
            "artifact.txt",
            tmp_path / "saved.txt",
        )


def test_handoff_root_exports_have_explicit_support_tiers() -> None:
    primary = (
        "GeneratedArtifactHandoffResult",
        "handoff_generated_artifact",
    )
    shared = (
        "DEFAULT_GENERATED_ARTIFACT_MAX_BYTES",
        "GENERATED_ARTIFACT_HANDOFF_SCHEMA",
        "GeneratedArtifactHandoffError",
    )

    for name in (*primary, *shared):
        assert name in adapter.__all__
        assert hasattr(adapter, name)

    for name in primary:
        assert (
            adapter.public_surface_tier(name)
            is adapter.PublicSurfaceTier.PRIMARY_PRODUCTION
        )
    for name in shared:
        assert (
            adapter.public_surface_tier(name)
            is adapter.PublicSurfaceTier.SHARED_SUPPORT
        )


def test_result_projection_is_stable_and_locator_free(tmp_path: Path) -> None:
    result = _result(tmp_path)

    assert result.to_dict() == {
        "schema": adapter.GENERATED_ARTIFACT_HANDOFF_SCHEMA,
        "conversation_id": "conversation-1",
        "source_filename": "artifact.txt",
        "destination": str((tmp_path / "artifact.txt").absolute()),
        "size_bytes": 3,
        "sha256": "a" * 64,
        "overwritten": False,
        "integrity_verified": True,
    }
