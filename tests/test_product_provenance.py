from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.product_provenance import (
    CompletionSource,
    build_product_execution_provenance,
)


def _response(*, finish_reason=None):
    return SimpleNamespace(
        conversation=SimpleNamespace(
            conversation_id="conversation-1",
            message_id="assistant-1",
            finish_reason=finish_reason,
        ),
        request=SimpleNamespace(observed_model="gpt-test"),
    )


def test_canonical_readback_completion_does_not_synthesize_finish_reason() -> None:
    provenance = build_product_execution_provenance(
        transport="browser-owned",
        response=_response(finish_reason=None),
        observation={"runtime_tab_id": 77},
        governance={
            "product_semantics": "ordinary-chatgpt",
            "canonical_readback_required": True,
            "read_plane": "BROWSERLESS_CANONICAL_HTTP",
            "session_plane": "BROWSERLESS_SESSION_HTTP",
            "write_plane": "BROWSER_NATIVE_PAGE_OWNED_WRITE",
        },
    )

    assert provenance.completion.completed is True
    assert provenance.completion.source is CompletionSource.CANONICAL_READBACK
    assert provenance.completion.canonical_completion_proven is True
    assert provenance.completion.finish_reason is None
    assert provenance.completion.finish_reason_observed is False
    assert provenance.completion.finality_detail is None
    assert provenance.identity.conversation_id == "conversation-1"
    assert provenance.identity.message_id == "assistant-1"
    assert provenance.identity.observed_model == "gpt-test"
    assert provenance.transport_metadata == {"runtime_tab_id": 77}


def test_observed_finish_reason_is_preserved_without_becoming_completion_source() -> None:
    provenance = build_product_execution_provenance(
        transport="browser-owned",
        response=_response(finish_reason="stop"),
        observation=SimpleNamespace(to_dict=lambda: {"source": "fake"}),
        governance={"canonical_readback_required": True},
    )

    assert provenance.completion.source is CompletionSource.CANONICAL_READBACK
    assert provenance.completion.finish_reason == "stop"
    assert provenance.completion.finish_reason_observed is True
    assert provenance.transport_metadata == {"source": "fake"}


def test_noncanonical_transport_return_is_distinct_from_canonical_completion() -> None:
    provenance = build_product_execution_provenance(
        transport="browser-owned",
        response=_response(),
        observation=None,
        governance={"canonical_readback_required": False},
    )

    assert provenance.completion.source is CompletionSource.TRANSPORT_RETURN
    assert provenance.completion.canonical_completion_proven is False
