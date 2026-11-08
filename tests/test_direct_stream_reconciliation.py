from __future__ import annotations

import threading
import time

import pytest

from chatgpt_web_adapter.direct_stream_reconciliation import (
    StalledStreamReconciler,
    confirmed_answer,
)


def payload(*, user="user-new", final="answer", end_turn=True, channel="final"):
    def node(identifier, parent, role, text, **extra):
        return {
            "id": identifier,
            "parent": parent,
            "message": {
                "id": identifier,
                "author": {"role": role},
                "content": {"content_type": "text", "parts": [text]},
                **extra,
            },
        }

    return {
        "current_node": "assistant-new",
        "mapping": {
            "old": node("old", None, "assistant", "old"),
            user: node(user, "old", "user", "request"),
            "assistant-new": node(
                "assistant-new",
                user,
                "assistant",
                final,
                end_turn=end_turn,
                channel=channel,
                metadata={"finish_details": {"type": "stop"}},
            ),
        },
    }


def test_confirmation_requires_exact_current_branch_and_terminal_answer():
    answer = confirmed_answer(payload(), user_message_id="user-new")
    assert answer is not None
    assert (answer.message_id, answer.text) == ("assistant-new", "answer")
    assert confirmed_answer(payload(), user_message_id="other") is None
    assert confirmed_answer(payload(final=""), user_message_id="user-new") is None
    assert confirmed_answer(payload(end_turn=False), user_message_id="user-new") is None
    assert (
        confirmed_answer(payload(channel="analysis"), user_message_id="user-new")
        is None
    )


def test_confirmation_rejects_newer_user_message():
    data = payload()
    data["mapping"]["later-user"] = {
        "parent": "assistant-new",
        "message": {
            "id": "later-user",
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": ["another turn"]},
        },
    }
    data["mapping"]["later-answer"] = {
        "parent": "later-user",
        "message": {
            "id": "later-answer",
            "author": {"role": "assistant"},
            "content": {"content_type": "text", "parts": ["other"]},
            "end_turn": True,
            "metadata": {"finish_details": {"type": "stop"}},
        },
    }
    data["current_node"] = "later-answer"
    assert confirmed_answer(data, user_message_id="user-new") is None


class Process:
    def __init__(self):
        self.terminated = threading.Event()

    def poll(self):
        return 1 if self.terminated.is_set() else None

    def terminate(self):
        self.terminated.set()


class Reader:
    def __init__(self, data, status="COMPLETE"):
        self.data, self.status = data, status
        self.calls = []

    def _build_headers(self, _):
        return {}

    def _json_request(self, method, url, body, headers):
        self.calls.append(method)
        return 200, {"status": self.status}

    def _get_conversation_payload(self, _):
        self.calls.append("GET")
        return self.data


def test_watchdog_stops_only_after_exact_readback_and_never_posts():
    process, reader = Process(), Reader(payload())
    worker = StalledStreamReconciler(
        reader, process, "chat", "user-new", idle_seconds=0, poll_seconds=0.001
    )
    worker.start()
    assert process.terminated.wait(1)
    worker.stop()
    worker.thread.join(1)
    assert worker.result.text == "answer"
    assert reader.calls == ["GET", "GET"]


@pytest.mark.parametrize(
    "status,data", [("COMPLETE", payload(user="old-user")), ("IS_STREAMING", payload())]
)
def test_watchdog_leaves_unconfirmed_stream_running(status, data):
    process, reader = Process(), Reader(data, status)
    worker = StalledStreamReconciler(
        reader, process, "chat", "user-new", idle_seconds=0, poll_seconds=0.005
    )
    worker.start()
    time.sleep(0.04)
    worker.stop()
    worker.thread.join(1)
    assert not process.terminated.is_set()
    assert worker.result is None
    assert all(method == "GET" for method in reader.calls)


def test_active_stream_is_not_polled():
    process, reader = Process(), Reader(payload())
    worker = StalledStreamReconciler(
        reader, process, "chat", "user-new", idle_seconds=10, poll_seconds=0.005
    )
    worker.start()
    time.sleep(0.04)
    worker.stop()
    worker.thread.join(1)
    assert reader.calls == []
    assert not process.terminated.is_set()


def test_failed_readback_keeps_stream_running():
    class FailingReader(Reader):
        def _get_conversation_payload(self, _):
            self.calls.append("GET")
            raise TimeoutError("read timed out")

    process, reader = Process(), FailingReader(payload())
    worker = StalledStreamReconciler(
        reader, process, "chat", "user-new", idle_seconds=0, poll_seconds=0.005
    )
    worker.start()
    time.sleep(0.04)
    worker.stop()
    worker.thread.join(1)
    assert reader.calls
    assert worker.result is None
    assert not process.terminated.is_set()


def test_stopped_worker_cannot_terminate_after_inflight_read():
    entered, release = threading.Event(), threading.Event()

    class SlowReader(Reader):
        def _get_conversation_payload(self, _):
            entered.set()
            assert release.wait(1)
            return self.data

    process, reader = Process(), SlowReader(payload())
    worker = StalledStreamReconciler(
        reader, process, "chat", "user-new", idle_seconds=0, poll_seconds=0.001
    )
    worker.start()
    assert entered.wait(1)
    worker.stop()
    release.set()
    worker.thread.join(1)
    assert worker.result is None
    assert not process.terminated.is_set()
