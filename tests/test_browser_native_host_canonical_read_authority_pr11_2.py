from __future__ import annotations

import chatgpt_web_adapter.browser_native_host as subject


def _request(
    broker: subject.BrowserNativeBroker,
    *,
    operation: str,
    request_id: str,
    lease_id: str | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "protocol": subject.PROTOCOL_VERSION,
        "token": broker.token,
        "type": operation,
        "request_id": request_id,
        "timeoutMs": 1_000,
    }
    if lease_id is not None:
        request["browserAuthorityLeaseId"] = lease_id
    return request


def test_authority_lane_stays_reserved_through_terminal_canonical_readback(
    monkeypatch,
    tmp_path,
) -> None:
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    forwarded_operations: list[str] = []

    def fake_write(stream, forwarded):
        del stream
        operation = forwarded["type"]
        forwarded_operations.append(operation)
        if operation == "turn":
            response = {
                "protocol": subject.PROTOCOL_VERSION,
                "type": "turn_result",
                "request_id": forwarded["request_id"],
                "ok": True,
                "browserAuthorityLeaseId": forwarded["browserAuthorityLeaseId"],
            }
        elif operation == "canonical_read":
            response = {
                "protocol": subject.PROTOCOL_VERSION,
                "type": "canonical_read_result",
                "request_id": forwarded["request_id"],
                "ok": True,
            }
        elif operation == "release_runtime_tab":
            response = {
                "protocol": subject.PROTOCOL_VERSION,
                "type": "release_runtime_tab_result",
                "request_id": forwarded["request_id"],
                "ok": True,
                "released": True,
                "alreadyAbsent": False,
                "runtimeTabId": 77,
                "browserAuthorityLeaseId": forwarded["browserAuthorityLeaseId"],
            }
        else:  # pragma: no cover - fixture guard
            raise AssertionError(f"unexpected operation: {operation}")
        broker.route_native_message(response)

    monkeypatch.setattr(subject, "write_native_message", fake_write)
    try:
        turn = broker.handle_local_request(
            _request(
                broker,
                operation="turn",
                request_id="turn-1",
                lease_id="lease-1",
            )
        )
        assert turn["ok"] is True
        assert broker.turn_lock.locked() is True
        assert broker._authority_reserved_lease_id == "lease-1"

        blocked_release = broker.handle_local_request(
            _request(
                broker,
                operation="release_runtime_tab",
                request_id="release-blocked",
                lease_id="lease-1",
            )
        )
        assert blocked_release["ok"] is False
        assert blocked_release["error"] == "BROWSER_NATIVE_BRIDGE_BUSY"
        assert "release_runtime_tab" not in forwarded_operations

        wrong_read = broker.handle_local_request(
            _request(
                broker,
                operation="canonical_read",
                request_id="read-wrong",
                lease_id="lease-2",
            )
        )
        assert wrong_read["ok"] is False
        assert wrong_read["error"] == "BROWSER_NATIVE_BRIDGE_BUSY"
        assert forwarded_operations == ["turn"]

        read = broker.handle_local_request(
            _request(
                broker,
                operation="canonical_read",
                request_id="read-1",
                lease_id="lease-1",
            )
        )
        assert read["ok"] is True
        assert forwarded_operations == ["turn", "canonical_read"]
        assert broker.turn_lock.locked() is True
        assert broker._authority_reserved_lease_id == "lease-1"

        wrong_complete = broker.handle_local_request(
            _request(
                broker,
                operation="canonical_read_complete",
                request_id="complete-wrong",
                lease_id="lease-2",
            )
        )
        assert wrong_complete["ok"] is False
        assert wrong_complete["error"] == "BROWSER_NATIVE_AUTHORITY_LEASE_MISMATCH"
        assert broker.turn_lock.locked() is True
        assert broker._authority_reserved_lease_id == "lease-1"

        complete = broker.handle_local_request(
            _request(
                broker,
                operation="canonical_read_complete",
                request_id="complete-1",
                lease_id="lease-1",
            )
        )
        assert complete == {
            "protocol": subject.PROTOCOL_VERSION,
            "request_id": "complete-1",
            "ok": True,
            "type": "canonical_read_complete_result",
        }
        assert broker.turn_lock.locked() is False
        assert broker._authority_reserved_lease_id is None

        release = broker.handle_local_request(
            _request(
                broker,
                operation="release_runtime_tab",
                request_id="release-1",
                lease_id="lease-1",
            )
        )
        assert release["ok"] is True
        assert forwarded_operations == [
            "turn",
            "canonical_read",
            "release_runtime_tab",
        ]
    finally:
        broker._clear_authority_reservation(release_lane=True)
        broker._server.server_close()


def test_retryable_canonical_reads_keep_same_lease_reserved_until_completion(
    monkeypatch,
    tmp_path,
) -> None:
    broker = subject.BrowserNativeBroker(state_dir=tmp_path)
    broker.extension_connected = True
    read_count = 0

    def fake_write(stream, forwarded):
        nonlocal read_count
        del stream
        operation = forwarded["type"]
        if operation == "turn":
            broker.route_native_message(
                {
                    "protocol": subject.PROTOCOL_VERSION,
                    "type": "turn_result",
                    "request_id": forwarded["request_id"],
                    "ok": True,
                    "browserAuthorityLeaseId": forwarded["browserAuthorityLeaseId"],
                }
            )
            return
        if operation == "canonical_read":
            read_count += 1
            broker.route_native_message(
                {
                    "protocol": subject.PROTOCOL_VERSION,
                    "type": "canonical_read_result",
                    "request_id": forwarded["request_id"],
                    "ok": False,
                    "reasonCode": "NOT_VISIBLE_YET",
                    "status": 404,
                    "retryable": True,
                }
            )
            return
        raise AssertionError(f"unexpected operation: {operation}")

    monkeypatch.setattr(subject, "write_native_message", fake_write)
    try:
        turn = broker.handle_local_request(
            _request(
                broker,
                operation="turn",
                request_id="turn-1",
                lease_id="lease-1",
            )
        )
        assert turn["ok"] is True

        for index in (1, 2):
            read = broker.handle_local_request(
                _request(
                    broker,
                    operation="canonical_read",
                    request_id=f"read-{index}",
                    lease_id="lease-1",
                )
            )
            assert read["ok"] is False
            assert read["status"] == 404
            assert read["retryable"] is True
            assert broker.turn_lock.locked() is True
            assert broker._authority_reserved_lease_id == "lease-1"

        assert read_count == 2

        complete = broker.handle_local_request(
            _request(
                broker,
                operation="canonical_read_complete",
                request_id="complete-1",
                lease_id="lease-1",
            )
        )
        assert complete["ok"] is True
        assert broker.turn_lock.locked() is False
        assert broker._authority_reserved_lease_id is None
    finally:
        broker._clear_authority_reservation(release_lane=True)
        broker._server.server_close()
