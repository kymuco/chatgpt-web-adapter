from __future__ import annotations

import chatgpt_web_adapter.browserless_product_execution_closure as subject


def test_current_surfaces_exhaust_supported_browserless_product_write() -> None:
    verdict, qualifying = subject.closure_verdict()
    assert verdict == subject.EXHAUSTED
    assert qualifying == []


def test_every_current_surface_fails_at_least_one_acceptance_requirement() -> None:
    assert subject.SURFACES
    assert all(not surface.qualifies() for surface in subject.SURFACES)


def test_desktop_is_native_product_but_has_no_external_turn_contract() -> None:
    desktop = next(item for item in subject.SURFACES if item.surface_id == "chatgpt_desktop")
    assert desktop.non_browser is True
    assert desktop.ordinary_chatgpt_chat_semantics is True
    assert desktop.existing_conversation_continuity is True
    assert desktop.external_programmatic_invocation is False
    assert desktop.qualifies() is False


def test_api_is_programmatic_but_separate_product() -> None:
    api = next(item for item in subject.SURFACES if item.surface_id == "openai_api")
    assert api.external_programmatic_invocation is True
    assert api.non_browser is True
    assert api.consumer_product_usage is False
    assert api.ordinary_chatgpt_chat_semantics is False


def test_sign_in_is_identity_only() -> None:
    surface = next(item for item in subject.SURFACES if item.surface_id == "sign_in_with_chatgpt")
    assert surface.disposition == "IDENTITY_ONLY"
    assert surface.chatgpt_memory_continuity is False
    assert surface.existing_conversation_continuity is False


def test_apps_sdk_has_reverse_direction() -> None:
    surface = next(item for item in subject.SURFACES if item.surface_id == "apps_sdk_mcp")
    assert surface.direction == "chatgpt_to_external_tool"
    assert surface.qualifies() is False


def test_codex_is_programmatic_negative_control_not_chat_history() -> None:
    surface = next(item for item in subject.SURFACES if item.surface_id == "codex_cli_sdk")
    assert surface.external_programmatic_invocation is True
    assert surface.consumer_product_usage is True
    assert surface.ordinary_chatgpt_chat_semantics is False
    assert surface.existing_conversation_continuity is False


def test_compliance_platform_is_not_turn_execution() -> None:
    surface = next(item for item in subject.SURFACES if item.surface_id == "compliance_platform")
    assert surface.disposition == "AUDIT_AND_COMPLIANCE_DATA_ONLY"
    assert surface.ordinary_chatgpt_chat_semantics is False


def test_future_supported_surface_reopens_closure() -> None:
    future = subject.ProductExecutionSurface(
        surface_id="future_chat_turn",
        name="Future Chat turn API",
        openai_supported=True,
        non_browser=True,
        external_programmatic_invocation=True,
        ordinary_chatgpt_chat_semantics=True,
        existing_conversation_continuity=True,
        chatgpt_memory_continuity=True,
        consumer_product_usage=True,
        direction="external_client_to_chatgpt_chat",
        disposition="SUPPORTED",
        evidence_note="hypothetical test surface",
    )
    verdict, qualifying = subject.closure_verdict([future])
    assert verdict == subject.FOUND
    assert qualifying == ["future_chat_turn"]


def test_report_keeps_browser_native_baseline_when_exhausted() -> None:
    report = subject.product_execution_closure_report()
    assert report["verdict"] == subject.EXHAUSTED
    assert report["supported_non_browser_product_write_available"] is False
    assert report["closure"]["browserless_turn_provider_eligible"] is False
    assert report["closure"]["minimum_proven_supported_product_write_runtime"] == subject.BROWSER_NATIVE_BASELINE
    assert "native_inventory" not in report


def test_report_governance_forbids_private_execution_probing() -> None:
    governance = subject.product_execution_closure_report()["governance"]
    assert governance == {
        "direct_private_product_write_probe": False,
        "challenge_solver_expansion": False,
        "browser_protection_emulation": False,
        "credential_extraction": False,
        "native_ui_automation": False,
        "undocumented_native_ipc_probe": False,
    }
