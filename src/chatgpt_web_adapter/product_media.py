from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import shutil
import tempfile
from typing import Iterator, Sequence

from .types import MediaItem, MediaSource


_BROWSER_OWNED_MEDIA_PATHS: ContextVar[tuple[str, ...] | None] = ContextVar(
    "cwa_browser_owned_media_paths",
    default=None,
)


@dataclass(frozen=True)
class BrowserOwnedMediaMaterialization:
    """Local file snapshot supplied to the official browser page.

    Only local paths cross the Native Messaging boundary. File bytes never travel
    inside the JSON bridge message. Byte-backed inputs and explicit filename
    overrides are materialized into a short-lived private temporary directory for
    the duration of one product turn.
    """

    paths: tuple[str, ...]
    count: int
    materialized_byte_inputs: int


def _split_media_item(item: MediaItem) -> tuple[MediaSource, str | None]:
    """Preserve the historical MediaItem tuple contract: (source, filename)."""

    if isinstance(item, tuple):
        if len(item) != 2:
            raise ValueError("media tuple must be (source, filename)")
        source, filename = item
        if filename is not None:
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
        return source, filename
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
    """Resolve rich-input media to stable local paths for one browser-owned turn.

    Existing path inputs without a filename override are resolved and validated
    without copying. In-memory bytes are snapshotted to temporary files. A tuple
    keeps the established ``(source, filename)`` meaning: the requested basename
    is preserved for both byte-backed and path-backed sources, so the official
    page sees the same filename contract as the legacy upload path.
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
                target_dir = root / f"item-{index}"
                target_dir.mkdir()
                target_name = filename or f"attachment-{index}{_byte_source_default_suffix(payload)}"
                target = target_dir / target_name
                try:
                    target.write_bytes(payload)
                except OSError as error:
                    raise ValueError(f"media[{index}] byte materialization failed") from error
                paths.append(str(target.resolve(strict=True)))
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
