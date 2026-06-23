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
    assert "package rename is complete" in text.lower()
    assert "not supported anymore" in text.lower()


def test_rename_doc_describes_current_canonical_import_only() -> None:
    text = DOC.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "supported import:" in lower_text
    assert "from chatgpt_web_adapter import chatgptwebclient" in lower_text
    assert "old `webchat_adapter` import" in lower_text
    assert "not supported anymore" in lower_text


def test_readme_links_to_rename_compatibility_plan() -> None:
    text = README.read_text(encoding="utf-8")

    assert "docs/rename_compatibility.md" in text
    assert "chatgpt-web-adapter" in text
    assert "chatgpt_web_adapter" in text
    assert "repository: `chatgpt-web-adapter`" in text


def test_package_metadata_uses_renamed_distribution() -> None:
    text = PYPROJECT.read_text(encoding="utf-8")

    assert 'name = "chatgpt-web-adapter"' in text
