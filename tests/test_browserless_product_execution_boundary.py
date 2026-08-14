from __future__ import annotations

import chatgpt_web_adapter.browserless_product_execution_closure as subject


def test_native_inventory_never_launches_chatgpt(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        class Result:
            returncode = 0
            stdout = ""
        return Result()

    monkeypatch.setattr(subject.os, "name", "nt", raising=False)
    monkeypatch.setattr(subject.shutil, "which", lambda name: "powershell.exe" if "powershell" in name else None)
    monkeypatch.setattr(subject.subprocess, "run", fake_run)
    result = subject.native_client_inventory()
    assert result["governance"]["launches_native_client"] is False
    assert len(calls) == 1
    rendered = " ".join(calls[0]).lower()
    assert "get-appxpackage" in rendered
    assert "start-process" not in rendered
    assert "chatgpt.exe" not in rendered


def test_native_inventory_does_not_probe_storage_or_ipc(monkeypatch) -> None:
    monkeypatch.setattr(subject.os, "name", "posix", raising=False)
    monkeypatch.setattr(subject.shutil, "which", lambda _name: None)
    result = subject.native_client_inventory()
    governance = result["governance"]
    assert governance["private_storage_read"] is False
    assert governance["undocumented_ipc_probe"] is False
    assert governance["credential_extraction"] is False


def test_surface_matrix_contains_no_secrets_or_private_endpoint_material() -> None:
    rendered = repr(subject.supported_surface_matrix()).lower()
    forbidden = ("sentinel", "turnstile", "proof_token", "session-token", "backend-api/f/conversation")
    assert not any(item in rendered for item in forbidden)
