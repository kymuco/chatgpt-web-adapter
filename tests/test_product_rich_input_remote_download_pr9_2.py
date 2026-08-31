from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

import chatgpt_web_adapter.product_media as product_media
from chatgpt_web_adapter.product_media import browser_owned_media_scope


class _Headers:
    def __init__(self, *, content_length: int | None = None) -> None:
        self._content_length = content_length

    def get_content_type(self):
        return "application/octet-stream"

    def get(self, name, default=None):
        if name.lower() == "content-length" and self._content_length is not None:
            return str(self._content_length)
        return default


class _StreamingResponse:
    def __init__(
        self,
        chunks: list[bytes],
        url: str,
        *,
        content_length: int | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self._url = url
        self.headers = _Headers(content_length=content_length)
        self.read_sizes: list[int] = []
        self.read1_sizes: list[int] = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def _take(self, size: int) -> bytes:
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if size >= 0 and len(chunk) > size:
            self._chunks.insert(0, chunk[size:])
            return chunk[:size]
        return chunk

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self._take(size)

    def read1(self, size=-1):
        self.read1_sizes.append(size)
        return self._take(size)

    def close(self):
        self.closed = True

    def geturl(self):
        return self._url


class _BlockingReadResponse:
    def __init__(self, url: str) -> None:
        self._url = url
        self.headers = _Headers()
        self.read_started = threading.Event()
        self.read_released = threading.Event()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read1(self, size=-1):
        self.read_started.set()
        if not self.read_released.wait(timeout=5.0):
            raise AssertionError("deadline abort did not interrupt the blocking body read")
        raise OSError("response closed by deadline abort")

    def close(self):
        self.closed = True
        self.read_released.set()

    def geturl(self):
        return self._url


def test_remote_media_streams_to_disk_in_bounded_read1_steps(monkeypatch):
    source = "https://example.test/files/blob.bin"
    response = _StreamingResponse([b"abc", b"def", b"ghi"], source, content_length=9)

    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_CHUNK_BYTES", 4)

    with browser_owned_media_scope([source]) as materialization:
        generated = Path(materialization.paths[0])
        assert generated.read_bytes() == b"abcdefghi"
        assert generated.name == "blob.bin"
        assert materialization.materialized_byte_inputs == 1

    assert response.read1_sizes
    assert response.read_sizes == []
    assert all(size > 0 for size in response.read1_sizes)
    assert max(response.read1_sizes) <= 4
    assert not generated.exists()


def test_remote_media_rejects_oversized_content_length_before_read(monkeypatch):
    source = "https://example.test/files/too-large.bin"
    response = _StreamingResponse(
        [b"should-not-be-read"],
        source,
        content_length=9,
    )
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_MAX_BYTES", 8)

    with pytest.raises(ValueError, match=r"exceeds 8 bytes"):
        with browser_owned_media_scope([source]):
            pass
    assert response.read1_sizes == []
    assert response.read_sizes == []


def test_remote_media_rejects_stream_that_exceeds_actual_byte_cap(monkeypatch):
    source = "https://example.test/files/chunked.bin"
    response = _StreamingResponse([b"1234", b"5678", b"9"], source)
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_MAX_BYTES", 8)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_CHUNK_BYTES", 4)

    with pytest.raises(ValueError, match=r"exceeds 8 bytes"):
        with browser_owned_media_scope([source]):
            pass
    assert response.read1_sizes == [4, 4, 1]
    assert response.read_sizes == []


def test_remote_media_enforces_total_deadline_while_data_keeps_arriving(monkeypatch):
    source = "https://example.test/files/slow-stream.bin"
    response = _StreamingResponse([b"a", b"b", b"c"], source)
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS", 1.0)

    clock = {"value": 0.0}
    original_read_step = product_media._read_response_step

    def fake_monotonic():
        return clock["value"]

    def advancing_read_step(response_obj, read_size):
        clock["value"] += 0.4
        return original_read_step(response_obj, read_size)

    monkeypatch.setattr(product_media.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(product_media, "_read_response_step", advancing_read_step)

    with pytest.raises(ValueError, match="total download deadline"):
        with browser_owned_media_scope([source]):
            pass
    assert response.read1_sizes


def test_remote_media_absolute_deadline_interrupts_blocking_body_read(monkeypatch):
    source = "https://example.test/files/drip-feed.bin"
    response = _BlockingReadResponse(source)
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS", 0.05)

    started = time.monotonic()
    with pytest.raises(ValueError, match="total download deadline"):
        with browser_owned_media_scope([source]):
            pass
    elapsed = time.monotonic() - started

    assert response.read_started.is_set()
    assert response.read_released.is_set()
    assert response.closed is True
    assert elapsed < 1.0


def test_remote_media_absolute_deadline_includes_response_open(monkeypatch):
    source = "https://example.test/files/slow-open.bin"
    response = _StreamingResponse([b"x"], source, content_length=1)
    open_started = threading.Event()
    release_open = threading.Event()

    def blocking_urlopen(request, *, timeout):
        open_started.set()
        if not release_open.wait(timeout=2.0):
            raise AssertionError("absolute deadline did not release the response-open caller")
        return response

    monkeypatch.setattr(product_media, "urlopen", blocking_urlopen)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS", 0.05)

    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match="total download deadline"):
            with browser_owned_media_scope([source]):
                pass
    finally:
        release_open.set()
    elapsed = time.monotonic() - started

    assert open_started.is_set()
    assert elapsed < 1.0

    cleanup_deadline = time.monotonic() + 1.0
    while not response.closed and time.monotonic() < cleanup_deadline:
        time.sleep(0.01)
    assert response.closed is True


def test_remote_media_generic_read_fallback_consumes_one_byte_per_deadline_check(monkeypatch):
    source = "https://example.test/files/fallback.bin"

    class _ReadOnlyResponse(_StreamingResponse):
        read1 = None

    response = _ReadOnlyResponse([b"abc"], source, content_length=3)
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)

    with browser_owned_media_scope([source]) as materialization:
        assert Path(materialization.paths[0]).read_bytes() == b"abc"

    assert response.read1_sizes == []
    assert response.read_sizes == [1, 1, 1, 1]


def test_remote_media_source_code_has_cancellable_absolute_deadline():
    source = Path(product_media.__file__).read_text(encoding="utf-8")
    assert "response.read()" not in source
    assert "response.read(read_size)" not in source
    assert "read1(read_size)" in source
    assert "_open_response_with_absolute_deadline(" in source
    assert "completed.wait(remaining)" in source
    assert "daemon=True" in source
    assert "threading.Timer(remaining, abort_at_deadline)" in source
    assert "_abort_response_read(response)" in source
    assert "shutdown(socket.SHUT_RDWR)" in source
    assert "_REMOTE_FETCH_MAX_BYTES" in source
    assert "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS" in source
