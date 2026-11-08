"""Bounded read-only reconciliation for a stalled Direct HTTP stream."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from .messages import _chat_message_from_node, _current_branch_nodes
from .status import _status_from_payload


@dataclass(frozen=True)
class ReconciledAnswer:
    message_id: str
    text: str


def confirmed_answer(payload: Any, *, user_message_id: str) -> ReconciledAnswer | None:
    """Require the exact submitted user message and a final current descendant."""
    if not isinstance(payload, dict) or not user_message_id:
        return None
    branch = _current_branch_nodes(payload)
    messages = [
        message
        for node_id, node in branch
        if (message := _chat_message_from_node(node_id, node)) is not None
    ]
    matches = [
        i
        for i, message in enumerate(messages)
        if message.role == "user" and message.message_id == user_message_id
    ]
    if len(matches) != 1 or matches[0] >= len(messages) - 1:
        return None
    if any(message.role == "user" for message in messages[matches[0] + 1 :]):
        return None
    status = _status_from_payload(payload)
    final = messages[-1]
    current = branch[-1][1].get("message") if branch else None
    if (
        not isinstance(current, dict)
        or current.get("end_turn") is not True
        or current.get("channel") not in (None, "final")
        or status.status != "completed"
        or status.finish_reason != "stop"
        or status.pending_approval
        or final.role != "assistant"
        or not final.text
        or not final.message_id
        or final.message_id != status.message_id
    ):
        return None
    return ReconciledAnswer(message_id=final.message_id, text=final.text)


class StalledStreamReconciler:
    """Observe a stream without retrying or replacing its product write."""

    def __init__(
        self,
        reader: Any,
        process: Any,
        conversation_id: str,
        user_message_id: str,
        *,
        idle_seconds: float = 10,
        poll_seconds: float = 3,
    ) -> None:
        self.reader = reader
        self.process = process
        self.conversation_id = conversation_id
        self.user_message_id = user_message_id
        self.idle_seconds = idle_seconds
        self.poll_seconds = poll_seconds
        self.last_activity = time.monotonic()
        self.stop_event = threading.Event()
        self.result: ReconciledAnswer | None = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def activity(self) -> None:
        self.last_activity = time.monotonic()

    def stop(self) -> None:
        self.stop_event.set()

    def _run(self) -> None:
        while not self.stop_event.wait(self.poll_seconds):
            if self.process.poll() is not None:
                return
            if time.monotonic() - self.last_activity < self.idle_seconds:
                continue
            try:
                headers = self.reader._build_headers(
                    {
                        "accept": "application/json",
                        "referer": f"https://chatgpt.com/c/{self.conversation_id}",
                    }
                )
                status, data = self.reader._json_request(
                    "GET",
                    f"https://chatgpt.com/backend-api/conversation/{self.conversation_id}/stream_status",
                    None,
                    headers,
                )
                if (
                    status != 200
                    or not isinstance(data, dict)
                    or data.get("status") != "COMPLETE"
                ):
                    continue
                if self.stop_event.is_set():
                    return
                payload = self.reader._get_conversation_payload(self.conversation_id)
                answer = confirmed_answer(payload, user_message_id=self.user_message_id)
                if (
                    answer is None
                    or self.stop_event.is_set()
                    or self.process.poll() is not None
                ):
                    continue
                self.result = answer
                try:
                    self.process.terminate()
                except OSError:
                    self.result = None
                    continue
                return
            except Exception:
                # Observation failures never turn an uncertain write into success.
                continue
