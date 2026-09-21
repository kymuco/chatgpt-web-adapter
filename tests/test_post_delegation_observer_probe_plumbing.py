from __future__ import annotations

import threading

import chatgpt_web_adapter.browser_native_host as host_module
from chatgpt_web_adapter.browser_native_host import BrowserNativeBroker
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir


def test_broker_forwards_observer_failure_probe_without_whitelisting(
    monkeypatch,
    tmp_path,
) -> None:
    broker = BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    forwarded: list[dict[str, object]] = []
    results: list[dict[str, object]] = []

    monkeypatch.setattr(
        host_module,
        "write_native_message",
        lambda _stream, payload: forwarded.append(dict(payload)),
    )

    request = {
        "protocol": 1,
        "token": broker.token,
        "type": "turn",
        "request_id": "probe-1",
        "text": "hello",
        "conversationId": "conversation-1",
        "timeoutMs": 5_000,
        "postDelegationObserverFailureProbe": True,
    }

    def run() -> None:
        results.append(broker.handle_local_request(request))

    thread = threading.Thread(target=run)
    thread.start()
    for _ in range(1_000):
        if forwarded:
            break
        threading.Event().wait(0.001)

    assert forwarded
    assert forwarded[0]["postDelegationObserverFailureProbe"] is True

    broker.route_native_message(
        {
            "protocol": 1,
            "type": "turn_result",
            "request_id": "probe-1",
            "ok": False,
            "error": "synthetic",
        }
    )
    thread.join(timeout=2)
    try:
        assert not thread.is_alive()
        assert results[0]["ok"] is False
    finally:
        broker._server.server_close()


def test_recovery_awaits_probe_decision_before_early_terminal_success() -> None:
    recovery = browser_native_extension_dir() / "service_worker_recovery.js"
    source = recovery.read_text(encoding="utf-8")
    start = source.index(
        "executeOfficialPageTurn = async function "
        "_executeOfficialPageTurnWithEarlyTerminalBoundary"
    )
    end = source.index(
        "async function _executeNativeTurnWithStaleUiRecovery",
        start,
    )
    block = source[start:end]

    response_index = block.index('method === "Network.responseReceived"')
    probe_start_index = block.index(
        "observerFailureProbePromise = Promise.resolve(",
        response_index,
    )
    first_boundary_index = block.index("const firstBoundary =")
    probe_await_index = block.index(
        "await observerFailureProbePromise",
        first_boundary_index,
    )
    early_accept_index = block.index(
        'if (firstBoundary?.kind === "assistant_terminal_candidate")'
    )

    assert response_index < probe_start_index < first_boundary_index
    assert first_boundary_index < probe_await_index < early_accept_index
