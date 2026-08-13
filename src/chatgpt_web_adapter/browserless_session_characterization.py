from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import (
    CHATGPT_SESSION_COOKIE,
    DEFAULT_AUTH_FILE,
    _get_access_token_expiry,
    load_auth_data,
)
from .auth_refresh import refresh_auth_session
from .auth_status import get_auth_status
from .browserless_feasibility import run_browserless_read_probe
from .client import ChatGPTWebClient
from .exceptions import AuthError, RequestError

NO_BROWSER_REENTRY_NEEDED_CURRENT_AUTH = "NO_BROWSER_REENTRY_NEEDED_CURRENT_AUTH"
BROWSERLESS_REFRESH_PROVEN = "BROWSERLESS_SESSION_REFRESH_PROVEN"
BROWSER_REENTRY_REQUIRED_NO_SESSION = "BROWSER_REENTRY_REQUIRED_NO_REUSABLE_SESSION"
BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED = "BROWSER_REENTRY_REQUIRED_SESSION_REFRESH_REJECTED"
REFRESH_PROBE_REQUIRED = "REFRESH_PROBE_REQUIRED_FOR_REENTRY_DECISION"
INDETERMINATE_TRANSPORT = "INDETERMINATE_TRANSPORT_OR_NETWORK_FAILURE"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ttl_seconds(expires_at: datetime | None, *, now: datetime) -> int | None:
    if expires_at is None:
        return None
    return int((expires_at - now).total_seconds())


@dataclass(frozen=True)
class BrowserlessAuthSnapshot:
    observed_at: str
    auth_file: str
    auth_file_exists: bool
    access_token_present: bool
    access_token_expires_at: str | None
    access_token_ttl_seconds: int | None
    access_token_needs_refresh: bool
    session_cookie_present: bool
    session_expires_at: str | None
    session_ttl_seconds: int | None
    browser_profile_exists: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserlessColdStartProbeResult:
    attempted: bool
    ok: bool
    conversation_id: str | None
    status: str | None
    sampled_message_count: int
    last_message_id: str | None
    error_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserlessRefreshProbeResult:
    attempted: bool
    ok: bool
    forced_access_token_absent_in_memory: bool
    session_cookie_present: bool
    status_code: int | None
    refreshed_access_token_present: bool
    refreshed_access_token_expires_at: str | None
    session_token_rotated: bool | None
    persisted: bool | None
    post_refresh_read_ok: bool
    post_refresh_status: str | None
    reentry_verdict: str
    error_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def capture_browserless_auth_snapshot(
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    *,
    now: datetime | None = None,
) -> BrowserlessAuthSnapshot:
    current = _utc_now() if now is None else now.astimezone(timezone.utc)
    status = get_auth_status(auth_file)
    access_expiry = status.access_token_expires_at
    session_expiry = _coerce_datetime(status.session_expires_at)
    return BrowserlessAuthSnapshot(
        observed_at=_iso_utc(current) or "",
        auth_file=str(Path(auth_file)),
        auth_file_exists=bool(status.file_exists),
        access_token_present=bool(status.access_token_present),
        access_token_expires_at=_iso_utc(access_expiry),
        access_token_ttl_seconds=_ttl_seconds(access_expiry, now=current),
        access_token_needs_refresh=bool(status.access_token_needs_refresh),
        session_cookie_present=bool(status.session_cookie_present),
        session_expires_at=_iso_utc(session_expiry),
        session_ttl_seconds=_ttl_seconds(session_expiry, now=current),
        browser_profile_exists=bool(status.browser_profile_exists),
    )


def _safe_error_kind(error: BaseException) -> str:
    if isinstance(error, AuthError):
        return "AUTH_ERROR"
    if isinstance(error, RequestError):
        return "REQUEST_ERROR"
    if isinstance(error, OSError):
        return "OS_ERROR"
    return type(error).__name__.upper()


def run_browserless_cold_start_probe(
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    sample_limit: int = 5,
) -> BrowserlessColdStartProbeResult:
    try:
        client = ChatGPTWebClient(
            auth_file=auth_file,
            auto_refresh_auth=False,
            auto_login=False,
            auto_sentinel=False,
        )
        result = run_browserless_read_probe(
            client,
            conversation,
            sample_limit=sample_limit,
        )
    except (AuthError, RequestError, OSError, ValueError) as error:
        return BrowserlessColdStartProbeResult(
            attempted=True,
            ok=False,
            conversation_id=None,
            status=None,
            sampled_message_count=0,
            last_message_id=None,
            error_kind=_safe_error_kind(error),
        )
    return BrowserlessColdStartProbeResult(
        attempted=True,
        ok=result.ok,
        conversation_id=result.conversation_id,
        status=result.status,
        sampled_message_count=result.sampled_message_count,
        last_message_id=result.last_message_id,
    )


def _refresh_failure_verdict(
    *,
    session_cookie_present: bool,
    error: BaseException,
) -> str:
    if not session_cookie_present:
        return BROWSER_REENTRY_REQUIRED_NO_SESSION
    if isinstance(error, AuthError):
        text = str(error).lower()
        if "status=401" in text or "status=403" in text:
            return BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED
    return INDETERMINATE_TRANSPORT


def run_browserless_session_refresh_probe(
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    sample_limit: int = 5,
    persist: bool = True,
) -> BrowserlessRefreshProbeResult:
    path = Path(auth_file)
    try:
        auth = load_auth_data(path, allow_expired_session_refresh=True)
    except (AuthError, OSError, ValueError) as error:
        return BrowserlessRefreshProbeResult(
            attempted=True,
            ok=False,
            forced_access_token_absent_in_memory=False,
            session_cookie_present=False,
            status_code=None,
            refreshed_access_token_present=False,
            refreshed_access_token_expires_at=None,
            session_token_rotated=None,
            persisted=None,
            post_refresh_read_ok=False,
            post_refresh_status=None,
            reentry_verdict=BROWSER_REENTRY_REQUIRED_NO_SESSION,
            error_kind=_safe_error_kind(error),
        )

    session_cookie_present = any(
        name == CHATGPT_SESSION_COOKIE
        or name.startswith(f"{CHATGPT_SESSION_COOKIE}.")
        for name in auth.cookies
    )
    if not session_cookie_present:
        return BrowserlessRefreshProbeResult(
            attempted=True,
            ok=False,
            forced_access_token_absent_in_memory=False,
            session_cookie_present=False,
            status_code=None,
            refreshed_access_token_present=False,
            refreshed_access_token_expires_at=None,
            session_token_rotated=None,
            persisted=None,
            post_refresh_read_ok=False,
            post_refresh_status=None,
            reentry_verdict=BROWSER_REENTRY_REQUIRED_NO_SESSION,
            error_kind="SESSION_COOKIE_MISSING",
        )

    # Prove the session-cookie boundary directly: the refresh request receives no
    # pre-existing bearer token even when the auth file still contains one.
    auth.accessToken = None
    auth.accessTokenSource = None
    client = ChatGPTWebClient(
        auth=auth,
        auth_file=path,
        auto_refresh_auth=False,
        auto_login=False,
        auto_sentinel=False,
        persist_refreshed_auth=False,
    )
    try:
        refreshed = refresh_auth_session(client, persist=persist, auth_file=path)
    except (AuthError, RequestError, OSError, ValueError) as error:
        return BrowserlessRefreshProbeResult(
            attempted=True,
            ok=False,
            forced_access_token_absent_in_memory=True,
            session_cookie_present=True,
            status_code=None,
            refreshed_access_token_present=False,
            refreshed_access_token_expires_at=None,
            session_token_rotated=None,
            persisted=None,
            post_refresh_read_ok=False,
            post_refresh_status=None,
            reentry_verdict=_refresh_failure_verdict(
                session_cookie_present=True,
                error=error,
            ),
            error_kind=_safe_error_kind(error),
        )

    try:
        expiry = _get_access_token_expiry(client.auth.accessToken)
    except Exception:
        expiry = None

    try:
        read_result = run_browserless_read_probe(
            client,
            conversation,
            sample_limit=sample_limit,
        )
        post_refresh_read_ok = bool(read_result.ok)
        post_refresh_status = read_result.status
    except (AuthError, RequestError, OSError, ValueError) as error:
        return BrowserlessRefreshProbeResult(
            attempted=True,
            ok=False,
            forced_access_token_absent_in_memory=True,
            session_cookie_present=True,
            status_code=refreshed.status_code,
            refreshed_access_token_present=bool(client.auth.accessToken),
            refreshed_access_token_expires_at=_iso_utc(expiry),
            session_token_rotated=refreshed.session_token_rotated,
            persisted=refreshed.persisted,
            post_refresh_read_ok=False,
            post_refresh_status=None,
            reentry_verdict=INDETERMINATE_TRANSPORT,
            error_kind=_safe_error_kind(error),
        )

    return BrowserlessRefreshProbeResult(
        attempted=True,
        ok=bool(refreshed.access_token_present and post_refresh_read_ok),
        forced_access_token_absent_in_memory=True,
        session_cookie_present=True,
        status_code=refreshed.status_code,
        refreshed_access_token_present=bool(client.auth.accessToken),
        refreshed_access_token_expires_at=_iso_utc(expiry),
        session_token_rotated=refreshed.session_token_rotated,
        persisted=refreshed.persisted,
        post_refresh_read_ok=post_refresh_read_ok,
        post_refresh_status=post_refresh_status,
        reentry_verdict=BROWSERLESS_REFRESH_PROVEN,
    )


def characterize_browserless_session(
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    sample_limit: int = 5,
    refresh_probe: bool = False,
    persist_refresh: bool = True,
) -> dict[str, Any]:
    before = capture_browserless_auth_snapshot(auth_file)
    cold_start = run_browserless_cold_start_probe(
        conversation,
        auth_file=auth_file,
        sample_limit=sample_limit,
    )

    refresh = None
    if refresh_probe:
        refresh = run_browserless_session_refresh_probe(
            conversation,
            auth_file=auth_file,
            sample_limit=sample_limit,
            persist=persist_refresh,
        )
        reentry_verdict = refresh.reentry_verdict
    elif cold_start.ok:
        reentry_verdict = NO_BROWSER_REENTRY_NEEDED_CURRENT_AUTH
    elif not before.session_cookie_present:
        reentry_verdict = BROWSER_REENTRY_REQUIRED_NO_SESSION
    else:
        reentry_verdict = REFRESH_PROBE_REQUIRED

    after = capture_browserless_auth_snapshot(auth_file)
    return {
        "pr": "PR8.2.1",
        "reentry_verdict": reentry_verdict,
        "snapshot_before": before.to_dict(),
        "cold_start": cold_start.to_dict(),
        "refresh_probe": refresh.to_dict() if refresh is not None else None,
        "snapshot_after": after.to_dict(),
        "governance": {
            "browser_process_required_by_probe": False,
            "direct_product_write": False,
            "browser_native_turn": False,
            "interactive_login": False,
            "challenge_solver": False,
            "access_token_value_emitted": False,
            "session_cookie_value_emitted": False,
            "forced_access_token_absent_only_in_memory": bool(refresh_probe),
        },
    }
