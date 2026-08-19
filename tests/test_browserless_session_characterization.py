from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import chatgpt_web_adapter.browserless_session_characterization as subject
from chatgpt_web_adapter.types import AuthData


def test_snapshot_reports_ttl_without_credentials(monkeypatch, tmp_path) -> None:
    now = datetime(2026, 8, 13, 16, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        subject,
        "get_auth_status",
        lambda _path: SimpleNamespace(
            file_exists=True,
            access_token_present=True,
            access_token_expires_at=now + timedelta(hours=1),
            access_token_needs_refresh=False,
            session_cookie_present=True,
            session_expires_at="2026-08-20T16:00:00Z",
            browser_profile_exists=True,
        ),
    )
    result = subject.capture_browserless_auth_snapshot(tmp_path / "auth.json", now=now)
    payload = result.to_dict()
    assert payload["access_token_ttl_seconds"] == 3600
    assert payload["session_ttl_seconds"] == 7 * 24 * 3600
    assert "token" not in " ".join(str(value) for value in payload.values()).lower()


def test_session_only_refresh_clears_bearer_and_reads_after_refresh(monkeypatch, tmp_path) -> None:
    secret_access = "SECRET_ACCESS"
    secret_session = "SECRET_SESSION"
    auth = AuthData(
        accessToken=secret_access,
        cookies={"__Secure-next-auth.session-token": secret_session},
    )
    monkeypatch.setattr(subject, "load_auth_data", lambda *a, **k: auth)
    captured = {}

    class FakeClient:
        def __init__(self, *, auth, **kwargs):
            captured["access_at_client_init"] = auth.accessToken
            captured["kwargs"] = kwargs
            self.auth = auth

    monkeypatch.setattr(subject, "ChatGPTWebClient", FakeClient)

    def fake_refresh(client, *, persist, auth_file):
        captured["access_at_refresh"] = client.auth.accessToken
        captured["persist"] = persist
        client.auth.accessToken = "NEW_SECRET_ACCESS"
        return SimpleNamespace(
            status_code=200,
            access_token_present=True,
            session_token_rotated=True,
            persisted=True,
        )

    monkeypatch.setattr(subject, "refresh_auth_session", fake_refresh)
    monkeypatch.setattr(subject, "_get_access_token_expiry", lambda token: None, raising=False)
    monkeypatch.setattr(
        subject,
        "run_browserless_read_probe",
        lambda *a, **k: SimpleNamespace(ok=True, status="completed"),
    )

    result = subject.run_browserless_session_refresh_probe(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
    )
    payload = result.to_dict()
    assert captured["access_at_client_init"] is None
    assert captured["access_at_refresh"] is None
    assert captured["kwargs"]["auto_refresh_auth"] is False
    assert captured["kwargs"]["auto_login"] is False
    assert captured["kwargs"]["auto_sentinel"] is False
    assert result.ok is True
    assert result.post_refresh_read_ok is True
    assert result.reentry_verdict == subject.BROWSERLESS_REFRESH_PROVEN
    rendered = repr(payload)
    assert secret_access not in rendered
    assert secret_session not in rendered
    assert "NEW_SECRET_ACCESS" not in rendered


def test_missing_session_cookie_requires_browser_reentry(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(subject, "load_auth_data", lambda *a, **k: AuthData(accessToken="x"))
    result = subject.run_browserless_session_refresh_probe(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
    )
    assert result.ok is False
    assert result.reentry_verdict == subject.BROWSER_REENTRY_REQUIRED_NO_SESSION
    assert result.error_kind == "SESSION_COOKIE_MISSING"


def test_401_session_refresh_rejection_requires_browser_reentry(monkeypatch, tmp_path) -> None:
    auth = AuthData(cookies={"__Secure-next-auth.session-token": "secret"})
    monkeypatch.setattr(subject, "load_auth_data", lambda *a, **k: auth)

    class FakeClient:
        def __init__(self, *, auth, **kwargs):
            self.auth = auth

    monkeypatch.setattr(subject, "ChatGPTWebClient", FakeClient)

    def reject(*args, **kwargs):
        raise subject.AuthError("ChatGPT session refresh failed: status=401")

    monkeypatch.setattr(subject, "refresh_auth_session", reject)
    result = subject.run_browserless_session_refresh_probe(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
    )
    assert result.reentry_verdict == subject.BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED
    assert result.error_kind == "AUTH_ERROR"


def test_transport_failure_is_not_misclassified_as_browser_reentry(monkeypatch, tmp_path) -> None:
    auth = AuthData(cookies={"__Secure-next-auth.session-token": "secret"})
    monkeypatch.setattr(subject, "load_auth_data", lambda *a, **k: auth)

    class FakeClient:
        def __init__(self, *, auth, **kwargs):
            self.auth = auth

    monkeypatch.setattr(subject, "ChatGPTWebClient", FakeClient)
    monkeypatch.setattr(
        subject,
        "refresh_auth_session",
        lambda *a, **k: (_ for _ in ()).throw(subject.RequestError("network")),
    )
    result = subject.run_browserless_session_refresh_probe(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
    )
    assert result.reentry_verdict == subject.INDETERMINATE_TRANSPORT


def test_cold_start_probe_uses_no_automatic_browser_or_refresh(monkeypatch, tmp_path) -> None:
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(subject, "ChatGPTWebClient", FakeClient)
    monkeypatch.setattr(
        subject,
        "run_browserless_read_probe",
        lambda *a, **k: SimpleNamespace(
            ok=True,
            conversation_id="conversation-1",
            status="completed",
            sampled_message_count=3,
            last_message_id="message-3",
        ),
    )
    result = subject.run_browserless_cold_start_probe(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
    )
    assert result.ok is True
    assert captured["auto_refresh_auth"] is False
    assert captured["auto_login"] is False
    assert captured["auto_sentinel"] is False


def test_full_characterization_does_not_require_refresh_when_cold_start_works(monkeypatch, tmp_path) -> None:
    snapshot = subject.BrowserlessAuthSnapshot(
        observed_at="2026-08-13T16:00:00Z",
        auth_file=str(tmp_path / "auth.json"),
        auth_file_exists=True,
        access_token_present=True,
        access_token_expires_at="2026-08-13T17:00:00Z",
        access_token_ttl_seconds=3600,
        access_token_needs_refresh=False,
        session_cookie_present=True,
        session_expires_at="2026-08-20T16:00:00Z",
        session_ttl_seconds=604800,
        browser_profile_exists=True,
    )
    monkeypatch.setattr(subject, "capture_browserless_auth_snapshot", lambda *a, **k: snapshot)
    monkeypatch.setattr(
        subject,
        "run_browserless_cold_start_probe",
        lambda *a, **k: subject.BrowserlessColdStartProbeResult(
            True, True, "conversation-1", "completed", 2, "message-2"
        ),
    )
    report = subject.characterize_browserless_session(
        "conversation-1",
        auth_file=tmp_path / "auth.json",
        refresh_probe=False,
    )
    assert report["reentry_verdict"] == subject.NO_BROWSER_REENTRY_NEEDED_CURRENT_AUTH
    assert report["refresh_probe"] is None
