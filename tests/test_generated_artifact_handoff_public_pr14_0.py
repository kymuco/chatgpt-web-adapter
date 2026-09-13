from __future__ import annotations

from pathlib import Path

import pytest

import chatgpt_web_adapter as adapter
import chatgpt_web_adapter.generated_artifact_handoff as handoff


class _WriteTransport:
    transport_id = adapter.DEFAULT_PRODUCT_TRANSPORT

    def governance(self) -> dict:
        return {}


def _result(tmp_path: Path) -> adapter.GeneratedArtifactHandoffResult:
    return adapter.GeneratedArtifactHandoffResult(
        conversation_id="conversation-1",
        source_filename="artifact.txt",
        destination=tmp_path / "artifact.txt",
        size_bytes=3,
        sha256="a" * 64,
        overwritten=False,
    )


def _runtime_with(canonical) -> adapter.ChatGPTProductRuntime:
    runtime = adapter.ChatGPTProductRuntime.__new__(adapter.ChatGPTProductRuntime)
    runtime.canonical = canonical
    runtime.transport = adapter.DEFAULT_PRODUCT_TRANSPORT
    runtime.write_transport = _WriteTransport()
    return runtime


def test_web_client_exposes_governed_generated_artifact_handoff() -> None:
    assert (
        adapter.ChatGPTWebClient.handoff_generated_artifact
        is handoff.handoff_generated_artifact
    )


def test_internal_handoff_helper_is_not_root_exported() -> None:
    assert "handoff_generated_artifact" not in adapter.__all__
    assert not hasattr(adapter, "handoff_generated_artifact")


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


def test_runtime_governance_declares_handoff_authority_when_supported() -> None:
    class _Canonical:
        def handoff_generated_artifact(self, *args, **kwargs):
            raise AssertionError("governance must not execute handoff")

    governance = _runtime_with(_Canonical()).governance()

    assert governance["generated_artifact_handoff_supported"] is True
    assert (
        governance["generated_artifact_handoff_identity_authority"]
        == "CONVERSATION_SCOPED_FILE_ID"
    )
    assert (
        governance["generated_artifact_handoff_destination_authority"]
        == "EXPLICIT_CALLER_PATH"
    )
    assert governance["generated_artifact_handoff_implicit_overwrite"] is False
    assert governance["generated_artifact_handoff_automatic_retry"] is False
    assert (
        governance["generated_artifact_handoff_cross_origin_chatgpt_credentials"]
        is False
    )


def test_runtime_governance_does_not_invent_handoff_for_legacy_client() -> None:
    governance = _runtime_with(object()).governance()

    assert governance["generated_artifact_handoff_supported"] is False
    assert governance["generated_artifact_handoff_identity_authority"] is None
    assert governance["generated_artifact_handoff_destination_authority"] is None
    assert governance["generated_artifact_handoff_implicit_overwrite"] is False
    assert governance["generated_artifact_handoff_automatic_retry"] is False


def test_handoff_root_value_exports_are_shared_support() -> None:
    shared = (
        "DEFAULT_GENERATED_ARTIFACT_MAX_BYTES",
        "GENERATED_ARTIFACT_HANDOFF_SCHEMA",
        "GeneratedArtifactHandoffError",
        "GeneratedArtifactHandoffResult",
    )

    for name in shared:
        assert name in adapter.__all__
        assert hasattr(adapter, name)
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
