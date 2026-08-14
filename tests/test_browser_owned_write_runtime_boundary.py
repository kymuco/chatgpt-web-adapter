from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/chatgpt_web_adapter/browser_owned_write_runtime.py"
EXAMPLE = ROOT / "examples/browser_owned_write_runtime.py"


def test_runtime_source_does_not_expand_private_write_or_protection_paths() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    forbidden = (
        "chat-requirements",
        "turnstile",
        "proof_token",
        "_generate_proof_token",
        "_get_chat_requirements",
        "backend-api/f/conversation",
        "backend-api/conversation",
        "chrome.debugger",
        "subprocess",
    )
    for token in forbidden:
        assert token not in source


def test_runtime_has_one_browser_native_delegation_site_and_no_retry_loop() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert source.count("return send_browser_native(") == 1
    assert "while True" not in source
    assert "for attempt" not in source


def test_operator_example_never_auto_logs_in_or_repairs_sentinel() -> None:
    source = EXAMPLE.read_text(encoding="utf-8")
    assert "auto_login=False" in source
    assert "auto_sentinel=False" in source
    assert "--send" in source
    assert "browser_login" not in source
    assert "send_browser_native" not in source
