from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import chatgpt_web_adapter
from chatgpt_web_adapter import ApprovalDecision, ApprovalPolicy, PendingApproval
from chatgpt_web_adapter.approval_policy import APPROVAL_DECISION_REASONS


def _approval(recipient: str = "python") -> PendingApproval:
    return PendingApproval(
        tool_message_id="tool-msg",
        target_message_id="target-node",
        recipient=recipient,
    )


def test_approval_decision_accepts_known_reasons() -> None:
    for reason in APPROVAL_DECISION_REASONS:
        decision = ApprovalDecision(allowed=False, reason=reason)
        assert decision.reason == reason


def test_approval_decision_requires_bool_allowed() -> None:
    with pytest.raises(TypeError, match="allowed must be a bool"):
        ApprovalDecision(allowed="false", reason="recipient_allowed")


def test_approval_decision_requires_known_reason() -> None:
    with pytest.raises(ValueError, match="unsupported approval decision reason"):
        ApprovalDecision(allowed=False, reason="unknown")


def test_approval_decision_normalizes_recipient_and_reason() -> None:
    decision = ApprovalDecision(
        allowed=True,
        reason=" recipient_allowed ",
        recipient=" python ",
    )

    assert decision.reason == "recipient_allowed"
    assert decision.recipient == "python"


def test_approval_decision_manual_required_is_strict_bool() -> None:
    assert ApprovalDecision(
        allowed=False,
        reason="manual_required_for_unknown_recipient",
        manual_required=True,
    ).manual_required is True

    with pytest.raises(TypeError, match="manual_required must be a bool"):
        ApprovalDecision(
            allowed=False,
            reason="manual_required_for_unknown_recipient",
            manual_required="true",
        )


def test_approval_decision_metadata_none_becomes_empty_dict() -> None:
    decision = ApprovalDecision(
        allowed=False,
        reason="recipient_denied",
        metadata_preview=None,
    )

    assert decision.metadata_preview == {}


def test_approval_decision_rejects_non_dict_metadata() -> None:
    with pytest.raises(TypeError, match="metadata_preview must be a dict"):
        ApprovalDecision(
            allowed=False,
            reason="recipient_denied",
            metadata_preview="bad",
        )


def test_approval_decision_deep_copies_metadata_on_construction() -> None:
    metadata = {"nested": {"value": 1}}
    decision = ApprovalDecision(
        allowed=False,
        reason="recipient_denied",
        metadata_preview=metadata,
    )

    metadata["nested"]["value"] = 2

    assert decision.metadata_preview == {"nested": {"value": 1}}


def test_approval_decision_to_dict_deep_copies_metadata() -> None:
    decision = ApprovalDecision(
        allowed=False,
        reason="recipient_denied",
        metadata_preview={"nested": {"value": 1}},
    )

    payload = decision.to_dict()
    payload["metadata_preview"]["nested"]["value"] = 2

    assert decision.metadata_preview == {"nested": {"value": 1}}


def test_approval_decision_from_dict_roundtrip() -> None:
    decision = ApprovalDecision(
        allowed=False,
        reason="manual_required_for_unknown_recipient",
        recipient="python",
        manual_required=True,
        metadata_preview={"safe": True},
    )

    assert ApprovalDecision.from_dict(decision.to_dict()) == decision


def test_approval_decision_from_dict_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="approval decision payload must be a dict"):
        ApprovalDecision.from_dict(None)


def test_approval_policy_defaults_deny_unknown_manual_required() -> None:
    policy = ApprovalPolicy()

    assert policy.allowed_recipients == frozenset()
    assert policy.denied_recipients == frozenset()
    assert policy.auto_approve_read_only is False
    assert policy.require_manual_for_unknown is True

    decision = policy.evaluate(_approval("python"))
    assert decision.allowed is False
    assert decision.reason == "manual_required_for_unknown_recipient"
    assert decision.recipient == "python"
    assert decision.manual_required is True


def test_approval_policy_normalizes_allowed_and_denied_recipients() -> None:
    policy = ApprovalPolicy(
        allowed_recipients={" python ", "python", "browser"},
        denied_recipients=[" shell "],
    )

    assert policy.allowed_recipients == frozenset({"python", "browser"})
    assert policy.denied_recipients == frozenset({"shell"})


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("allowed_recipients", {"allowed_recipients": {""}}),
        ("denied_recipients", {"denied_recipients": {"  "}}),
    ],
)
def test_approval_policy_rejects_empty_recipient(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match=f"{field_name} contains invalid recipient"):
        ApprovalPolicy(**kwargs)


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("allowed_recipients", {"allowed_recipients": {1}}),
        ("denied_recipients", {"denied_recipients": {object()}}),
    ],
)
def test_approval_policy_rejects_non_string_recipient(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} contains invalid recipient"):
        ApprovalPolicy(**kwargs)


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("allowed_recipients", {"allowed_recipients": "python"}),
        ("denied_recipients", {"denied_recipients": "browser"}),
    ],
)
def test_approval_policy_rejects_plain_string_recipient_collections(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(TypeError, match=f"{field_name} must be an iterable of strings"):
        ApprovalPolicy(**kwargs)


def test_approval_policy_rejects_allowed_denied_conflict() -> None:
    with pytest.raises(ValueError, match="recipients cannot be both allowed and denied"):
        ApprovalPolicy(
            allowed_recipients={"python", "browser"},
            denied_recipients={"browser"},
        )


def test_approval_policy_rejects_non_bool_flags() -> None:
    with pytest.raises(TypeError, match="auto_approve_read_only must be a bool"):
        ApprovalPolicy(auto_approve_read_only="false")
    with pytest.raises(TypeError, match="require_manual_for_unknown must be a bool"):
        ApprovalPolicy(require_manual_for_unknown="true")


def test_approval_policy_is_frozen() -> None:
    policy = ApprovalPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.require_manual_for_unknown = False


def test_approval_policy_stores_frozensets() -> None:
    policy = ApprovalPolicy(allowed_recipients={"python"})

    assert isinstance(policy.allowed_recipients, frozenset)
    assert isinstance(policy.denied_recipients, frozenset)


def test_approval_policy_to_dict_sorts_recipients() -> None:
    policy = ApprovalPolicy(
        allowed_recipients={"python", "browser"},
        denied_recipients={"shell", "bio"},
        auto_approve_read_only=True,
        require_manual_for_unknown=False,
    )

    assert policy.to_dict() == {
        "allowed_recipients": ["browser", "python"],
        "denied_recipients": ["bio", "shell"],
        "auto_approve_read_only": True,
        "require_manual_for_unknown": False,
    }


def test_approval_policy_from_dict_roundtrip() -> None:
    policy = ApprovalPolicy(
        allowed_recipients={"python"},
        denied_recipients={"browser"},
        auto_approve_read_only=True,
        require_manual_for_unknown=False,
    )

    assert ApprovalPolicy.from_dict(policy.to_dict()) == policy


def test_approval_policy_from_dict_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="approval policy payload must be a dict"):
        ApprovalPolicy.from_dict(None)


def test_approval_policy_denied_recipient_denies() -> None:
    policy = ApprovalPolicy(denied_recipients={"browser"})

    decision = policy.evaluate(_approval("browser"))

    assert decision.allowed is False
    assert decision.reason == "recipient_denied"
    assert decision.recipient == "browser"
    assert decision.manual_required is False


def test_approval_policy_allowed_recipient_allows() -> None:
    policy = ApprovalPolicy(allowed_recipients={"python"})

    decision = policy.evaluate(_approval("python"))

    assert decision.allowed is True
    assert decision.reason == "recipient_allowed"
    assert decision.recipient == "python"
    assert decision.manual_required is False


def test_approval_policy_unknown_recipient_requires_manual_by_default() -> None:
    policy = ApprovalPolicy()

    decision = policy.evaluate(_approval("python"))

    assert decision.allowed is False
    assert decision.reason == "manual_required_for_unknown_recipient"
    assert decision.recipient == "python"
    assert decision.manual_required is True


def test_approval_policy_unknown_recipient_with_manual_disabled_is_still_denied() -> None:
    policy = ApprovalPolicy(require_manual_for_unknown=False)

    decision = policy.evaluate(_approval("python"))

    assert decision.allowed is False
    assert decision.reason == "unknown_recipient_denied"
    assert decision.recipient == "python"
    assert decision.manual_required is False


def test_approval_policy_auto_approve_read_only_does_not_allow_without_evidence() -> None:
    policy = ApprovalPolicy(auto_approve_read_only=True)

    decision = policy.evaluate(_approval("python"))

    assert decision.allowed is False
    assert decision.reason == "manual_required_for_unknown_recipient"
    assert decision.manual_required is True


def test_approval_policy_auto_approve_read_only_allows_with_explicit_read_only_flag() -> None:
    policy = ApprovalPolicy(auto_approve_read_only=True)

    decision = policy.evaluate_with_metadata(
        _approval("python"),
        {"read_only": True},
    )

    assert decision.allowed is True
    assert decision.reason == "read_only_auto_approved"
    assert decision.manual_required is False
    assert decision.metadata_preview == {"read_only": True}


def test_approval_policy_read_only_without_auto_approve_requires_manual() -> None:
    policy = ApprovalPolicy(auto_approve_read_only=False)

    decision = policy.evaluate_with_metadata(
        _approval("python"),
        {"operation_type": "read"},
    )

    assert decision.allowed is False
    assert decision.reason == "read_only_auto_approve_disabled"
    assert decision.manual_required is True
    assert decision.metadata_preview == {"operation_type": "read"}


def test_approval_policy_evaluate_rejects_non_pending_approval() -> None:
    with pytest.raises(TypeError, match="approval must be a PendingApproval"):
        ApprovalPolicy().evaluate("bad")


def test_approval_policy_types_are_exported_from_public_package() -> None:
    assert chatgpt_web_adapter.ApprovalDecision is ApprovalDecision
    assert chatgpt_web_adapter.ApprovalPolicy is ApprovalPolicy
    assert "ApprovalDecision" in chatgpt_web_adapter.__all__
    assert "ApprovalPolicy" in chatgpt_web_adapter.__all__
