from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from chatgpt_web_adapter.browser_authority_instant_failure_forensics_preflight_pr8_8 import (
    run_preflight,
)
from chatgpt_web_adapter.browser_authority_instant_failure_forensics_support_pr8_8 import (
    InstantFailureForensicsProvider,
)
from chatgpt_web_adapter.browser_native_install import browser_native_extension_dir

LEASE_ID = "lease-popup-subtree"
CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"


def test_popup_subtree_worker_is_additive_after_failure_layer_and_read_only():
    root = browser_native_extension_dir()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.1.13"
    observability = (root / "service_worker_observability.js").read_text(encoding="utf-8")
    prior = 'importScripts("service_worker_instant_failure_forensics_pr8_8.js")'
    new = 'importScripts("service_worker_instant_popup_subtree_forensics_pr8_8.js")'
    assert prior in observability and new in observability
    assert observability.index(prior) < observability.index(new)

    worker = (root / "service_worker_instant_popup_subtree_forensics_pr8_8.js").read_text(
        encoding="utf-8"
    )
    for token in (
        "popupSubtreeCaptureSupported",
        "popupLocalTraversalSupported",
        "modeLabelActionableAncestorMappingSupported",
        "candidateCapDealiasingSupported",
        "popupEvidencePersistenceSupported",
        "rawPopupTextRedactionSupported",
        "modeBearingDescendantModes",
        "actionableAncestorHops",
        "globalCandidateCapUsed: false",
        "throw error",
    ):
        assert token in worker
    for forbidden in (
        "Input.insertText",
        "Input.dispatchMouseEvent",
        "submitOfficialPageTurn(",
        "chrome.tabs.create(",
        "chrome.tabs.update(",
        "chrome.tabs.remove(",
        "chrome.debugger.attach(",
        "Network.getResponseBody",
        "document.cookie",
    ):
        assert forbidden not in worker


def test_provider_parses_popup_subtree_support(monkeypatch):
    provider = InstantFailureForensicsProvider()

    def rpc(payload, *, timeout):
        assert payload["characterizeInstantFailureForensicsSupport"] is True
        return {
            "instantFailureForensicsSupported": True,
            "instantFailureForensicsSchemaVersion": 1,
            "failureRecordPersistenceSupported": True,
            "preInputFailureBoundarySupported": True,
            "retainedRouteForensicsCompositionSupported": True,
            "retainedPickerForensicsCompositionSupported": True,
            "rawErrorRedactionSupported": True,
            "leaseIdExported": False,
            "zeroProductWrites": True,
            "automaticRetry": False,
            "popupSubtreeCaptureSupported": True,
            "popupLocalTraversalSupported": True,
            "modeLabelActionableAncestorMappingSupported": True,
            "candidateCapDealiasingSupported": True,
            "popupEvidencePersistenceSupported": True,
            "rawPopupTextRedactionSupported": True,
        }

    monkeypatch.setattr(provider, "_characterization_rpc", rpc)
    support = provider.instant_failure_forensics_support()
    assert support["popup_subtree_capture_supported"] is True
    assert support["popup_local_traversal_supported"] is True
    assert support["mode_label_actionable_ancestor_mapping_supported"] is True
    assert support["candidate_cap_dealiasing_supported"] is True
    assert support["popup_evidence_persistence_supported"] is True
    assert support["raw_popup_text_redaction_supported"] is True


def test_provider_parses_lease_fenced_popup_local_mode_to_actionable_mapping(monkeypatch):
    provider = InstantFailureForensicsProvider()

    def rpc(payload, *, timeout):
        assert payload["expectedBrowserAuthorityLeaseId"] == LEASE_ID
        return {
            "failureCaptured": True,
            "failureCode": "OPTION_NOT_FOUND",
            "failureReason": "instant_option_missing",
            "preInputFailureBoundaryProven": True,
            "promptInsertionReached": False,
            "submitReached": False,
            "rawErrorExported": False,
            "leaseIdExported": False,
            "zeroProductWrites": True,
            "automaticRetry": False,
            "selection": {
                "selectedModeBeforeSelection": "HIGH",
                "conversationWriteCountDuringSelection": 0,
                "unexpectedConversationWriteBeforeSelectionComplete": False,
            },
            "popupSubtreeRecordAvailable": True,
            "popupSubtree": {
                "schemaVersion": 1,
                "capturedAtFailure": True,
                "failureCode": "OPTION_NOT_FOUND",
                "failureReason": "instant_option_missing",
                "captureStatus": "POPUP_SUBTREE_CAPTURED",
                "captureTabId": 123,
                "routeKind": "CONVERSATION",
                "observedConversationId": CONVERSATION,
                "rawUrlExported": False,
                "rawTextExported": False,
                "rawHtmlExported": False,
                "leaseIdExported": False,
                "zeroProductWrites": True,
                "automaticRetry": False,
                "candidateCapDealiased": True,
                "globalCandidateCapUsed": False,
                "topology": {
                    "surfaceFound": True,
                    "surfaceSelectionStatus": "SELECTED_MODE_BEARING_POPUP",
                    "candidateSurfaceCount": 1,
                    "candidateSurfaces": [
                        {
                            "tag": "DIV",
                            "role": "menu",
                            "knownModeDescendantCount": 3,
                            "actionableDescendantCount": 3,
                            "rect": {"x": 800, "y": 800, "width": 224, "height": 96},
                        }
                    ],
                    "selectedSurface": {
                        "tag": "DIV",
                        "role": "menu",
                        "knownModeDescendantCount": 3,
                        "actionableDescendantCount": 3,
                        "rect": {"x": 800, "y": 800, "width": 224, "height": 96},
                    },
                    "recognizedModes": ["HIGH", "INSTANT", "MEDIUM"],
                    "popupSubtreeVisibleElementCount": 12,
                    "modeLabelCount": 3,
                    "modeLabels": [
                        {
                            "mode": "INSTANT",
                            "evidence": "OWN_TEXT",
                            "tag": "SPAN",
                            "role": None,
                            "rect": {"x": 820, "y": 840, "width": 60, "height": 20},
                            "actionableAncestorFound": True,
                            "actionableAncestorHops": 2,
                            "actionableAncestor": {
                                "tag": "DIV",
                                "role": "menuitem",
                                "directModes": [],
                                "subtreeModes": ["INSTANT"],
                                "ariaChecked": None,
                                "ariaSelected": None,
                                "ariaExpanded": None,
                                "ariaHaspopup": None,
                                "dataState": None,
                                "disabled": False,
                                "pointerEventsEnabled": True,
                                "rect": {"x": 815, "y": 834, "width": 224, "height": 24},
                                "childElementCount": 1,
                            },
                        }
                    ],
                    "modeLabelsTruncated": False,
                    "actionableDescendantCount": 3,
                    "actionableDescendants": [
                        {
                            "tag": "DIV",
                            "role": "menuitem",
                            "directModes": [],
                            "subtreeModes": ["INSTANT"],
                            "modeBearingDescendantModes": ["INSTANT"],
                            "modeBearingDescendantCount": 1,
                            "disabled": False,
                            "pointerEventsEnabled": True,
                            "rect": {"x": 815, "y": 834, "width": 224, "height": 24},
                            "childElementCount": 1,
                        }
                    ],
                    "actionableDescendantsTruncated": False,
                },
            },
        }

    monkeypatch.setattr(provider, "_characterization_rpc", rpc)
    record = provider.instant_failure_forensics_record(LEASE_ID)
    popup = record["popup_subtree"]
    assert record["popup_subtree_record_available"] is True
    assert popup["capture_status"] == "POPUP_SUBTREE_CAPTURED"
    assert popup["candidate_cap_dealiased"] is True
    assert popup["global_candidate_cap_used"] is False
    assert popup["recognized_modes"] == ["HIGH", "INSTANT", "MEDIUM"]
    label = popup["mode_labels"][0]
    assert label["mode"] == "INSTANT"
    assert label["actionable_ancestor_found"] is True
    assert label["actionable_ancestor_hops"] == 2
    assert label["actionable_ancestor"]["role"] == "menuitem"
    assert label["actionable_ancestor"]["direct_modes"] == []
    assert label["actionable_ancestor"]["subtree_modes"] == ["INSTANT"]
    assert popup["actionable_descendants"][0]["mode_bearing_descendant_modes"] == ["INSTANT"]


def test_production_popup_support_false_fails_preflight_before_authority_or_write():
    class Provider:
        def instant_failure_forensics_support(self):
            return {
                "supported": True,
                "schema": 1,
                "failure_record_persistence_supported": True,
                "pre_input_failure_boundary_supported": True,
                "retained_route_forensics_composition_supported": True,
                "retained_picker_forensics_composition_supported": True,
                "raw_error_redaction_supported": True,
                "lease_id_exported": False,
                "zero_product_writes": True,
                "automatic_retry": False,
                "popup_subtree_capture_supported": False,
                "popup_local_traversal_supported": False,
                "mode_label_actionable_ancestor_mapping_supported": False,
                "candidate_cap_dealiasing_supported": False,
                "popup_evidence_persistence_supported": False,
                "raw_popup_text_redaction_supported": False,
            }
        def instant_selection_support(self):
            return {"instant_selection_repair_supported": True, "product_ui_selection_supported": True}
        def retained_route_identity_support(self):
            return {"retained_route_identity_supported": True, "zero_product_writes": True}
        def retained_picker_forensics_support(self):
            return {"retained_picker_forensics_supported": True, "zero_product_writes": True}
        def characterization_status(self):
            raise AssertionError("must fail before authority preflight")

    runner = SimpleNamespace(provider=Provider())
    report = {}
    phase = ["start"]
    with pytest.raises(RuntimeError, match="POPUP_SUBTREE_EXTENSION_RELOAD_REQUIRED"):
        run_preflight(runner, report, CONVERSATION, 1.0, phase)
