from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import mimetypes
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile
import time
from typing import Iterator, Sequence
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from .types import MediaItem, MediaSource


_BROWSER_OWNED_MEDIA_PATHS: ContextVar[tuple[str, ...] | None] = ContextVar(
    "cwa_browser_owned_media_paths",
    default=None,
)
_DATA_URI_RE = re.compile(
    r"^data:([^;,]+)?(?:;[^,;]+)*;base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_REMOTE_FETCH_TIMEOUT_SECONDS = 30.0
_REMOTE_FETCH_TOTAL_DEADLINE_SECONDS = 30.0
_REMOTE_FETCH_MAX_BYTES = 512 * 1024 * 1024
_REMOTE_FETCH_CHUNK_BYTES = 1024 * 1024
_REMOTE_PREFIX_BYTES = 16


@dataclass(frozen=True)
class BrowserOwnedMediaMaterialization:
    """Local file snapshot supplied to the official browser page.

    Only local paths cross the Native Messaging boundary. File bytes never travel
    inside the JSON bridge message. Byte-backed, data-URI, HTTP(S), and explicit
    filename-override inputs are materialized into a short-lived private temporary
    directory for the duration of one product turn.
    """

    paths: tuple[str, ...]
    count: int
    materialized_byte_inputs: int


def _normalize_media_filename(filename: str | None) -> str | None:
    if filename is None:
        return None
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("media filename must be a non-empty string or None")
    filename = filename.strip()
    windows_path = PureWindowsPath(filename)
    if (
        filename in {".", ".."}
        or Path(filename).name != filename
        or windows_path.name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise ValueError("media filename must be a basename without path components")
    return filename


def _split_media_item(item: MediaItem) -> tuple[MediaSource, str | None]:
    """Preserve the historical MediaItem tuple contract: (source, filename)."""

    if isinstance(item, tuple):
        if len(item) != 2:
            raise ValueError("media tuple must be (source, filename)")
        source, filename = item
        return source, _normalize_media_filename(filename)
    return item, None


def _byte_source_default_suffix(payload: bytes) -> str:
    """Keep unnamed image bytes classifiable without inventing MIME tuple semantics."""

    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(payload) >= 12 and payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def _read_byte_source(source: bytes | bytearray) -> bytes:
    if isinstance(source, bytes):
        return source
    return bytes(source)


def _decode_data_uri(source: str, *, index: int) -> tuple[bytes, str | None]:
    match = _DATA_URI_RE.match(source)
    if not match:
        raise ValueError(f"media[{index}] data URI must use base64 encoding")
    try:
        payload = base64.b64decode(match.group(2))
    except Exception as error:
        raise ValueError(f"media[{index}] data URI base64 is invalid") from error
    if not payload:
        raise ValueError(f"media[{index}] data URI payload is empty")
    mime_type = match.group(1).strip().lower() if match.group(1) else None
    return payload, mime_type


def _response_content_length(response: object) -> int | None:
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    raw = getter("Content-Length")
    if raw is None:
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _set_response_read_timeout(response: object, timeout_seconds: float) -> None:
    """Best-effort tighten the standard urllib socket to the remaining deadline."""

    timeout_seconds = max(0.001, float(timeout_seconds))
    fp = getattr(response, "fp", None)
    candidates = (
        getattr(getattr(fp, "raw", None), "_sock", None),
        getattr(fp, "_sock", None),
    )
    for candidate in candidates:
        setter = getattr(candidate, "settimeout", None)
        if callable(setter):
            setter(timeout_seconds)
            return


def _url_basename(source: str) -> str | None:
    try:
        basename = unquote(Path(urlparse(source).path).name)
    except (TypeError, ValueError):
        return None
    try:
        return _normalize_media_filename(basename) if basename else None
    except ValueError:
        return None


def _materialized_name(
    *,
    payload: bytes,
    index: int,
    filename: str | None,
    source_name: str | None = None,
    mime_type: str | None = None,
) -> str:
    if filename:
        return filename
    if source_name:
        if Path(source_name).suffix:
            return source_name
        guessed = mimetypes.guess_extension(mime_type or "", strict=False)
        return f"{source_name}{guessed}" if guessed else source_name
    guessed = mimetypes.guess_extension(mime_type or "", strict=False)
    suffix = guessed or _byte_source_default_suffix(payload)
    return f"attachment-{index}{suffix}"


def _download_http_source_to_file(
    source: str,
    *,
    index: int,
    root: Path,
    filename: str | None,
) -> Path:
    """Stream one remote source directly to disk under byte and wall-clock bounds."""

    started_at = time.monotonic()
    deadline_at = started_at + _REMOTE_FETCH_TOTAL_DEADLINE_SECONDS
    try:
        request = Request(source, headers={"User-Agent": "Mozilla/5.0"})
        response_context = urlopen(request, timeout=_REMOTE_FETCH_TIMEOUT_SECONDS)
    except Exception as error:
        raise ValueError(f"media[{index}] URL source is unavailable") from error

    try:
        with response_context as response:
            if time.monotonic() >= deadline_at:
                raise ValueError(f"media[{index}] URL source exceeded total download deadline")

            declared_length = _response_content_length(response)
            if declared_length is not None and declared_length > _REMOTE_FETCH_MAX_BYTES:
                raise ValueError(
                    f"media[{index}] URL source exceeds {_REMOTE_FETCH_MAX_BYTES} bytes"
                )

            content_type = response.headers.get_content_type() if response.headers else None
            final_url = response.geturl() or source
            target_dir = root / f"item-{index}"
            target_dir.mkdir()

            total_bytes = 0
            prefix = bytearray()
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target_dir,
                prefix=".remote-",
                suffix=".part",
                delete=False,
            ) as staging_file:
                staging_path = Path(staging_file.name)
                while True:
                    remaining = deadline_at - time.monotonic()
                    if remaining <= 0:
                        raise ValueError(
                            f"media[{index}] URL source exceeded total download deadline"
                        )
                    _set_response_read_timeout(
                        response,
                        min(_REMOTE_FETCH_TIMEOUT_SECONDS, remaining),
                    )
                    read_size = min(
                        _REMOTE_FETCH_CHUNK_BYTES,
                        _REMOTE_FETCH_MAX_BYTES - total_bytes + 1,
                    )
                    chunk = response.read(read_size)
                    if not chunk:
                        break
                    if not isinstance(chunk, (bytes, bytearray)):
                        raise ValueError(f"media[{index}] URL source returned non-byte data")
                    total_bytes += len(chunk)
                    if total_bytes > _REMOTE_FETCH_MAX_BYTES:
                        raise ValueError(
                            f"media[{index}] URL source exceeds {_REMOTE_FETCH_MAX_BYTES} bytes"
                        )
                    if len(prefix) < _REMOTE_PREFIX_BYTES:
                        needed = _REMOTE_PREFIX_BYTES - len(prefix)
                        prefix.extend(chunk[:needed])
                    staging_file.write(chunk)
                    if time.monotonic() >= deadline_at:
                        raise ValueError(
                            f"media[{index}] URL source exceeded total download deadline"
                        )

            if total_bytes == 0:
                raise ValueError(f"media[{index}] URL source is empty")

            target_name = _materialized_name(
                payload=bytes(prefix),
                index=index,
                filename=filename,
                source_name=_url_basename(final_url),
                mime_type=content_type,
            )
            target = target_dir / target_name
            try:
                staging_path.replace(target)
            except OSError as error:
                raise ValueError(f"media[{index}] URL materialization failed") from error
            return target.resolve(strict=True)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"media[{index}] URL source is unavailable") from error


def _write_materialized_bytes(
    payload: bytes,
    *,
    root: Path,
    index: int,
    filename: str,
) -> Path:
    target_dir = root / f"item-{index}"
    target_dir.mkdir()
    target = target_dir / filename
    try:
        target.write_bytes(payload)
    except OSError as error:
        raise ValueError(f"media[{index}] byte materialization failed") from error
    return target.resolve(strict=True)


def _copy_with_filename(source: Path, *, root: Path, index: int, filename: str) -> Path:
    target_dir = root / f"item-{index}"
    target_dir.mkdir()
    target = target_dir / filename
    try:
        shutil.copyfile(source, target)
    except OSError as error:
        raise ValueError(f"media[{index}] filename materialization failed") from error
    return target.resolve(strict=True)


@contextmanager
def materialize_browser_owned_media(
    media: Sequence[MediaItem] | None,
) -> Iterator[BrowserOwnedMediaMaterialization]:
    """Resolve rich-input MediaItem values to stable local paths for one turn.

    The established public source forms remain valid: local paths, raw bytes,
    base64 ``data:`` URIs, and HTTP(S) URLs. Non-path sources are snapshotted into
    the private per-turn directory before browser delegation, so the Native
    Messaging boundary remains path-only. A tuple keeps the established
    ``(source, filename)`` meaning for every source form.
    """

    if media is None:
        yield BrowserOwnedMediaMaterialization((), 0, 0)
        return
    if isinstance(media, (str, bytes, bytearray, Path)):
        raise TypeError("media must be a sequence of MediaItem values")

    items = list(media)
    if not items:
        yield BrowserOwnedMediaMaterialization((), 0, 0)
        return

    with tempfile.TemporaryDirectory(prefix="cwa-pr9-2-media-") as temp_dir:
        root = Path(temp_dir)
        paths: list[str] = []
        materialized_byte_inputs = 0

        for index, item in enumerate(items):
            source, filename = _split_media_item(item)

            if isinstance(source, (bytes, bytearray)):
                payload = _read_byte_source(source)
                if not payload:
                    raise ValueError(f"media[{index}] byte source is empty")
                target_name = _materialized_name(
                    payload=payload,
                    index=index,
                    filename=filename,
                )
                target = _write_materialized_bytes(
                    payload,
                    root=root,
                    index=index,
                    filename=target_name,
                )
                paths.append(str(target))
                materialized_byte_inputs += 1
                continue

            if isinstance(source, str) and source.startswith("data:"):
                payload, mime_type = _decode_data_uri(source, index=index)
                target_name = _materialized_name(
                    payload=payload,
                    index=index,
                    filename=filename,
                    mime_type=mime_type,
                )
                target = _write_materialized_bytes(
                    payload,
                    root=root,
                    index=index,
                    filename=target_name,
                )
                paths.append(str(target))
                materialized_byte_inputs += 1
                continue

            if isinstance(source, str) and source.startswith(("http://", "https://")):
                target = _download_http_source_to_file(
                    source,
                    index=index,
                    root=root,
                    filename=filename,
                )
                paths.append(str(target))
                materialized_byte_inputs += 1
                continue

            if not isinstance(source, (str, Path)) and not hasattr(source, "__fspath__"):
                raise TypeError(
                    f"media[{index}] source must be bytes, bytearray, str, Path, or PathLike"
                )
            try:
                path = Path(source).expanduser().resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise ValueError(f"media[{index}] path is unavailable") from error
            if not path.is_file():
                raise ValueError(f"media[{index}] path must reference a regular file")

            if filename is None or filename == path.name:
                paths.append(str(path))
            else:
                paths.append(
                    str(_copy_with_filename(path, root=root, index=index, filename=filename))
                )

        yield BrowserOwnedMediaMaterialization(
            paths=tuple(paths),
            count=len(paths),
            materialized_byte_inputs=materialized_byte_inputs,
        )


@contextmanager
def browser_owned_media_scope(
    media: Sequence[MediaItem] | None,
) -> Iterator[BrowserOwnedMediaMaterialization]:
    """Bind one rich-input materialization to the current execution context.

    BrowserOwnedProductWriteRuntime itself remains unchanged. Deep inside that
    proven runtime, ``send_browser_native`` reads this execution-local scope and
    forwards only the local paths to the official-page provider. Parallel turns
    in other threads/tasks cannot observe the binding.
    """

    if _BROWSER_OWNED_MEDIA_PATHS.get() is not None:
        raise RuntimeError("nested browser-owned media scopes are not supported")
    with materialize_browser_owned_media(media) as materialization:
        token = _BROWSER_OWNED_MEDIA_PATHS.set(materialization.paths)
        try:
            yield materialization
        finally:
            _BROWSER_OWNED_MEDIA_PATHS.reset(token)


def current_browser_owned_attachment_paths() -> tuple[str, ...] | None:
    """Return the current execution-local attachment paths, if a scope is active."""

    return _BROWSER_OWNED_MEDIA_PATHS.get()
