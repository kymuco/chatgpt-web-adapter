from __future__ import annotations

import json
import os
import socket
import struct
from pathlib import Path
from typing import Any, BinaryIO

HOST_NAME = "com.kymuco.chatgpt_web_adapter"
PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1_000_000
LOCAL_FRAME = struct.Struct("!I")
NATIVE_FRAME = struct.Struct("=I")


def default_browser_native_state_dir() -> Path:
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return root / "chatgpt-web-adapter" / "browser-native"
    if os.uname().sysname == "Darwin":
        return Path.home() / "Library" / "Application Support" / "chatgpt-web-adapter" / "browser-native"
    runtime = os.getenv("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "chatgpt-web-adapter" / "browser-native"
    return Path.home() / ".cache" / "chatgpt-web-adapter" / "browser-native"


def bridge_descriptor_path(state_dir: str | Path | None = None) -> Path:
    root = Path(state_dir) if state_dir is not None else default_browser_native_state_dir()
    return root / "bridge.json"


def encode_message(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        raise ValueError("browser-native message exceeds 1 MB safety limit")
    return body


def decode_message(body: bytes) -> dict[str, Any]:
    if len(body) > MAX_MESSAGE_BYTES:
        raise ValueError("browser-native message exceeds 1 MB safety limit")
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("browser-native message must be a JSON object")
    return payload


def _read_exact_stream(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_native_message(stream: BinaryIO) -> dict[str, Any]:
    header = _read_exact_stream(stream, NATIVE_FRAME.size)
    (size,) = NATIVE_FRAME.unpack(header)
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("native message exceeds 1 MB host limit")
    return decode_message(_read_exact_stream(stream, size))


def write_native_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    body = encode_message(payload)
    stream.write(NATIVE_FRAME.pack(len(body)))
    stream.write(body)
    stream.flush()


def _recv_exact_socket(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_local_message(sock: socket.socket) -> dict[str, Any]:
    header = _recv_exact_socket(sock, LOCAL_FRAME.size)
    (size,) = LOCAL_FRAME.unpack(header)
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("local browser-native message exceeds 1 MB safety limit")
    return decode_message(_recv_exact_socket(sock, size))


def send_local_message(sock: socket.socket, payload: dict[str, Any]) -> None:
    body = encode_message(payload)
    sock.sendall(LOCAL_FRAME.pack(len(body)) + body)
