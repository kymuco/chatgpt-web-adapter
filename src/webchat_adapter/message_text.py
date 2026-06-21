from __future__ import annotations

from typing import Any

TEXT_FIELD_KEYS = (
    "text",
    "content",
    "value",
    "caption",
    "alt_text",
    "title",
)
PART_FIELD_KEYS = (
    "parts",
    "multimodal_text",
    "items",
    "children",
)
MEDIA_KIND_BY_MIME_PREFIX = {
    "image/": "image",
    "audio/": "audio",
    "video/": "video",
}
MEDIA_KIND_MARKERS = (
    ("image_asset_pointer", "image"),
    ("audio_asset_pointer", "audio"),
    ("video_asset_pointer", "video"),
    ("asset_pointer", "media"),
    ("assetpointer", "media"),
    ("attachment", "file"),
    ("file", "file"),
)
ASSET_POINTER_KEYS = (
    "asset_pointer",
    "assetPointer",
    "image_asset_pointer",
    "audio_asset_pointer",
    "video_asset_pointer",
)


def extract_message_text(message: dict[str, Any]) -> str:
    """Best-effort text extraction from unstable ChatGPT web message payloads."""

    if not isinstance(message, dict):
        return ""

    chunks: list[str] = []
    stack: set[int] = set()
    _collect_text(message.get("content"), chunks, stack)

    if not chunks:
        _collect_text(message.get("text"), chunks, stack)
        _collect_text(message.get("multimodal_text"), chunks, stack)

    return "\n".join(chunks).strip()


def _collect_text(value: Any, chunks: list[str], stack: set[int]) -> None:
    if value is None:
        return

    if isinstance(value, str):
        _append_text(chunks, value)
        return

    if isinstance(value, (int, float, bool)):
        return

    if isinstance(value, list):
        value_id = id(value)
        if value_id in stack:
            return
        stack.add(value_id)
        try:
            for item in value:
                _collect_text(item, chunks, stack)
        finally:
            stack.discard(value_id)
        return

    if not isinstance(value, dict):
        return

    value_id = id(value)
    if value_id in stack:
        return
    stack.add(value_id)
    try:
        placeholder = _media_placeholder(value)
        if placeholder:
            _append_text(chunks, placeholder)

        for key in TEXT_FIELD_KEYS:
            if key in value:
                _collect_text(value[key], chunks, stack)

        for key in PART_FIELD_KEYS:
            if key in value:
                _collect_text(value[key], chunks, stack)
    finally:
        stack.discard(value_id)


def _append_text(chunks: list[str], value: str) -> None:
    text = value.strip()
    if not text:
        return
    if chunks and chunks[-1] == text:
        return
    chunks.append(text)


def _media_placeholder(value: dict[str, Any]) -> str | None:
    media_kind = _media_kind(value)
    if media_kind is None:
        return None

    file_name = _media_file_name(value)
    if file_name and media_kind == "file":
        return f"[file: {file_name}]"
    return f"[{media_kind}]"


def _media_kind(value: dict[str, Any]) -> str | None:
    mime_type = value.get("mime_type") or value.get("mimeType")
    if isinstance(mime_type, str):
        mime_type = mime_type.strip().lower()
        for prefix, kind in MEDIA_KIND_BY_MIME_PREFIX.items():
            if mime_type.startswith(prefix):
                return kind
        if mime_type:
            return "file"

    for key in ("type", "content_type"):
        raw_value = value.get(key)
        if not isinstance(raw_value, str):
            continue
        normalized = raw_value.strip().lower()
        for marker, kind in MEDIA_KIND_MARKERS:
            if marker in normalized:
                return kind

    for key in ASSET_POINTER_KEYS:
        if key in value:
            return _asset_pointer_kind(key)

    if _media_file_name(value) and _has_media_signal(value):
        return "file"

    return None


def _asset_pointer_kind(key: str) -> str:
    if key.startswith("image"):
        return "image"
    if key.startswith("audio"):
        return "audio"
    if key.startswith("video"):
        return "video"
    return "media"


def _media_file_name(value: dict[str, Any]) -> str | None:
    for key in ("file_name", "filename", "name"):
        file_name = value.get(key)
        if isinstance(file_name, str) and file_name.strip():
            return file_name.strip()
    return None


def _has_media_signal(value: dict[str, Any]) -> bool:
    signal_keys = (
        "mime_type",
        "mimeType",
        "file_name",
        "filename",
        *ASSET_POINTER_KEYS,
    )
    return any(key in value for key in signal_keys)
