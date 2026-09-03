from __future__ import annotations

from pathlib import Path

from chatgpt_web_adapter.product_runtime import ChatGPTProductRuntime
from chatgpt_web_adapter.product_submission_runtime_gate import (
    install_product_submission_runtime_surface,
)
from chatgpt_web_adapter.product_ui_liveness_runtime_gate import (
    install_product_ui_liveness_runtime_surface,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "chatgpt_web_adapter"


def test_runtime_owns_submission_and_liveness_methods_in_class_body() -> None:
    for name in (
        "submit",
        "await_final",
        "submission_lifecycle_snapshot",
        "observe_ui_liveness",
        "governance",
    ):
        method = ChatGPTProductRuntime.__dict__.get(name)
        assert callable(method)
        assert method.__module__ == "chatgpt_web_adapter.product_runtime"


def test_historical_installers_are_validation_only_and_identity_preserving() -> None:
    before = {
        name: getattr(ChatGPTProductRuntime, name)
        for name in (
            "submit",
            "await_final",
            "submission_lifecycle_snapshot",
            "observe_ui_liveness",
            "governance",
        )
    }

    install_product_submission_runtime_surface(ChatGPTProductRuntime)
    install_product_ui_liveness_runtime_surface(ChatGPTProductRuntime)

    after = {name: getattr(ChatGPTProductRuntime, name) for name in before}
    assert after == before


def test_historical_gate_sources_do_not_assign_runtime_methods() -> None:
    submission_gate = (PACKAGE / "product_submission_runtime_gate.py").read_text(
        encoding="utf-8"
    )
    liveness_gate = (PACKAGE / "product_ui_liveness_runtime_gate.py").read_text(
        encoding="utf-8"
    )

    forbidden = (
        "runtime_class.submit =",
        "runtime_class.await_final =",
        "runtime_class.submission_lifecycle_snapshot =",
        "runtime_class.observe_ui_liveness =",
        "runtime_class.governance =",
        "setattr(runtime_class",
    )
    for token in forbidden:
        assert token not in submission_gate
        assert token not in liveness_gate
