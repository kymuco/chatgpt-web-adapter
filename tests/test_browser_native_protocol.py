from __future__ import annotations

import io
import socket

from chatgpt_web_adapter.browser_native_protocol import (
    PROTOCOL_VERSION,
    read_native_message,
    recv_local_message,
    send_local_message,
    write_native_message,
)


def test_native_stdio_frame_round_trip() -> None:
    stream = io.BytesIO()
    write_native_message(stream, {"protocol": PROTOCOL_VERSION, "value": "мир"})
    stream.seek(0)
    assert read_native_message(stream) == {"protocol": PROTOCOL_VERSION, "value": "мир"}


def test_loopback_frame_round_trip() -> None:
    left, right = socket.socketpair()
    try:
        send_local_message(left, {"protocol": PROTOCOL_VERSION, "value": 7})
        assert recv_local_message(right) == {"protocol": PROTOCOL_VERSION, "value": 7}
    finally:
        left.close()
        right.close()
