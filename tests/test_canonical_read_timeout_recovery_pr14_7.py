from __future__ import annotations

from types import SimpleNamespace

import pytest

import chatgpt_web_adapter.browser_context_canonical_v2 as canonical_v2
from chatgpt_web_adapter.browser_context_canonical import BrowserContextCanonicalReadError
from chatgpt_web_adapter.browser_context_canonical_v2 import BrowserContextCanonicalTransportV2


class _ProbeTransport(BrowserContextCanonicalTransportV2):
    def __init__(self, reasons: list[str]) -> None:
        provider = SimpleNamespace(
            _load_descriptor=lambda: {},
            _current_browser_authority_lease_id=lambda: "lease-1",
        )
        super().__init__(provider, read_timeout=1.0)
        self.reasons = list(reasons)
        self.calls: list[tuple[str, float, bool, str | None]] = []

    def _read_wire_conversation_once(
        self,
        conversation_id: str,
        *,
        read_timeout: float,
        include_all_pages: bool,
        lease_id: str | None,
    ) -> dict[str, object]:
        self.calls.append(
            (conversation_id, read_timeout, include_all_pages, lease_id)
        )
        if self.reasons:
            reason = self.reasons.pop(0)
            raise BrowserContextCanonicalReadError(
                reason,
                conversation_id=conversation_id,
                retryable=False,
            )
        return {"conversation_id": conversation_id, "messages": []}


@pytest.mark.parametrize("include_all_pages", [False, True])
def test_timeout_retries_one_fresh_canonical_read_with_same_identity(
    monkeypatch: pytest.MonkeyPatch,
    include_all_pages: bool,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(canonical_v2.time, "sleep", sleeps.append)
    transport = _ProbeTransport(["CANONICAL_READ_TIMEOUT"])

    payload = transport._read_wire_conversation(
        "conversation-1",
        timeout=7.0,
        include_all_pages=include_all_pages,
    )

    assert payload == {"conversation_id": "conversation-1", "messages": []}
    assert transport.calls == [
        ("conversation-1", 7.0, include_all_pages, "lease-1"),
        ("conversation-1", 7.0, include_all_pages, "lease-1"),
    ]
    assert sleeps == [canonical_v2._CANONICAL_TIMEOUT_RETRY_DELAY_SECONDS]


def test_timeout_retry_exhaustion_fails_closed_with_specific_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(canonical_v2.time, "sleep", lambda _delay: None)
    transport = _ProbeTransport(
        ["CANONICAL_READ_TIMEOUT", "CANONICAL_READ_TIMEOUT"]
    )

    with pytest.raises(BrowserContextCanonicalReadError) as captured:
        transport._read_wire_conversation(
            "conversation-1",
            timeout=9.0,
            include_all_pages=True,
        )

    assert captured.value.reason_code == "CANONICAL_READ_TIMEOUT_EXHAUSTED"
    assert captured.value.retryable is True
    assert len(transport.calls) == canonical_v2._CANONICAL_TIMEOUT_MAX_ATTEMPTS
    assert {call[3] for call in transport.calls} == {"lease-1"}


def test_non_timeout_canonical_failure_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(canonical_v2.time, "sleep", lambda _delay: None)
    transport = _ProbeTransport(["CANONICAL_READ_AUTHENTICATION_REQUIRED"])

    with pytest.raises(BrowserContextCanonicalReadError) as captured:
        transport._read_wire_conversation(
            "conversation-1",
            timeout=5.0,
            include_all_pages=False,
        )

    assert captured.value.reason_code == "CANONICAL_READ_AUTHENTICATION_REQUIRED"
    assert len(transport.calls) == 1
