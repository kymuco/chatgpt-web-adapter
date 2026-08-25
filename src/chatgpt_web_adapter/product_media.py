from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import mimetypes
from pathlib import Path
import tempfile
from typing import Iterator, Sequence

from .types import MediaItem, MediaSource


@dataclass(frozen=True)
class BrowserOwnedMediaMaterialization:
    """Local file snapshot supplied to the official browser page.

    Only local paths cross the Native Messaging boundary. File bytes never travel
    inside the JSON bridge message. Byte-backed inputs are materialized into a
    short-lived private temporary directory for the duration of one product turn.
    """

    paths: tuple[str, ...]
    count: int
    materialized_byte_inputs: int


def _split_media_item(item: MediaItem) -> tuple[MediaSource, str | None]:
    if isinstance(item, tuple):
        if len(item) != 2:
            raise ValueError("media tuple must be (source, mime_type)")
        source, mime_type = item
        if mime_type is not None and (not isinstance(mime_type, str) or not mime_type.strip()):
            raise ValueError("media mime_type must be a non-empty string or None")
        return source, mime_type.strip() if isinstance(mime_type, str) else None
    return item, None


def _suffix_for_mime_type(mime_type: str | None) -> str:
    if not mime_type:
        return ".bin"
    guessed = mimetypes.guess_extension(mime_type, strict=False)
    return guessed if isinstance(guessed, str) and guessed else ".bin"


def _read_byte_source(source: bytes | bytearray) -> bytes:
    if isinstance(source, bytes):
        return source
    return bytes(source)


@contextmanager
def materialize_browser_owned_media(
    media: Sequence[MediaItem] | None,
) -> Iterator[BrowserOwnedMediaMaterialization]:
    """Resolve rich-input media to stable local paths for one browser-owned turn.

    Existing path inputs are resolved and validated without copying. In-memory
    bytes are snapshotted to temporary files, avoiding Native Messaging payload
    inflation and keeping the official page responsible for the actual upload and
    protected conversation write.
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
        materialized = 0

        for index, item in enumerate(items):
            source, mime_type = _split_media_item(item)
            if isinstance(source, (bytes, bytearray)):
                payload = _read_byte_source(source)
                if not payload:
                    raise ValueError(f"media[{index}] byte source is empty")
                target = root / f"attachment-{index}{_suffix_for_mime_type(mime_type)}"
                target.write_bytes(payload)
                paths.append(str(target.resolve(strict=True)))
                materialized += 1
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
            paths.append(str(path))

        yield BrowserOwnedMediaMaterialization(
            paths=tuple(paths),
            count=len(paths),
            materialized_byte_inputs=materialized,
        )
