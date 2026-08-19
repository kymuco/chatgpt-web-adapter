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

PRIMARY_PRODUCT_EXAMPLES = ["product_runtime.py"]
COMPATIBILITY_EXAMPLES = [
    "basic_send.py",
    "continue_saved.py",
    "attach_existing.py",
    "read_messages.py",
    "status_polling.py",
]
EXPERIMENTAL_EXAMPLES = [
    "approve_tools.py",
    "raw_payload.py",
    "github_auto_approve.py",
]
RESEARCH_DIAGNOSTIC_EXAMPLES = [
    "browser_native_send.py",
    "diagnose_latency.py",
    "watch_conversation.py",
]

PUBLIC_API_EXAMPLES = [
    *REQUIRED_EXAMPLES,
    "browser_native_send.py",
    "product_runtime.py",
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


def test_public_examples_use_public_package_imports_only() -> None:
    for filename in PUBLIC_API_EXAMPLES:
        path = EXAMPLES / filename
        assert path.is_file()
        text = path.read_text(encoding="utf-8")

        assert "from chatgpt_web_adapter." not in text
        assert "import chatgpt_web_adapter." not in text


def test_primary_product_example_uses_runtime_capabilities_and_provenance() -> None:
    text = (EXAMPLES / "product_runtime.py").read_text(encoding="utf-8")

    assert "assemble_product_runtime" in text
    assert "runtime.capabilities()" in text
    assert "send_text_observed" in text
    assert "execution.provenance.to_dict()" in text
    assert '"surface": "PRIMARY_PRODUCTION"' in text
    assert "auto_sentinel" not in text


def test_readme_classifies_example_groups_without_deleting_history() -> None:
    text = README.read_text(encoding="utf-8")

    assert "Primary production example:" in text
    assert "Compatibility examples:" in text
    assert "Experimental examples:" in text
    assert "Research/diagnostic examples:" in text
    for filename in (
        *PRIMARY_PRODUCT_EXAMPLES,
        *COMPATIBILITY_EXAMPLES,
        *EXPERIMENTAL_EXAMPLES,
        *RESEARCH_DIAGNOSTIC_EXAMPLES,
    ):
        assert f"examples/{filename}" in text


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
