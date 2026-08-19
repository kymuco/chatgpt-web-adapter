from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "examples" / "verify_browser_native_stress.py"

spec = importlib.util.spec_from_file_location("verify_browser_native_stress", VERIFIER)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _message(role: str, text: str):
    return SimpleNamespace(role=role, text=text)


def test_analyze_stress_messages_accepts_exact_order_with_intermediate_nodes() -> None:
    messages = []
    for index in range(1, 21):
        marker = f"SDK_BRIDGE_STRESS_{index:02d}"
        messages.extend(
            [
                _message("user", f"Reply with exactly: {marker}"),
                _message("assistant", "Обработка заняла пару секунд"),
                _message("assistant", marker),
            ]
        )

    report = module.analyze_stress_messages(messages)

    assert report["ok"] is True
    assert report["observed_user_markers"] == 20
    assert report["observed_assistant_markers"] == 20
    assert report["order_ok"] is True


def test_analyze_stress_messages_rejects_missing_and_duplicate_markers() -> None:
    messages = []
    for index in range(1, 21):
        marker = f"SDK_BRIDGE_STRESS_{index:02d}"
        if index != 7:
            messages.append(_message("user", f"Reply with exactly: {marker}"))
        messages.append(_message("assistant", marker))
    messages.append(_message("assistant", "SDK_BRIDGE_STRESS_03"))

    report = module.analyze_stress_messages(messages)

    assert report["ok"] is False
    assert report["missing_user"] == [7]
    assert report["duplicate_assistant"] == [3]
    assert report["order_ok"] is False
