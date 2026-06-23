from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

TAGLINE = "Python SDK for controlling existing ChatGPT web sessions without browser UI."
REQUIRED_WARNING_LINES = [
    "Not the official OpenAI API.",
    "Uses an existing ChatGPT web session.",
    "Web backend behavior may change.",
]


def test_readme_starts_with_new_positioning() -> None:
    text = README.read_text(encoding="utf-8")
    intro = text[:500]

    assert TAGLINE in intro
    for line in REQUIRED_WARNING_LINES:
        assert line in intro


def test_readme_explains_what_this_is_and_is_not() -> None:
    text = README.read_text(encoding="utf-8")
    lower_text = text.lower()

    assert "## What This Is" in text
    assert "## When It Is Useful" in text
    assert "## What This Is Not" in text
    assert "existing chatgpt web session" in lower_text
    assert "the official openai api" in lower_text
    assert "a replacement for the openai python sdk" in lower_text


def test_readme_keeps_key_existing_paths_and_workflows() -> None:
    text = README.read_text(encoding="utf-8")

    assert "from chatgpt_web_adapter import ChatGPTWebClient" in text
    assert "docs/raw_payload.md" in text
    assert "PayloadBuilder" in text
    assert "validate_payload" in text
    assert "send_payload" in text
    assert "docs/rename_compatibility.md" in text
    assert "examples/diagnose_latency.py" in text
