"""HDE creates a new CWA conversation; the initial chat ID can be absent.

Intercept the actual legacy client's main curl subprocess boundary; all other
provider preparation is synthetic. No model send or auth-file access.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from chatgpt_web_adapter import legacy_client_core as core
from test_browserless_dispatch_identity import StopBeforePost, _client


@pytest.mark.parametrize("fail_storage", [False, True])
def test_new_chat_identity_exact_before_post(monkeypatch, fail_storage):
    client, _ = _client(monkeypatch, False)
    identities = []
    launches = []

    def persist(identity):
        assert set(identity) == {
            "conversation_id", "user_message_id", "parent_message_id", "temporary"
        }
        assert identity["conversation_id"] is None
        assert identity["temporary"] is False
        assert isinstance(identity["user_message_id"], str)
        assert identity["user_message_id"]
        assert isinstance(identity["parent_message_id"], str)
        assert identity["parent_message_id"]
        assert "synthetic private request" not in repr(identity)
        identities.append(dict(identity))
        if fail_storage:
            raise OSError("synthetic persistence failure")

    def intercept(command, **_kwargs):
        launches.append(1)
        assert len(identities) == 1
        arg = command[command.index("--data-binary") + 1]
        payload = json.loads(Path(arg[1:]).read_text(encoding="utf-8"))
        assert not payload.get("conversation_id")
        users = [m for m in payload["messages"] if m["author"]["role"] == "user"]
        assert len(users) == 1
        assert users[0]["id"] == identities[0]["user_message_id"]
        assert payload["parent_message_id"] == identities[0]["parent_message_id"]
        raise StopBeforePost()

    monkeypatch.setattr(core.subprocess, "Popen", intercept)
    with pytest.raises(OSError if fail_storage else StopBeforePost):
        client.send("synthetic private request", on_dispatch_identity=persist)
    assert len(identities) == 1
    assert len(launches) == (0 if fail_storage else 1)
