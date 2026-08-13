from __future__ import annotations

from types import SimpleNamespace

from chatgpt_web_adapter.browserless_feasibility import (
    SUPPORTED_BROWSERLESS_PRODUCT_WRITE_VERDICT,
    base_feasibility_report,
    run_browserless_read_probe,
)


def test_report_keeps_supported_write_verdict_negative_but_reopenable() -> None:
    report = base_feasibility_report()
    assert report["verdict"] == "SUPPORTED_BROWSERLESS_PRODUCT_WRITE_NOT_FOUND"
    assert report["supported_browserless_product_write_available"] is False
    assert SUPPORTED_BROWSERLESS_PRODUCT_WRITE_VERDICT == report["verdict"]
    assert report["governance"]["read_only_probe"] is True
    assert report["governance"]["direct_product_write_probe"] is False
    assert report["governance"]["challenge_solver_expansion"] is False
    assert report["governance"]["browser_protection_emulation"] is False


def test_capability_matrix_has_expected_pr82_gates() -> None:
    matrix = {row["gate"]: row for row in base_feasibility_report()["capabilities"]}
    assert set(matrix) == {"B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"}
    assert matrix["B0"]["verdict"] == "PASS"
    assert matrix["B2"]["verdict"] == "BROWSER_REQUIRED"
    assert matrix["B3"]["verdict"] == "SUPPORTED_BROWSERLESS_PRODUCT_WRITE_NOT_FOUND"
    assert matrix["B6"]["verdict"] == "SEPARATE_PRODUCT"
    assert matrix["B7"]["verdict"] == "BROWSER_NATIVE_BASELINE"


def test_live_probe_reads_only_bounded_metadata() -> None:
    calls = []

    class Client:
        def get_status(self, conversation):
            calls.append(("status", conversation))
            return SimpleNamespace(status="completed")

        def get_messages(self, conversation, **kwargs):
            calls.append(("messages", conversation, kwargs))
            return [
                SimpleNamespace(message_id="m1", text="SECRET ONE"),
                SimpleNamespace(message_id="m2", text="SECRET TWO"),
            ]

    result = run_browserless_read_probe(Client(), "conversation-1", sample_limit=2)
    payload = result.to_dict()

    assert calls == [
        ("status", "conversation-1"),
        ("messages", "conversation-1", {"limit": 2, "include_empty": True}),
    ]
    assert payload == {
        "attempted": True,
        "ok": True,
        "conversation_id": "conversation-1",
        "status": "completed",
        "sampled_message_count": 2,
        "last_message_id": "m2",
    }
    assert "SECRET" not in repr(payload)


def test_live_probe_rejects_invalid_sample_limit() -> None:
    client = SimpleNamespace()
    for value in (-1,):
        try:
            run_browserless_read_probe(client, "conversation-1", sample_limit=value)
        except ValueError:
            pass
        else:
            raise AssertionError("negative sample_limit must fail")
