from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import DEFAULT_AUTH_FILE
from .browserless_session_characterization import (
    BROWSER_REENTRY_REQUIRED_NO_SESSION,
    BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED,
    BROWSERLESS_REFRESH_PROVEN,
    INDETERMINATE_TRANSPORT,
    BrowserlessAuthSnapshot,
    BrowserlessColdStartProbeResult,
    BrowserlessRefreshProbeResult,
    capture_browserless_auth_snapshot,
    run_browserless_cold_start_probe,
    run_browserless_session_refresh_probe,
)

REPLICATION_PROVEN = "BROWSERLESS_SESSION_RENEWAL_REPLICATION_PROVEN"
REPLICATION_INCOMPLETE = "BROWSERLESS_SESSION_RENEWAL_REPLICATION_INCOMPLETE"
NO_REUSABLE_SESSION = "NO_REUSABLE_SESSION"
SESSION_REFRESH_REJECTED = "SESSION_REFRESH_REJECTED_401_403"
LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE = "LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE"
TRANSPORT_OR_NETWORK_FAILURE = "TRANSPORT_OR_NETWORK_FAILURE"
POST_REFRESH_COLD_RESTART_READ_FAILURE = "POST_REFRESH_COLD_RESTART_READ_FAILURE"
REAL_POST_ACCESS_EXPIRY_RENEWAL_DEFERRED = "REAL_POST_ACCESS_EXPIRY_RENEWAL_DEFERRED"

MIN_CYCLES = 1
MAX_CYCLES = 10
DEFAULT_CYCLES = 3


def _parse_iso_utc(value: str | None) -> datetime | None:
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


def _session_expiry_extended(
    before: BrowserlessAuthSnapshot,
    after: BrowserlessAuthSnapshot,
) -> bool:
    before_expiry = _parse_iso_utc(before.session_expires_at)
    after_expiry = _parse_iso_utc(after.session_expires_at)
    if before_expiry is None or after_expiry is None:
        return False
    return after_expiry > before_expiry


def _normalize_cycles(cycles: int) -> int:
    if isinstance(cycles, bool) or not isinstance(cycles, int):
        raise TypeError("cycles must be an int")
    if cycles < MIN_CYCLES or cycles > MAX_CYCLES:
        raise ValueError(f"cycles must be between {MIN_CYCLES} and {MAX_CYCLES}")
    return cycles


def _failure_from_refresh(refresh: BrowserlessRefreshProbeResult) -> tuple[str, bool]:
    if refresh.reentry_verdict == BROWSER_REENTRY_REQUIRED_NO_SESSION:
        return NO_REUSABLE_SESSION, True
    if refresh.reentry_verdict == BROWSER_REENTRY_REQUIRED_REFRESH_REJECTED:
        return SESSION_REFRESH_REJECTED, True
    if refresh.reentry_verdict == INDETERMINATE_TRANSPORT:
        return TRANSPORT_OR_NETWORK_FAILURE, False
    return LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE, False


@dataclass(frozen=True)
class BrowserlessRenewalCycleResult:
    cycle: int
    ok: bool
    refresh_ok: bool
    refresh_status_code: int | None
    session_token_rotated: bool | None
    persisted: bool
    cold_restart_attempted: bool
    cold_restart_read_ok: bool
    cold_restart_status: str | None
    session_cookie_present_after: bool
    session_expiry_extended: bool
    failure_kind: str | None
    browser_reentry_required: bool
    error_kind: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrowserlessRenewalReplicationResult:
    verdict: str
    requested_cycles: int
    attempted_cycles: int
    successful_cycles: int
    session_rotation_count: int
    persistence_count: int
    cold_restart_read_count: int
    session_expiry_extension_count: int
    long_lived_session_reusable_after_replication: bool
    browser_reentry_required: bool
    terminal_failure_kind: str | None
    longitudinal_gate: str
    cycles: tuple[BrowserlessRenewalCycleResult, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cycles"] = [item.to_dict() for item in self.cycles]
        return payload


def _cycle_from_refresh_failure(
    cycle: int,
    refresh: BrowserlessRefreshProbeResult,
    after: BrowserlessAuthSnapshot,
) -> BrowserlessRenewalCycleResult:
    failure_kind, browser_reentry_required = _failure_from_refresh(refresh)
    return BrowserlessRenewalCycleResult(
        cycle=cycle,
        ok=False,
        refresh_ok=False,
        refresh_status_code=refresh.status_code,
        session_token_rotated=refresh.session_token_rotated,
        persisted=bool(refresh.persisted),
        cold_restart_attempted=False,
        cold_restart_read_ok=False,
        cold_restart_status=None,
        session_cookie_present_after=after.session_cookie_present,
        session_expiry_extended=False,
        failure_kind=failure_kind,
        browser_reentry_required=browser_reentry_required,
        error_kind=refresh.error_kind,
    )


def run_browserless_renewal_cycle(
    cycle: int,
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    sample_limit: int = 5,
) -> BrowserlessRenewalCycleResult:
    before = capture_browserless_auth_snapshot(auth_file)
    refresh = run_browserless_session_refresh_probe(
        conversation,
        auth_file=auth_file,
        sample_limit=sample_limit,
        persist=True,
    )

    if not refresh.ok:
        after = capture_browserless_auth_snapshot(auth_file)
        return _cycle_from_refresh_failure(cycle, refresh, after)

    # A successful in-memory refresh is insufficient evidence for replication.
    # The refreshed auth state must first have been persisted to disk.
    if refresh.persisted is not True:
        after = capture_browserless_auth_snapshot(auth_file)
        return BrowserlessRenewalCycleResult(
            cycle=cycle,
            ok=False,
            refresh_ok=True,
            refresh_status_code=refresh.status_code,
            session_token_rotated=refresh.session_token_rotated,
            persisted=False,
            cold_restart_attempted=False,
            cold_restart_read_ok=False,
            cold_restart_status=None,
            session_cookie_present_after=after.session_cookie_present,
            session_expiry_extended=_session_expiry_extended(before, after),
            failure_kind=LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE,
            browser_reentry_required=False,
            error_kind="REFRESH_NOT_PERSISTED",
        )

    # Fresh-process-equivalent read: this creates a new client from auth_file,
    # so the cycle cannot pass by continuing to use the refreshed in-memory client.
    cold = run_browserless_cold_start_probe(
        conversation,
        auth_file=auth_file,
        sample_limit=sample_limit,
    )
    after = capture_browserless_auth_snapshot(auth_file)

    if not cold.ok:
        return BrowserlessRenewalCycleResult(
            cycle=cycle,
            ok=False,
            refresh_ok=True,
            refresh_status_code=refresh.status_code,
            session_token_rotated=refresh.session_token_rotated,
            persisted=True,
            cold_restart_attempted=True,
            cold_restart_read_ok=False,
            cold_restart_status=cold.status,
            session_cookie_present_after=after.session_cookie_present,
            session_expiry_extended=_session_expiry_extended(before, after),
            failure_kind=POST_REFRESH_COLD_RESTART_READ_FAILURE,
            browser_reentry_required=False,
            error_kind=cold.error_kind,
        )

    return BrowserlessRenewalCycleResult(
        cycle=cycle,
        ok=True,
        refresh_ok=True,
        refresh_status_code=refresh.status_code,
        session_token_rotated=refresh.session_token_rotated,
        persisted=True,
        cold_restart_attempted=True,
        cold_restart_read_ok=True,
        cold_restart_status=cold.status,
        session_cookie_present_after=after.session_cookie_present,
        session_expiry_extended=_session_expiry_extended(before, after),
        failure_kind=None,
        browser_reentry_required=False,
        error_kind=None,
    )


def replicate_browserless_session_renewal(
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    cycles: int = DEFAULT_CYCLES,
    sample_limit: int = 5,
) -> BrowserlessRenewalReplicationResult:
    requested_cycles = _normalize_cycles(cycles)
    cycle_results: list[BrowserlessRenewalCycleResult] = []

    for cycle in range(1, requested_cycles + 1):
        result = run_browserless_renewal_cycle(
            cycle,
            conversation,
            auth_file=auth_file,
            sample_limit=sample_limit,
        )
        cycle_results.append(result)
        if not result.ok:
            break

    attempted = len(cycle_results)
    successful = sum(1 for item in cycle_results if item.ok)
    rotations = sum(1 for item in cycle_results if item.session_token_rotated is True)
    persisted = sum(1 for item in cycle_results if item.persisted)
    cold_reads = sum(1 for item in cycle_results if item.cold_restart_read_ok)
    expiry_extensions = sum(1 for item in cycle_results if item.session_expiry_extended)
    browser_reentry_required = any(item.browser_reentry_required for item in cycle_results)
    terminal_failure = next(
        (item.failure_kind for item in reversed(cycle_results) if item.failure_kind is not None),
        None,
    )

    final_snapshot = capture_browserless_auth_snapshot(auth_file)
    replication_proven = (
        attempted == requested_cycles
        and successful == requested_cycles
        and persisted == requested_cycles
        and cold_reads == requested_cycles
        and final_snapshot.session_cookie_present
    )

    return BrowserlessRenewalReplicationResult(
        verdict=REPLICATION_PROVEN if replication_proven else REPLICATION_INCOMPLETE,
        requested_cycles=requested_cycles,
        attempted_cycles=attempted,
        successful_cycles=successful,
        session_rotation_count=rotations,
        persistence_count=persisted,
        cold_restart_read_count=cold_reads,
        session_expiry_extension_count=expiry_extensions,
        long_lived_session_reusable_after_replication=bool(
            replication_proven and final_snapshot.session_cookie_present
        ),
        browser_reentry_required=browser_reentry_required,
        terminal_failure_kind=terminal_failure,
        longitudinal_gate=REAL_POST_ACCESS_EXPIRY_RENEWAL_DEFERRED,
        cycles=tuple(cycle_results),
    )


def replication_report(
    conversation: Any,
    *,
    auth_file: str | Path = DEFAULT_AUTH_FILE,
    cycles: int = DEFAULT_CYCLES,
    sample_limit: int = 5,
) -> dict[str, Any]:
    result = replicate_browserless_session_renewal(
        conversation,
        auth_file=auth_file,
        cycles=cycles,
        sample_limit=sample_limit,
    )
    return {
        "pr": "PR8.2.2",
        **result.to_dict(),
        "failure_taxonomy": {
            NO_REUSABLE_SESSION: {"browser_reentry_required": True},
            SESSION_REFRESH_REJECTED: {"browser_reentry_required": True},
            LOCAL_AUTH_STATE_OR_PERSISTENCE_FAILURE: {"browser_reentry_required": False},
            TRANSPORT_OR_NETWORK_FAILURE: {"browser_reentry_required": False},
            POST_REFRESH_COLD_RESTART_READ_FAILURE: {"browser_reentry_required": False},
        },
        "governance": {
            "browser_process_required_by_probe": False,
            "direct_product_write": False,
            "browser_native_turn": False,
            "interactive_login": False,
            "challenge_solver": False,
            "access_token_value_emitted": False,
            "session_cookie_value_emitted": False,
            "real_access_expiry_simulated": False,
            "max_cycles": MAX_CYCLES,
        },
    }
