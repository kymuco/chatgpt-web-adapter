from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any
import uuid


class BrowserAuthorityPolicy(str, Enum):
    PERSISTENT = "PERSISTENT"
    IDLE_TTL = "IDLE_TTL"
    TURN_SCOPED = "TURN_SCOPED"


class BrowserAuthorityLeaseState(str, Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    RELEASE_UNKNOWN = "RELEASE_UNKNOWN"


class TurnLifecycleState(str, Enum):
    PREPARED = "PREPARED"
    DISPATCHED = "DISPATCHED"
    WRITE_COMPLETED = "WRITE_COMPLETED"
    FINALIZED = "FINALIZED"
    READBACK_INCOMPLETE = "READBACK_INCOMPLETE"
    AMBIGUOUS = "AMBIGUOUS"


class BrowserAuthorityConfigSource(str, Enum):
    PER_TURN = "PER_TURN"
    RUNTIME_DEFAULT = "RUNTIME_DEFAULT"
    TRANSPORT_DEFAULT = "TRANSPORT_DEFAULT"
    IMPLICIT = "IMPLICIT"


@dataclass(frozen=True)
class BrowserAuthorityPolicyResolution:
    policy: BrowserAuthorityPolicy
    ttl_ms: int | None
    policy_source: BrowserAuthorityConfigSource
    ttl_source: BrowserAuthorityConfigSource | None
    disposal_action: str

    def __post_init__(self) -> None:
        if not isinstance(self.policy, BrowserAuthorityPolicy):
            object.__setattr__(self, "policy", BrowserAuthorityPolicy(str(self.policy).strip().upper()))
        if not isinstance(self.policy_source, BrowserAuthorityConfigSource):
            object.__setattr__(
                self,
                "policy_source",
                BrowserAuthorityConfigSource(str(self.policy_source).strip().upper()),
            )
        if self.ttl_source is not None and not isinstance(
            self.ttl_source, BrowserAuthorityConfigSource
        ):
            object.__setattr__(
                self,
                "ttl_source",
                BrowserAuthorityConfigSource(str(self.ttl_source).strip().upper()),
            )
        if self.ttl_ms is not None:
            if isinstance(self.ttl_ms, bool) or not isinstance(self.ttl_ms, int):
                raise TypeError("ttl_ms must be an int or None")
            if self.ttl_ms < 0:
                raise ValueError("ttl_ms must be >= 0")
        if self.policy is BrowserAuthorityPolicy.PERSISTENT:
            if self.ttl_ms is not None:
                raise ValueError("PERSISTENT policy cannot carry a disposal TTL")
            if self.disposal_action != "KEEP":
                raise ValueError("PERSISTENT policy must use KEEP disposal action")
        elif self.policy is BrowserAuthorityPolicy.IDLE_TTL:
            if self.ttl_ms is None or self.ttl_ms <= 0:
                raise ValueError("IDLE_TTL policy requires ttl_ms > 0")
            if self.disposal_action != "CLOSE":
                raise ValueError("IDLE_TTL policy must use CLOSE disposal action")
        elif self.policy is BrowserAuthorityPolicy.TURN_SCOPED:
            if self.ttl_ms is None or self.ttl_ms < 0:
                raise ValueError("TURN_SCOPED policy requires ttl_ms >= 0")
            if self.disposal_action != "CLOSE":
                raise ValueError("TURN_SCOPED policy must use CLOSE disposal action")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.value,
            "ttl_ms": self.ttl_ms,
            "policy_source": self.policy_source.value,
            "ttl_source": self.ttl_source.value if self.ttl_source is not None else None,
            "disposal_action": self.disposal_action,
        }


def _normalize_policy(value: BrowserAuthorityPolicy | str | None) -> BrowserAuthorityPolicy | None:
    if value is None:
        return None
    if isinstance(value, BrowserAuthorityPolicy):
        return value
    if not isinstance(value, str):
        raise TypeError("browser_authority_policy must be a string or BrowserAuthorityPolicy")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("browser_authority_policy must not be empty")
    try:
        return BrowserAuthorityPolicy(normalized)
    except ValueError as error:
        supported = ", ".join(policy.value for policy in BrowserAuthorityPolicy)
        raise ValueError(
            f"unsupported browser_authority_policy {value!r}; expected one of: {supported}"
        ) from error


def _normalize_ttl(value: int | None, *, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int or None")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def resolve_browser_authority_policy(
    *,
    per_turn_policy: BrowserAuthorityPolicy | str | None = None,
    per_turn_ttl_ms: int | None = None,
    runtime_policy: BrowserAuthorityPolicy | str | None = None,
    runtime_ttl_ms: int | None = None,
    transport_policy: BrowserAuthorityPolicy | str = BrowserAuthorityPolicy.PERSISTENT,
    transport_ttl_ms: int | None = None,
) -> BrowserAuthorityPolicyResolution:
    """Resolve PR8.8 policy using per-turn > runtime > transport precedence.

    TTL precedence is independent, but a higher-priority PERSISTENT policy makes
    lower-priority TTL values irrelevant. An explicit per-turn TTL paired with
    PERSISTENT is rejected because it is internally contradictory.
    """

    per_turn_policy_n = _normalize_policy(per_turn_policy)
    runtime_policy_n = _normalize_policy(runtime_policy)
    transport_policy_n = _normalize_policy(transport_policy)
    if transport_policy_n is None:
        raise ValueError("transport_policy is required")

    per_turn_ttl = _normalize_ttl(per_turn_ttl_ms, name="per_turn_ttl_ms")
    runtime_ttl = _normalize_ttl(runtime_ttl_ms, name="runtime_ttl_ms")
    transport_ttl = _normalize_ttl(transport_ttl_ms, name="transport_ttl_ms")

    if per_turn_policy_n is not None:
        policy = per_turn_policy_n
        policy_source = BrowserAuthorityConfigSource.PER_TURN
    elif runtime_policy_n is not None:
        policy = runtime_policy_n
        policy_source = BrowserAuthorityConfigSource.RUNTIME_DEFAULT
    else:
        policy = transport_policy_n
        policy_source = BrowserAuthorityConfigSource.TRANSPORT_DEFAULT

    if policy is BrowserAuthorityPolicy.PERSISTENT:
        if per_turn_ttl is not None:
            raise ValueError("per-turn ttl cannot be used with PERSISTENT policy")
        return BrowserAuthorityPolicyResolution(
            policy=policy,
            ttl_ms=None,
            policy_source=policy_source,
            ttl_source=None,
            disposal_action="KEEP",
        )

    ttl_ms: int | None
    ttl_source: BrowserAuthorityConfigSource | None
    if per_turn_ttl is not None:
        ttl_ms = per_turn_ttl
        ttl_source = BrowserAuthorityConfigSource.PER_TURN
    elif runtime_ttl is not None:
        ttl_ms = runtime_ttl
        ttl_source = BrowserAuthorityConfigSource.RUNTIME_DEFAULT
    elif transport_ttl is not None:
        ttl_ms = transport_ttl
        ttl_source = BrowserAuthorityConfigSource.TRANSPORT_DEFAULT
    elif policy is BrowserAuthorityPolicy.TURN_SCOPED:
        ttl_ms = 0
        ttl_source = BrowserAuthorityConfigSource.IMPLICIT
    else:
        ttl_ms = None
        ttl_source = None

    return BrowserAuthorityPolicyResolution(
        policy=policy,
        ttl_ms=ttl_ms,
        policy_source=policy_source,
        ttl_source=ttl_source,
        disposal_action="CLOSE",
    )


@dataclass(frozen=True)
class BrowserAuthorityLease:
    lease_id: str
    generation: int
    policy: BrowserAuthorityPolicy
    ttl_ms: int | None
    issued_at_ms: int
    runtime_tab_id_at_acquire: int | None
    state: BrowserAuthorityLeaseState = BrowserAuthorityLeaseState.ACTIVE
    released_at_ms: int | None = None
    runtime_tab_id_at_release: int | None = None
    disposal_due_at_ms: int | None = None

    def __post_init__(self) -> None:
        lease_id = self.lease_id.strip() if isinstance(self.lease_id, str) else ""
        if not lease_id:
            raise ValueError("lease_id is required")
        object.__setattr__(self, "lease_id", lease_id)
        if isinstance(self.generation, bool) or not isinstance(self.generation, int):
            raise TypeError("generation must be an int")
        if self.generation <= 0:
            raise ValueError("generation must be positive")
        if not isinstance(self.policy, BrowserAuthorityPolicy):
            object.__setattr__(
                self,
                "policy",
                BrowserAuthorityPolicy(str(self.policy).strip().upper()),
            )
        for field_name in ("issued_at_ms",):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an int")
            if value < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if self.ttl_ms is not None:
            if isinstance(self.ttl_ms, bool) or not isinstance(self.ttl_ms, int):
                raise TypeError("ttl_ms must be an int or None")
            if self.ttl_ms < 0:
                raise ValueError("ttl_ms must be >= 0")
        if not isinstance(self.state, BrowserAuthorityLeaseState):
            object.__setattr__(
                self,
                "state",
                BrowserAuthorityLeaseState(str(self.state).strip().upper()),
            )
        if self.state is BrowserAuthorityLeaseState.ACTIVE:
            if self.released_at_ms is not None or self.disposal_due_at_ms is not None:
                raise ValueError("ACTIVE lease cannot have release/disposal timestamps")
        if self.state is BrowserAuthorityLeaseState.RELEASED:
            if self.released_at_ms is None:
                raise ValueError("RELEASED lease requires released_at_ms")
            if self.policy is BrowserAuthorityPolicy.PERSISTENT:
                if self.disposal_due_at_ms is not None:
                    raise ValueError("PERSISTENT lease cannot have disposal_due_at_ms")
            else:
                if self.ttl_ms is None:
                    raise ValueError("disposable lease requires ttl_ms")
                expected = self.released_at_ms + self.ttl_ms
                if self.disposal_due_at_ms != expected:
                    raise ValueError(
                        "disposal_due_at_ms must start from Browser Authority Lease release"
                    )
        if self.state is BrowserAuthorityLeaseState.RELEASE_UNKNOWN:
            if self.disposal_due_at_ms is not None:
                raise ValueError("RELEASE_UNKNOWN lease cannot schedule disposal")

    @classmethod
    def issue(
        cls,
        *,
        generation: int,
        resolution: BrowserAuthorityPolicyResolution,
        issued_at_ms: int,
        runtime_tab_id: int | None,
        lease_id: str | None = None,
    ) -> "BrowserAuthorityLease":
        return cls(
            lease_id=lease_id or str(uuid.uuid4()),
            generation=generation,
            policy=resolution.policy,
            ttl_ms=resolution.ttl_ms,
            issued_at_ms=issued_at_ms,
            runtime_tab_id_at_acquire=runtime_tab_id,
        )

    @property
    def authority_release_proven(self) -> bool:
        return self.state is BrowserAuthorityLeaseState.RELEASED

    @property
    def disposal_allowed(self) -> bool:
        return (
            self.state is BrowserAuthorityLeaseState.RELEASED
            and self.policy is not BrowserAuthorityPolicy.PERSISTENT
            and self.disposal_due_at_ms is not None
        )

    def release(
        self,
        *,
        released_at_ms: int,
        runtime_tab_id: int | None,
    ) -> "BrowserAuthorityLease":
        if self.state is not BrowserAuthorityLeaseState.ACTIVE:
            raise ValueError("only ACTIVE Browser Authority Lease can be released")
        if released_at_ms < self.issued_at_ms:
            raise ValueError("released_at_ms cannot precede issued_at_ms")
        due = None
        if self.policy is not BrowserAuthorityPolicy.PERSISTENT:
            if self.ttl_ms is None:
                raise ValueError("disposable lease requires ttl_ms")
            due = released_at_ms + self.ttl_ms
        return replace(
            self,
            state=BrowserAuthorityLeaseState.RELEASED,
            released_at_ms=released_at_ms,
            runtime_tab_id_at_release=runtime_tab_id,
            disposal_due_at_ms=due,
        )

    def release_unknown(self) -> "BrowserAuthorityLease":
        if self.state is not BrowserAuthorityLeaseState.ACTIVE:
            return self
        return replace(self, state=BrowserAuthorityLeaseState.RELEASE_UNKNOWN)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["policy"] = self.policy.value
        payload["state"] = self.state.value
        payload["authority_release_proven"] = self.authority_release_proven
        payload["disposal_allowed"] = self.disposal_allowed
        return payload


@dataclass(frozen=True)
class TurnLifecycle:
    lifecycle_id: str
    browser_authority_lease_id: str
    started_at_ms: int
    state: TurnLifecycleState = TurnLifecycleState.PREPARED
    write_completed_at_ms: int | None = None
    terminal_at_ms: int | None = None
    reconciliation_required: bool = False

    def __post_init__(self) -> None:
        lifecycle_id = self.lifecycle_id.strip() if isinstance(self.lifecycle_id, str) else ""
        lease_id = (
            self.browser_authority_lease_id.strip()
            if isinstance(self.browser_authority_lease_id, str)
            else ""
        )
        if not lifecycle_id:
            raise ValueError("lifecycle_id is required")
        if not lease_id:
            raise ValueError("browser_authority_lease_id is required")
        object.__setattr__(self, "lifecycle_id", lifecycle_id)
        object.__setattr__(self, "browser_authority_lease_id", lease_id)
        if not isinstance(self.state, TurnLifecycleState):
            object.__setattr__(
                self,
                "state",
                TurnLifecycleState(str(self.state).strip().upper()),
            )
        if isinstance(self.started_at_ms, bool) or not isinstance(self.started_at_ms, int):
            raise TypeError("started_at_ms must be an int")
        if self.started_at_ms < 0:
            raise ValueError("started_at_ms must be >= 0")
        if self.state is TurnLifecycleState.WRITE_COMPLETED and self.write_completed_at_ms is None:
            raise ValueError("WRITE_COMPLETED requires write_completed_at_ms")
        if self.state in {
            TurnLifecycleState.FINALIZED,
            TurnLifecycleState.READBACK_INCOMPLETE,
            TurnLifecycleState.AMBIGUOUS,
        } and self.terminal_at_ms is None:
            raise ValueError(f"{self.state.value} requires terminal_at_ms")
        if self.state is TurnLifecycleState.FINALIZED and self.reconciliation_required:
            raise ValueError("FINALIZED lifecycle cannot require reconciliation")
        if self.state in {
            TurnLifecycleState.READBACK_INCOMPLETE,
            TurnLifecycleState.AMBIGUOUS,
        } and not self.reconciliation_required:
            raise ValueError(f"{self.state.value} lifecycle requires reconciliation")

    @classmethod
    def prepare(
        cls,
        *,
        browser_authority_lease_id: str,
        started_at_ms: int,
        lifecycle_id: str | None = None,
    ) -> "TurnLifecycle":
        return cls(
            lifecycle_id=lifecycle_id or str(uuid.uuid4()),
            browser_authority_lease_id=browser_authority_lease_id,
            started_at_ms=started_at_ms,
        )

    @property
    def logical_turn_terminal(self) -> bool:
        return self.state in {
            TurnLifecycleState.FINALIZED,
            TurnLifecycleState.READBACK_INCOMPLETE,
            TurnLifecycleState.AMBIGUOUS,
        }

    def dispatched(self) -> "TurnLifecycle":
        if self.state is not TurnLifecycleState.PREPARED:
            raise ValueError("only PREPARED lifecycle can be dispatched")
        return replace(self, state=TurnLifecycleState.DISPATCHED)

    def write_completed(self, *, at_ms: int) -> "TurnLifecycle":
        if self.state not in {
            TurnLifecycleState.PREPARED,
            TurnLifecycleState.DISPATCHED,
        }:
            raise ValueError("write completion requires PREPARED/DISPATCHED lifecycle")
        return replace(
            self,
            state=TurnLifecycleState.WRITE_COMPLETED,
            write_completed_at_ms=at_ms,
        )

    def finalized(self, *, at_ms: int) -> "TurnLifecycle":
        if self.state not in {
            TurnLifecycleState.DISPATCHED,
            TurnLifecycleState.WRITE_COMPLETED,
        }:
            raise ValueError("finality requires DISPATCHED/WRITE_COMPLETED lifecycle")
        return replace(
            self,
            state=TurnLifecycleState.FINALIZED,
            terminal_at_ms=at_ms,
            reconciliation_required=False,
        )

    def readback_incomplete(self, *, at_ms: int) -> "TurnLifecycle":
        return replace(
            self,
            state=TurnLifecycleState.READBACK_INCOMPLETE,
            terminal_at_ms=at_ms,
            reconciliation_required=True,
        )

    def ambiguous(self, *, at_ms: int) -> "TurnLifecycle":
        return replace(
            self,
            state=TurnLifecycleState.AMBIGUOUS,
            terminal_at_ms=at_ms,
            reconciliation_required=True,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["logical_turn_terminal"] = self.logical_turn_terminal
        return payload
