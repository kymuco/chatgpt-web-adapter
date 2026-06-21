from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PAYLOAD_DOC = ROOT / "docs" / "raw_payload.md"
README = ROOT / "README.md"


def test_raw_payload_docs_exist_and_warn_about_instability() -> None:
    text = RAW_PAYLOAD_DOC.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "not an official" in lower_text
    assert "web backend may change" in lower_text
    assert "real ChatGPT web conversations" in text
    assert "use at your own risk" in lower_text


def test_raw_payload_docs_reference_public_api() -> None:
    text = RAW_PAYLOAD_DOC.read_text(encoding="utf-8")

    assert "PayloadBuilder" in text
    assert "validate_payload" in text
    assert "send_payload" in text
    assert "PayloadValidationError" in text
    assert "raw_payload_sent" in text


def test_readme_links_to_raw_payload_docs() -> None:
    text = README.read_text(encoding="utf-8")

    assert "docs/raw_payload.md" in text
    assert "PayloadBuilder" in text
    assert "validate_payload" in text
    assert "send_payload" in text
