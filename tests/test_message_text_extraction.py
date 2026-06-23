from __future__ import annotations

from chatgpt_web_adapter.message_text import extract_message_text


def test_extract_message_text_reads_content_text() -> None:
    assert extract_message_text({"content": {"text": "Hello"}}) == "Hello"


def test_extract_message_text_reads_string_parts() -> None:
    message = {"content": {"parts": ["Hello", "world"]}}

    assert extract_message_text(message) == "Hello\nworld"


def test_extract_message_text_reads_structured_text_part() -> None:
    message = {"content": {"parts": [{"type": "text", "text": "Hello"}]}}

    assert extract_message_text(message) == "Hello"


def test_extract_message_text_reads_structured_known_text_fields() -> None:
    message = {
        "content": {
            "parts": [
                {"caption": "Caption"},
                {"alt_text": "Alt text"},
                {"title": "Title"},
                {"value": "Value"},
            ]
        }
    }

    assert extract_message_text(message) == "Caption\nAlt text\nTitle\nValue"


def test_extract_message_text_reads_multimodal_text_with_image_placeholder() -> None:
    message = {
        "content": {
            "content_type": "multimodal_text",
            "parts": [
                {"type": "text", "text": "Look"},
                {"type": "image_asset_pointer"},
            ],
        }
    }

    assert extract_message_text(message) == "Look\n[image]"


def test_extract_message_text_reads_multimodal_text_string() -> None:
    message = {"content": {"multimodal_text": "Look at this"}}

    assert extract_message_text(message) == "Look at this"


def test_extract_message_text_reads_multimodal_text_list() -> None:
    message = {"content": {"multimodal_text": [{"text": "A"}, {"text": "B"}]}}

    assert extract_message_text(message) == "A\nB"


def test_extract_message_text_emits_file_placeholder_with_filename() -> None:
    message = {"content": {"parts": [{"type": "file", "file_name": "report.pdf"}]}}

    assert extract_message_text(message) == "[file: report.pdf]"


def test_extract_message_text_emits_image_placeholder_from_mime_type() -> None:
    message = {"content": {"parts": [{"mime_type": "image/png"}]}}

    assert extract_message_text(message) == "[image]"


def test_extract_message_text_emits_audio_and_video_placeholders() -> None:
    audio = {"content": {"parts": [{"mime_type": "audio/mpeg"}]}}
    video = {"content": {"parts": [{"mime_type": "video/mp4"}]}}

    assert extract_message_text(audio) == "[audio]"
    assert extract_message_text(video) == "[video]"


def test_extract_message_text_emits_media_placeholder_from_asset_pointer_key() -> None:
    message = {"content": {"parts": [{"asset_pointer": "file-service://asset"}]}}

    assert extract_message_text(message) == "[media]"


def test_extract_message_text_unknown_dict_returns_empty_string() -> None:
    message = {"content": {"parts": [{"unknown": {"nested": 1}}]}}

    assert extract_message_text(message) == ""


def test_extract_message_text_reads_content_as_string() -> None:
    assert extract_message_text({"content": "tool output"}) == "tool output"


def test_extract_message_text_reads_content_as_list() -> None:
    assert extract_message_text({"content": ["A", {"text": "B"}]}) == "A\nB"


def test_extract_message_text_empty_messages_return_empty_string() -> None:
    assert extract_message_text({}) == ""
    assert extract_message_text({"content": None}) == ""
    assert extract_message_text({"content": {"parts": []}}) == ""


def test_extract_message_text_tool_and_system_shapes_do_not_crash() -> None:
    tool_message = {"author": {"role": "tool"}, "content": {"result": {"ok": True}}}
    system_message = {"author": {"role": "system"}, "content": None}

    assert extract_message_text(tool_message) == ""
    assert extract_message_text(system_message) == ""


def test_extract_message_text_reads_tool_text_when_present() -> None:
    message = {"author": {"role": "tool"}, "content": {"text": "Tool output"}}

    assert extract_message_text(message) == "Tool output"


def test_extract_message_text_deduplicates_adjacent_duplicate_chunks() -> None:
    message = {"content": {"text": "Hello", "parts": ["Hello", "world"]}}

    assert extract_message_text(message) == "Hello\nworld"


def test_extract_message_text_does_not_recurse_forever_on_cycles() -> None:
    content: dict = {"text": "Hello"}
    content["parts"] = [content]

    assert extract_message_text({"content": content}) == "Hello"


def test_extract_message_text_allows_reused_structured_objects_in_sibling_positions() -> None:
    part = {"text": "Repeated"}
    message = {"content": {"parts": [part, part]}}

    assert extract_message_text(message) == "Repeated"
