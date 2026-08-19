from chatgpt_web_adapter.browser_authority_lease import (
    BrowserAuthorityLease,
    BrowserAuthorityLeaseState,
    BrowserAuthorityPolicy,
    BrowserAuthorityConfigSource,
    TurnLifecycle,
    TurnLifecycleState,
    resolve_browser_authority_policy,
)


def test_default_policy_is_persistent() -> None:
    resolved = resolve_browser_authority_policy()
    assert resolved.policy is BrowserAuthorityPolicy.PERSISTENT
    assert resolved.ttl_ms is None
    assert resolved.policy_source is BrowserAuthorityConfigSource.TRANSPORT_DEFAULT
    assert resolved.disposal_action == "KEEP"


def test_policy_precedence_per_turn_over_runtime_over_transport() -> None:
    resolved = resolve_browser_authority_policy(
        per_turn_policy="TURN_SCOPED",
        per_turn_ttl_ms=0,
        runtime_policy="IDLE_TTL",
        runtime_ttl_ms=20_000,
        transport_policy="PERSISTENT",
    )
    assert resolved.policy is BrowserAuthorityPolicy.TURN_SCOPED
    assert resolved.ttl_ms == 0
    assert resolved.policy_source is BrowserAuthorityConfigSource.PER_TURN
    assert resolved.ttl_source is BrowserAuthorityConfigSource.PER_TURN


def test_idle_ttl_can_inherit_runtime_ttl() -> None:
    resolved = resolve_browser_authority_policy(
        per_turn_policy="IDLE_TTL",
        runtime_ttl_ms=12_000,
    )
    assert resolved.policy is BrowserAuthorityPolicy.IDLE_TTL
    assert resolved.ttl_ms == 12_000
    assert resolved.ttl_source is BrowserAuthorityConfigSource.RUNTIME_DEFAULT


def test_idle_ttl_requires_positive_ttl() -> None:
    import pytest
    with pytest.raises(ValueError, match="requires ttl_ms > 0"):
        resolve_browser_authority_policy(per_turn_policy="IDLE_TTL")
    with pytest.raises(ValueError, match="requires ttl_ms > 0"):
        resolve_browser_authority_policy(
            per_turn_policy="IDLE_TTL",
            per_turn_ttl_ms=0,
        )


def test_turn_scoped_defaults_to_zero_ttl() -> None:
    resolved = resolve_browser_authority_policy(per_turn_policy="TURN_SCOPED")
    assert resolved.ttl_ms == 0
    assert resolved.ttl_source is BrowserAuthorityConfigSource.IMPLICIT


def test_persistent_ignores_lower_priority_runtime_ttl_when_explicit_per_turn() -> None:
    resolved = resolve_browser_authority_policy(
        per_turn_policy="PERSISTENT",
        runtime_policy="IDLE_TTL",
        runtime_ttl_ms=30_000,
    )
    assert resolved.policy is BrowserAuthorityPolicy.PERSISTENT
    assert resolved.ttl_ms is None


def test_explicit_per_turn_ttl_is_invalid_with_persistent() -> None:
    import pytest
    with pytest.raises(ValueError, match="per-turn ttl"):
        resolve_browser_authority_policy(
            per_turn_policy="PERSISTENT",
            per_turn_ttl_ms=1,
        )


def test_ttl_starts_at_browser_authority_release_not_issue() -> None:
    resolved = resolve_browser_authority_policy(
        per_turn_policy="IDLE_TTL",
        per_turn_ttl_ms=5000,
    )
    lease = BrowserAuthorityLease.issue(
        generation=1,
        resolution=resolved,
        issued_at_ms=1000,
        runtime_tab_id=7,
        lease_id="lease-1",
    )
    released = lease.release(released_at_ms=3500, runtime_tab_id=7)
    assert released.state is BrowserAuthorityLeaseState.RELEASED
    assert released.disposal_due_at_ms == 8500
    assert released.disposal_due_at_ms != lease.issued_at_ms + 5000


def test_persistent_release_never_schedules_disposal() -> None:
    lease = BrowserAuthorityLease.issue(
        generation=1,
        resolution=resolve_browser_authority_policy(),
        issued_at_ms=1000,
        runtime_tab_id=None,
        lease_id="lease-1",
    ).release(released_at_ms=2000, runtime_tab_id=8)
    assert lease.authority_release_proven is True
    assert lease.disposal_allowed is False
    assert lease.disposal_due_at_ms is None


def test_release_unknown_cannot_dispose() -> None:
    lease = BrowserAuthorityLease.issue(
        generation=1,
        resolution=resolve_browser_authority_policy(
            per_turn_policy="TURN_SCOPED",
            per_turn_ttl_ms=0,
        ),
        issued_at_ms=1000,
        runtime_tab_id=8,
        lease_id="lease-1",
    ).release_unknown()
    assert lease.state is BrowserAuthorityLeaseState.RELEASE_UNKNOWN
    assert lease.authority_release_proven is False
    assert lease.disposal_allowed is False
    assert lease.disposal_due_at_ms is None


def test_browser_authority_release_does_not_finalize_turn_lifecycle() -> None:
    turn = TurnLifecycle.prepare(
        browser_authority_lease_id="lease-1",
        started_at_ms=1000,
        lifecycle_id="turn-1",
    ).dispatched()
    turn = turn.write_completed(at_ms=2000)
    assert turn.state is TurnLifecycleState.WRITE_COMPLETED
    assert turn.logical_turn_terminal is False
    turn = turn.finalized(at_ms=3000)
    assert turn.state is TurnLifecycleState.FINALIZED
    assert turn.logical_turn_terminal is True


def test_readback_incomplete_and_ambiguous_require_reconciliation() -> None:
    base = TurnLifecycle.prepare(
        browser_authority_lease_id="lease-1",
        started_at_ms=1000,
        lifecycle_id="turn-1",
    ).dispatched()
    incomplete = base.write_completed(at_ms=1500).readback_incomplete(at_ms=3000)
    ambiguous = base.ambiguous(at_ms=2000)
    assert incomplete.state is TurnLifecycleState.READBACK_INCOMPLETE
    assert incomplete.reconciliation_required is True
    assert ambiguous.state is TurnLifecycleState.AMBIGUOUS
    assert ambiguous.reconciliation_required is True
