from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "rename_compatibility.md"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"


def test_rename_compatibility_doc_exists_and_names_future_target() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "chatgpt-web-adapter" in text
    assert "chatgpt_web_adapter" in text
    assert "webchat_adapter" in text
    assert "compatibility import" in text.lower()


def test_rename_plan_is_explicitly_future_only() -> None:
    text = DOC.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "the rename is planned for a future milestone" in lower_text
    assert "only `webchat_adapter` exists" in lower_text
    assert "that future import is not available yet." in lower_text
    assert "for now, use `webchat_adapter`." in lower_text


def test_readme_links_to_rename_compatibility_plan() -> None:
    text = README.read_text(encoding="utf-8")

    assert "docs/rename_compatibility.md" in text
    assert "chatgpt-web-adapter" in text
    assert "chatgpt_web_adapter" in text
    assert "webchat_adapter" in text


def test_package_metadata_is_not_renamed_yet() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")

    assert 'name = "webchat-adapter"' in text
    assert 'name = "chatgpt-web-adapter"' not in text
