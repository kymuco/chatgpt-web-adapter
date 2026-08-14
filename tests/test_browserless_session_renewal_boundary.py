from __future__ import annotations

from pathlib import Path

import chatgpt_web_adapter.browserless_session_renewal_replication as subject


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src" / "chatgpt_web_adapter" / "browserless_session_renewal_replication.py"
EXAMPLE = ROOT / "examples" / "browserless_session_renewal_replication.py"


def test_replication_layer_has_no_product_write_or_browser_native_turn() -> None:
    text = MODULE.read_text(encoding="utf-8")
    lowered = text.lower()
    forbidden = (
        "send_browser_native(",
        "browsernativeturnprovider(",
        "chat_requirements_url",
        "_get_chat_requirements(",
        "_generate_proof_token(",
        "turnstile",
        "execute_native_turn",
    )
    for marker in forbidden:
        assert marker not in lowered


def test_real_access_expiry_remains_deferred_and_operator_probe_is_bounded() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    example_text = EXAMPLE.read_text(encoding="utf-8")
    assert subject.REAL_POST_ACCESS_EXPIRY_RENEWAL_DEFERRED in module_text
    assert "real_access_expiry_simulated\": False" in module_text
    assert "--cycles" in example_text
    assert subject.MAX_CYCLES == 10
    assert subject.DEFAULT_CYCLES == 3
