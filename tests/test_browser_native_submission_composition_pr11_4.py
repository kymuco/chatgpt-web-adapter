from __future__ import annotations

from types import SimpleNamespace

import chatgpt_web_adapter.browser_native_client as subject
from chatgpt_web_adapter.types import ChatResponse


def test_compatibility_send_composes_exactly_one_submit_and_one_await(monkeypatch):
    calls = []
    client = SimpleNamespace()
    submission = SimpleNamespace(submission_id="submission-1")
    response = ChatResponse(text="done")

    def fake_submit(self, prompt, **kwargs):
        calls.append(("submit", self, prompt, dict(kwargs)))
        return submission

    def fake_await(self, value):
        calls.append(("await", self, value))
        return response

    monkeypatch.setattr(subject, "submit_browser_native", fake_submit)
    monkeypatch.setattr(subject, "await_browser_native_final", fake_await)

    result = subject.send_browser_native(
        client,
        "hello",
        conversation="conversation-0",
        timeout=77.0,
        poll_interval=0.25,
    )

    assert result is response
    assert [entry[0] for entry in calls] == ["submit", "await"]
    assert calls[0][1] is client
    assert calls[0][2] == "hello"
    assert calls[0][3]["conversation"] == "conversation-0"
    assert calls[0][3]["timeout"] == 77.0
    assert calls[0][3]["poll_interval"] == 0.25
    assert calls[1] == ("await", client, submission)
