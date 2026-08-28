from __future__ import annotations

from pathlib import Path

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if size >= 0 and len(chunk) > size:
            self._chunks.insert(0, chunk[size:])
            return chunk[:size]
        return chunk

    def geturl(self):
        return self._url


def test_remote_media_streams_to_disk_in_bounded_reads(monkeypatch):
    source = "https://example.test/files/blob.bin"
    response = _StreamingResponse([b"abc", b"def", b"ghi"], source, content_length=9)

    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_CHUNK_BYTES", 4)

    with browser_owned_media_scope([source]) as materialization:
        generated = Path(materialization.paths[0])
        assert generated.read_bytes() == b"abcdefghi"
        assert generated.name == "blob.bin"
        assert materialization.materialized_byte_inputs == 1

    assert response.read_sizes
    assert all(size > 0 for size in response.read_sizes)
    assert max(response.read_sizes) <= 4
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
    assert response.read_sizes == [4, 4, 1]


def test_remote_media_enforces_total_deadline_while_data_keeps_arriving(monkeypatch):
    source = "https://example.test/files/slow-stream.bin"
    response = _StreamingResponse([b"a", b"b", b"c"], source)
    monkeypatch.setattr(product_media, "urlopen", lambda request, *, timeout: response)
    monkeypatch.setattr(product_media, "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS", 1.0)

    clock = {"value": 0.0}

    def fake_monotonic():
        clock["value"] += 0.4
        return clock["value"]

    monkeypatch.setattr(product_media.time, "monotonic", fake_monotonic)

    with pytest.raises(ValueError, match="total download deadline"):
        with browser_owned_media_scope([source]):
            pass
    assert response.read_sizes


def test_remote_media_source_code_has_no_unbounded_response_read():
    source = Path(product_media.__file__).read_text(encoding="utf-8")
    assert "response.read()" not in source
    assert "response.read(read_size)" in source
    assert "_REMOTE_FETCH_MAX_BYTES" in source
    assert "_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS" in source
