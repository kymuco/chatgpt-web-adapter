"""Cross-surface regression for regular and Project-scoped ChatGPT links.

All cases are read-only and synthetic: never connect to a ChatGPT account.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from chatgpt_web_adapter import ChatGPTWebClient, ConversationRef
from chatgpt_web_adapter.messages import get_messages as parse_messages


CONVERSATION_ID = "6ae57b9d-95dc-83ed-8bab-3556e8c2d1c0"
PROJECT_ID = "g-p-6ade211b7c10819194ec0adbdc964fe3-cwa"
REGULAR_URL = f"https://chatgpt.com/c/{CONVERSATION_ID}"
PROJECT_URL = f"https://chatgpt.com/g/{PROJECT_ID}/c/{CONVERSATION_ID}"


def _payload() -> dict:
    return {
        "conversation_id": CONVERSATION_ID,
        "current_node": "assistant-1",
        "mapping": {
            "user-1": {
                "id": "user-1",
                "parent": None,
                "message": {
                    "id": "message-user-1",
                    "author": {"role": "user"},
                    "content": {"parts": ["Prompt"]},
                    "create_time": 1.0,
                },
            },
            "assistant-1": {
                "id": "assistant-1",
                "parent": "user-1",
                "message": {
                    "id": "message-assistant-1",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"parts": ["Answer"]},
                    "create_time": 2.0,
                },
            },
        },
    }


@pytest.mark.parametrize(
    "url", [REGULAR_URL, PROJECT_URL, PROJECT_URL + "?model=gpt-6"]
)
def test_user_full_history_to_markdown_pattern_uses_canonical_id(url: str) -> None:
    """Exercise the user's ConversationRef -> full payload -> messages path."""
    calls = []
    client = object.__new__(ChatGPTWebClient)

    def fake_full_read(conversation_id: str) -> dict:
        calls.append(conversation_id)
        return _payload()

    client._get_full_conversation_payload = fake_full_read
    ref = ConversationRef.from_any(url)
    payload = client._get_full_conversation_payload(ref.conversation_id)

    class PayloadReader:
        def __init__(self, result):
            self.payload = result

        def _get_conversation_payload(self, _conversation_id):
            return self.payload

    messages = parse_messages(
        PayloadReader(payload),
        ref,
        limit=None,
        roles=("user", "assistant"),
        include_empty=False,
    )
    blocks = []
    for message in messages:
        if message.role == "assistant" and message.recipient not in (None, "all"):
            continue
        text = message.text.strip()
        if text:
            blocks.append(f"## {(message.role or 'message').upper()}\n\n{text}")

    assert calls == [CONVERSATION_ID]
    assert blocks == ["## USER\n\nPrompt", "## ASSISTANT\n\nAnswer"]
    assert len(payload["mapping"]) == 2


@pytest.mark.parametrize("url", [REGULAR_URL, PROJECT_URL])
def test_public_attach_and_message_read_accept_both_routes(url: str) -> None:
    client = object.__new__(ChatGPTWebClient)
    calls = []

    def read(conversation_id: str) -> dict:
        calls.append(conversation_id)
        return _payload()

    client._get_conversation_payload = read
    client._get_full_conversation_payload = read
    assert client.attach_conversation(url).conversation_id == CONVERSATION_ID
    assert [message.text for message in client.get_messages(url, limit=None)] == [
        "Prompt",
        "Answer",
    ]
    assert calls and set(calls) == {CONVERSATION_ID}


def test_extension_route_parser_supports_project_tabs_without_ambiguous_matches() -> None:
    """Run the shipping service-worker route parser in a Node VM (no Chrome)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    worker = (
        Path(__file__).resolve().parents[1]
        / "src/chatgpt_web_adapter/browser_native_extension/service_worker.js"
    )
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync(process.argv[1], "utf8");
const begin = source.indexOf("function conversationIdFromUrl(url) {");
const end = source.indexOf("\nfunction _cwaBaseIsConversationWrite", begin);
assert.ok(begin >= 0 && end > begin);
const parse = vm.runInNewContext(
  "(" + source.slice(begin, end).trim() + ")", {
    URL,
    CHATGPT_ORIGIN: "https://chatgpt.com"
  }
);
const id = "6ae57b9d-95dc-83ed-8bab-3556e8c2d1c0";
const project = "g-p-6ade211b7c10819194ec0adbdc964fe3-cwa";
assert.equal(parse("https://chatgpt.com/c/" + id), id);
assert.equal(parse("https://chatgpt.com/g/" + project + "/c/" + id), id);
assert.equal(parse("https://chatgpt.com/g/" + project + "/c/" + id + "/?model=gpt-6"), id);
for (const bad of [
  "https://example.com/g/" + project + "/c/" + id,
  "https://chatgpt.com/g/" + project,
  "https://chatgpt.com/g/not-project/c/" + id,
  "https://chatgpt.com/c/" + id + "/extra",
  "https://chatgpt.com/g/" + project + "/c/" + id + "/extra",
  "https://chatgpt.com/other/c/" + id
]) assert.equal(parse(bad), null, bad);
"""
    result = subprocess.run(
        [node, "-e", script, str(worker)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
