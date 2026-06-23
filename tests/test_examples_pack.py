from __future__ import annotations

import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
README = ROOT / "README.md"

REQUIRED_EXAMPLES = [
    "basic_send.py",
    "continue_saved.py",
    "attach_existing.py",
    "read_messages.py",
    "status_polling.py",
    "approve_tools.py",
    "raw_payload.py",
]


def test_examples_pack_files_exist() -> None:
    for filename in REQUIRED_EXAMPLES:
        assert (EXAMPLES / filename).is_file()


def test_examples_compile() -> None:
    for path in sorted(EXAMPLES.glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def test_required_examples_use_script_entrypoint() -> None:
    for filename in REQUIRED_EXAMPLES:
        text = (EXAMPLES / filename).read_text(encoding="utf-8")

        assert "def main() -> None:" in text
        assert 'if __name__ == "__main__":' in text
        assert "main()" in text


def test_examples_use_public_package_imports_only() -> None:
    for path in sorted(EXAMPLES.glob("*.py")):
        text = path.read_text(encoding="utf-8")

        assert "from chatgpt_web_adapter." not in text
        assert "import chatgpt_web_adapter." not in text


def test_dangerous_examples_warn_about_risk() -> None:
    approve_text = (EXAMPLES / "approve_tools.py").read_text(encoding="utf-8").lower()
    raw_payload_text = (EXAMPLES / "raw_payload.py").read_text(encoding="utf-8").lower()

    assert "approves pending tool actions" in approve_text
    assert "review the target conversation" in approve_text
    assert "not the official openai api" in raw_payload_text
    assert "web backend behavior may change" in raw_payload_text
    assert "creates real" in raw_payload_text


def test_readme_links_to_examples_pack() -> None:
    text = README.read_text(encoding="utf-8")

    for filename in REQUIRED_EXAMPLES:
        assert f"examples/{filename}" in text
