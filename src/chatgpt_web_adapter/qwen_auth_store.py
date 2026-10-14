"""Opt-in, local-only Qwen session persistence outside the checkout."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .qwen_http import QwenHttpCredentials

AUTH_FILE = (
    Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".config"))
    / "chatgpt-web-adapter"
    / "qwen_auth.dat"
)


class QwenAuthStoreError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi(value: bytes, *, encrypt: bool) -> bytes:
    source = ctypes.create_string_buffer(value)
    incoming = _Blob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    if encrypt:
        func = crypt.CryptProtectData
        args: tuple[Any, ...] = (
            ctypes.byref(incoming),
            "CWA Qwen web credentials",
            None,
            None,
            None,
            0,
            ctypes.byref(outgoing),
        )
    else:
        func = crypt.CryptUnprotectData
        args = (
            ctypes.byref(incoming),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(outgoing),
        )
    if not func(*args):
        raise QwenAuthStoreError("QWEN_DPAPI_OPERATION_FAILED")
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def save_qwen_credentials(
    credentials: QwenHttpCredentials, *, path: Path = AUTH_FILE
) -> None:
    payload = json.dumps(
        {
            "schema": 1,
            "access_token": credentials.access_token,
            "cookies": credentials.cookies,
            "expires_at": credentials.expires_at,
        }
    ).encode("utf-8")
    if os.name == "nt":
        value = b"DPAPI1:" + base64.b64encode(_dpapi(payload, encrypt=True))
    else:
        # Non-Windows fallback: an explicitly private, per-user POSIX file.
        value = b"JSON1:" + payload
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.parent.chmod(0o700)
    fd, temp = tempfile.mkstemp(prefix=".qwen-auth-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load_qwen_credentials(*, path: Path = AUTH_FILE) -> QwenHttpCredentials:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"DPAPI1:") and os.name == "nt":
            value = _dpapi(base64.b64decode(raw[7:]), encrypt=False)
        elif raw.startswith(b"JSON1:") and os.name != "nt":
            value = raw[6:]
        else:
            raise QwenAuthStoreError("QWEN_AUTH_STORE_FORMAT_MISMATCH")
        body = json.loads(value)
        if not isinstance(body, dict) or body.get("schema") != 1:
            raise QwenAuthStoreError("QWEN_AUTH_STORE_SCHEMA_MISMATCH")
        return QwenHttpCredentials(
            access_token=body["access_token"],
            cookies=body.get("cookies", {}),
            expires_at=body.get("expires_at"),
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise QwenAuthStoreError(
            "QWEN_AUTH_UNAVAILABLE: import from authorized Chrome or log in again"
        ) from error
