"""Offline Direct HTTP text integrity regressions; no network or credentials."""

from contextlib import nullcontext
from threading import RLock

import pytest

from chatgpt_web_adapter.browserless_http import BrowserlessHTTPClient
from chatgpt_web_adapter.browserless_stream import parse_event
from chatgpt_web_adapter.client import ChatGPTWebClient
from chatgpt_web_adapter.exceptions import RequestError
from chatgpt_web_adapter.response_integrity import canonical_turn_text
from chatgpt_web_adapter.types import ChatConversation, ChatResponse

PATH = "/message/content/parts/0"


def snapshot(text, message_id="a", channel="final"):
    return {
        "v": {
            "message": {
                "id": message_id,
                "author": {"role": "assistant"},
                "recipient": "all",
                "channel": channel,
                "content": {"content_type": "text", "parts": [text]},
            }
        }
    }


def patch(text, operation="append"):
    return {"p": PATH, "o": operation, "v": text}


def assemble(events):
    state = {"recipient": "all"}
    emitted = []
    for event in events:
        tokens, _ = parse_event(event, state)
        emitted.extend(tokens)
    return state.get("_browserless_final_text", "".join(emitted)), "".join(emitted)


@pytest.mark.parametrize("batched", [False, True])
def test_replacement_does_not_repeat_incomplete_word(batched):
    prefix = "Да, ты прав! ❤️ Я проверила исход"
    replacement = patch(prefix, "replace")
    if batched:
        replacement = {"o": "patch", "v": [replacement]}
    final, emitted = assemble(
        [snapshot(""), patch(prefix), replacement, patch("ники.")]
    )
    assert final == prefix + "ники."
    assert emitted == final


def test_nonprefix_snapshot_revision_is_final_even_without_retractable_callback():
    final, emitted = assemble(
        [snapshot("Неправильный"), snapshot("Правильный"), patch(" ответ.")]
    )
    assert final == "Правильный ответ."
    assert emitted == "Неправильный"


def test_nonprefix_patch_revision_with_subsequent_append():
    final, emitted = assemble(
        [snapshot("old"), patch("new", "replace"), patch(" text")]
    )
    assert final == "new text"
    assert emitted == "old"


def test_legitimate_repeat_is_not_deduplicated():
    assert assemble([snapshot(""), patch("да "), patch("да ")])[0] == "да да "


def test_repeated_snapshot_and_multiple_messages():
    final, _ = assemble(
        [
            snapshot("first "),
            snapshot("first "),
            snapshot("hidden", "thinking", "analysis"),
            patch("hidden suffix"),
            snapshot("second", "b"),
        ]
    )
    assert final == "first second"


def test_unbound_prefix_does_not_duplicate_at_first_snapshot():
    final, emitted = assemble([patch("prefix"), snapshot("prefix"), patch(" end")])
    assert final == emitted == "prefix end"


def test_multiple_content_parts_preserved():
    event = snapshot("old")
    event["v"]["message"]["content"]["parts"].append(" suffix")
    final, _ = assemble([event, patch("new", "replace")])
    assert final == "new suffix"


def canonical_payload():
    return {
        "conversation_id": "c",
        "current_node": "assistant-node",
        "mapping": {
            "user-node": {
                "parent": None,
                "message": {"id": "u", "author": {"role": "user"}},
            },
            "assistant-node": {
                "parent": "user-node",
                "message": {
                    "id": "a",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "channel": "final",
                    "status": "finished_successfully",
                    "end_turn": True,
                    "content": {"content_type": "text", "parts": ["Correct ", "text"]},
                },
            },
        },
    }


def test_canonical_read_is_identity_bound_and_preserves_exact_parts():
    assert (
        canonical_turn_text(
            canonical_payload(), conversation_id="c", user_id="u", message_id="a"
        )
        == "Correct text"
    )


@pytest.mark.parametrize(
    "mutation",
    ["other_conversation", "other_message", "other_user", "running", "hidden"],
)
def test_canonical_read_never_guesses(mutation):
    payload = canonical_payload()
    if mutation == "other_conversation":
        payload["conversation_id"] = "wrong"
    elif mutation == "other_message":
        payload["mapping"]["assistant-node"]["message"]["id"] = "wrong"
    elif mutation == "other_user":
        payload["mapping"]["user-node"]["message"]["id"] = "wrong"
    elif mutation == "running":
        payload["mapping"]["assistant-node"]["message"]["status"] = "in_progress"
    else:
        payload["mapping"]["assistant-node"]["message"]["channel"] = "analysis"
    with pytest.raises(RequestError, match="do not replay"):
        canonical_turn_text(payload, conversation_id="c", user_id="u", message_id="a")


@pytest.mark.parametrize("read_ok", [True, False])
def test_verify_final_text_one_write_and_one_read(monkeypatch, read_ok):
    client = object.__new__(BrowserlessHTTPClient)
    client._browserless_lock = RLock()
    client._browserless_sending = False
    client.last_timing = {}
    client.set_sentinel_bundle_provider = lambda _: None
    monkeypatch.setattr(
        "chatgpt_web_adapter.browserless_http.bootstrap_web_session", lambda _: True
    )
    monkeypatch.setattr(
        "chatgpt_web_adapter.browserless_http.suppress_web_session_debug_trace",
        nullcontext,
    )
    writes = []
    reads = []

    def send(_self, prompt, **kwargs):
        writes.append(prompt)
        return ChatResponse(
            text="CorruptCorrupt",
            conversation=ChatConversation(
                conversation_id="c", user_id="u", message_id="a"
            ),
        )

    def read(cid):
        reads.append(cid)
        if not read_ok:
            raise RequestError("read failed")
        return canonical_payload()

    monkeypatch.setattr(ChatGPTWebClient, "send", send)
    monkeypatch.setattr(client, "_get_conversation_payload", read)
    if read_ok:
        assert client.send("Once", verify_final_text=True).text == "Correct text"
    else:
        with pytest.raises(RequestError, match="read failed"):
            client.send("Once", verify_final_text=True)
    assert writes == ["Once"]
    assert reads == ["c"]
    assert client._browserless_sending is False
