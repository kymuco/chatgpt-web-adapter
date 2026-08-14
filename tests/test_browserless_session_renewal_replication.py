from __future__ import annotations

from datetime import datetime, timezone

import pytest

import chatgpt_web_adapter.browserless_session_renewal_replication as subject
from chatgpt_web_adapter.browserless_session_characterization import (
    BROWSER_REENTRY_REQUIRED_NO_SESSION,
    BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED,
    BROWSERLESS_REFRESH_PROVEN,
    INDETERMINATE_TRANSPORT,
    BrowserlessAuthSnapshot,
    BrowserlessColdStartProbeResult,
    BrowserlessRefreshProbeResult,
)


def _snapshot(*, session: bool = True, expiry: str = "2026-11-10T00:00:00Z") -> BrowserlessAuthSnapshot:
    return BrowserlessAuthSnapshot(
        observed_at="2026-08-14T07:00:00Z",
        auth_file="auth_data.json",
        auth_file_exists=True,
        access_token_present=True,
        access_token_expires_at="2026-08-21T16:45:48Z",
        access_token_ttl_seconds=640000,
        access_token_needs_refresh=False,
        session_cookie_present=session,
        session_expires_at=expiry if session else None,
        session_ttl_seconds=7600000 if session else None,
        browser_profile_exists=True,
    )


def _refresh(
    *,
    ok: bool = True,
    persisted: bool | None = True,
    rotated: bool | None = True,
    verdict: str = BROWSERLESS_REFRESH_PROVEN,
    error_kind: str | None = None,
) -> BrowserlessRefreshProbeResult:
    return BrowserlessRefreshProbeResult(
        attempted=True,
        ok=ok,
        forced_access_token_absent_in_memory=True,
        session_cookie_present=True,
        status_code=200 if ok else None,
        refreshed_access_token_present=ok,
        refreshed_access_token_expires_at="2026-08-21T16:45:48Z" if ok else None,
        session_token_rotated=rotated,
        persisted=persisted,
        post_refresh_read_ok=ok,
        post_refresh_status="completed" if ok else None,
        reentry_verdict=verdict,
        error_kind=error_kind,
    )


def _cold(*, ok: bool = True) -> BrowserlessColdStartProbeResult:
    return BrowserlessColdStartProbeResult(
        attempted=True,
        ok=ok,
        conversation_id="conversation-1" if ok else None,
        status="completed" if ok else None,
        sampled_message_count=2 if ok else 0,
        last_message_id="message-2" if ok else None,
        error_kind=None if ok else "REQUEST_ERROR",
    )


def test_cycles_are_bounded() -> None:
    assert subject._normalize_cycles(1) == 1
    assert subject._normalize_cycles(10) == 10
    with pytest.raises(TypeError):
        subject._normalize_cycles(True)
    with pytest.raises(ValueError):
        subject._normalize_cycles(0)
    with pytest.raises(ValueError):
        subject._normalize_cycles(11)


def test_successful_cycle_requires_persist_then_fresh_cold_read(monkeypatch, tmp_path) -> None:
    snapshots = iter([
        _snapshot(expiry="2026-11-10T00:00:00Z"),
        _snapshot(expiry="2026-11-11T00:00:00Z"),
    ])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(subject, "run_browserless_session_refresh_probe", lambda *a, **k: _refresh())
    captured = {}

    def cold(*args, **kwargs):
        captured.update(kwargs)
        return _cold()

    monkeypatch.setattr(subject, "run_browserless_cold_start_probe", cold)
    result = subject.run_browserless_renewal_cycle(
        1,
        "conversation-1",
        auth_file=tmp_path / "auth.json",
        sample_limit=3,
    )
    assert result.ok is True
    assert result.persisted is True
    assert result.cold_restart_read_ok is True
    assert result.session_expiry_extended is True
    assert captured["sample_limit"] == 3


def test_refresh_without_persistence_cannot_pass_and_skips_cold_read(monkeypatch, tmp_path) -> None:
    snapshots = iter([_snapshot(), _snapshot()])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(
        subject,
        "run_browserless_session_refresh_probe",
        lambda *a, **k: _refresh(persisted=False),
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("cold read must not run when refresh was not persisted")

    monkeypatch.setattr(subject, "run_browserless_cold_start_probe", forbidden)
    result = subject.run_browserless_renewal_cycle(1, "conversation-1", auth_file=tmp_path / "auth.json")
    assert result.ok is False
    assert result.failure_kind == subject.LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE
    assert result.cold_restart_attempted is False
    assert result.browser_reentry_required is False


def test_missing_reusable_session_requires_browser_reentry(monkeypatch, tmp_path) -> None:
    snapshots = iter([_snapshot(session=False), _snapshot(session=False)])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(
        subject,
        "run_browserless_session_refresh_probe",
        lambda *a, **k: _refresh(
            ok=False,
            persisted=None,
            rotated=None,
            verdict=BROWSER_REENTRY_REQUIRED_NO_SESSION,
            error_kind="SESSION_COOKIE_MISSING",
        ),
    )
    result = subject.run_browserless_renewal_cycle(1, "conversation-1", auth_file=tmp_path / "auth.json")
    assert result.failure_kind == subject.NO_REUSABLE_SESSION
    assert result.browser_reentry_required is True


def test_server_refresh_rejection_requires_browser_reentry(monkeypatch, tmp_path) -> None:
    snapshots = iter([_snapshot(), _snapshot()])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(
        subject,
        "run_browserless_session_refresh_probe",
        lambda *a, **k: _refresh(
            ok=False,
            persisted=None,
            rotated=None,
            verdict=BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED,
            error_kind="AUTH_ERROR",
        ),
    )
    result = subject.run_browserless_renewal_cycle(1, "conversation-1", auth_file=tmp_path / "auth.json")
    assert result.failure_kind == subject.SESSION_REFRESH_REJECTED
    assert result.browser_reentry_required is True


def test_transport_failure_does_not_require_browser_reentry(monkeypatch, tmp_path) -> None:
    snapshots = iter([_snapshot(), _snapshot()])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(
        subject,
        "run_browserless_session_refresh_probe",
        lambda *a, **k: _refresh(
            ok=False,
            persisted=None,
            rotated=None,
            verdict=INDETERMINATE_TRANSPORT,
            error_kind="REQUEST_ERROR",
        ),
    )
    result = subject.run_browserless_renewal_cycle(1, "conversation-1", auth_file=tmp_path / "auth.json")
    assert result.failure_kind == subject.TRANSPORT_OR_NETWORK_FAILURE
    assert result.browser_reentry_required is False


def test_post_refresh_cold_restart_failure_is_indeterminate(monkeypatch, tmp_path) -> None:
    snapshots = iter([_snapshot(), _snapshot()])
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: next(snapshots))
    monkeypatch.setattr(subject, "run_browserless_session_refresh_probe", lambda *a, **k: _refresh())
    monkeypatch.setattr(subject, "run_browserless_cold_start_probe", lambda *a, **k: _cold(ok=False))
    result = subject.run_browserless_renewal_cycle(1, "conversation-1", auth_file=tmp_path / "auth.json")
    assert result.failure_kind == subject.POST_REFRESH_COLD_RESTART_READ_FAILURE
    assert result.browser_reentry_required is False
    assert result.cold_restart_attempted is True


def test_three_cycle_replication_counts_persistence_and_cold_reuse(monkeypatch, tmp_path) -> None:
    cycle_results = [
        subject.BrowserlessRenewalCycleResult(
            cycle=index,
            ok=True,
            refresh_ok=True,
            refresh_status_code=200,
            session_token_rotated=(index != 2),
            persisted=True,
            cold_restart_attempted=True,
            cold_restart_read_ok=True,
            cold_restart_status="completed",
            session_cookie_present_after=True,
            session_expiry_extended=(index == 1),
            failure_kind=None,
            browser_reentry_required=False,
            error_kind=None,
        )
        for index in (1, 2, 3)
    ]
    monkeypatch.setattr(
        subject,
        "run_browserless_renewal_cycle",
        lambda cycle, *a, **k: cycle_results[cycle - 1],
    )
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: _snapshot())
    result = subject.replicate_browserless_session_renewal(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
        cycles=3,
    )
    assert result.verdict == subject.REPLICATION_PROVEN
    assert result.attempted_cycles == 3
    assert result.successful_cycles == 3
    assert result.session_rotation_count == 2
    assert result.persistence_count == 3
    assert result.cold_restart_read_count == 3
    assert result.session_expiry_extension_count == 1
    assert result.long_lived_session_reusable_after_replication is True


def test_replication_stops_at_first_failure(monkeypatch, tmp_path) -> None:
    good = subject.BrowserlessRenewalCycleResult(
        1, True, True, 200, True, True, True, True, "completed", True, False, None, False, None
    )
    bad = subject.BrowserlessRenewalCycleResult(
        2,
        False,
        False,
        None,
        None,
        False,
        False,
        False,
        None,
        False,
        False,
        subject.NO_REUSABLE_SESSION,
        True,
        "SESSION_COOKIE_MISSING",
    )
    seen = []

    def cycle(index, *args, **kwargs):
        seen.append(index)
        return good if index == 1 else bad

    monkeypatch.setattr(subject, "run_browserless_renewal_cycle", cycle)
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: _snapshot(session=False))
    result = subject.replicate_browserless_session_renewal(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
        cycles=3,
    )
    assert seen == [1, 2]
    assert result.verdict == subject.REPLICATION_INCOMPLETE
    assert result.browser_reentry_required is True
    assert result.terminal_failure_kind == subject.NO_REUSABLE_SESSION
    assert result.attempted_cycles == 2
