from __future__ import annotations

import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from chatgpt_web_adapter.exceptions import RequestError
from tools.capability_capture_v0_semantic_browser import (
    capture_semantic_pair,
    classify_semantic_stability,
    validate_semantic_observation,
)

ROOT = Path(__file__).resolve().parents[1]
_JS = (
    ROOT
    / "src/chatgpt_web_adapter/browser_native_extension"
    / "service_worker_capability_capture_v0.js"
)


def _desc(role: str, kind: str, region: str, interactable: bool) -> dict:
    return {
        "role": role,
        "kind": kind,
        "region": region,
        "interactable": interactable,
    }


def _snapshot(*, count: int = 1, output_region: str = "right") -> dict:
    return {
        "routeVerified": True,
        "resultFamilyStages": {
            "rawFamily": 1,
            "visibleFamily": 1,
            "visibleLeaves": 1,
        },
        "source_input": {
            "candidateCount": count,
            "uniqueDescriptor": (
                _desc("textbox", "textarea", "left", True) if count == 1 else None
            ),
        },
        "translated_result": {
            "candidateCount": 1,
            "uniqueDescriptor": _desc("result_leaf", "span", output_region, False),
        },
    }


def _response() -> dict:
    return {
        "type": "research_capture_translate_semantic_v0_result",
        "ok": True,
        "schema": "CWA_CAPTURE_C1_TWO_DOCUMENT_STRUCTURE_V2",
        "productId": "google-translate-web",
        "captureMode": "EXPLICIT_TWO_TAB_OBSERVE_ONLY",
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "observations": [_snapshot(), _snapshot()],
        "selectorProvenance": "HANDWRITTEN_REFERENCE_FAMILIES_NOT_LEARNED",
        "semanticFinalityProven": False,
        "canonicalCompletionProven": False,
        "replayExecutable": False,
        "newWriteAuthority": False,
        "automaticRetry": False,
        "rawContentRetained": False,
    }


class FakeBridge:
    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self.response = _response() if response is None else response
        self.error = error
        self.calls = []

    def _rpc(self, payload, **kwargs):
        self.calls.append((payload, kwargs))
        if self.error is not None:
            raise self.error
        return deepcopy(self.response)


def _validate(response: dict) -> dict:
    return validate_semantic_observation(
        response, source_language="en", target_language="es"
    )


def _classify(response: dict) -> dict:
    return classify_semantic_stability(_validate(response))


def test_two_distinct_tabs_return_bounded_comparison_without_write() -> None:
    bridge = FakeBridge()
    report = capture_semantic_pair(
        bridge,
        tab_ids=(101, 102),
        source_language="en",
        target_language="es",
        explicit_consent=True,
    )
    [invocation] = bridge.calls
    request, options = invocation
    assert request["type"] == "research_capture_translate_semantic_v0"
    assert request["tabIds"] == [101, 102]
    assert request["consent"] == "EXPLICIT_TWO_TAB_OBSERVE_ONLY"
    assert request["timeoutMs"] == 20000
    assert options["timeout"] == 30.0
    # Native-host broker waits delegated timeout plus 5s. Client reserves
    # 10s so the host can return its explicit timeout before socket expiry.
    assert options["delegated_response_margin"] == 10.0
    assert options["delegated_timeout_ms_key"] == "timeoutMs"
    assert not {"text", "translatedText", "url", "selector"} & set(request)
    assert report["observations"]["source_input"]["status"] == (
        "CONSISTENT_REFERENCE_FAMILY_SIGNATURE"
    )
    assert report["observations"]["translated_result"]["status"] == (
        "CONSISTENT_REFERENCE_FAMILY_SIGNATURE"
    )
    result_observation = report["observations"]["translated_result"]
    assert result_observation["reference_family_stages_by_document"] == {
        "A": {"rawFamily": 1, "visibleFamily": 1, "visibleLeaves": 1},
        "B": {"rawFamily": 1, "visibleFamily": 1, "visibleLeaves": 1},
    }
    assert result_observation["reference_family_diagnosis_by_document"] == {
        "A": "VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT",
        "B": "VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT",
    }
    assert report["observations"]["source_input"]["candidate_counts_by_document"] == {
        "A": 1,
        "B": 1,
    }
    result_counts = report["observations"]["translated_result"][
        "candidate_counts_by_document"
    ]
    assert result_counts == {
        "A": 1,
        "B": 1,
    }
    assert report["observations"]["source_input"]["learned_locator_proven"] is False
    assert report["independent_renderer_process_proven"] is False
    assert report["selector_families_from_capture"] is False
    assert report["semantic_finality_proven"] is False
    assert report["replay_executable"] is False
    assert report["new_write_authority"] is False
    assert report["automatic_retry"] is False
    # C1 must be routed by the Translate domain before the base router.
    translate = (
        ROOT
        / "src/chatgpt_web_adapter/browser_native_extension"
        / "service_worker_google_translate_capability.js"
    ).read_text(encoding="utf-8")
    assert "message?.type === CWA_CAPTURE_V0_SEMANTIC_OPERATION" in translate
    assert "tabIds" not in report
    assert "text" not in report


@pytest.mark.parametrize(
    "changes",
    [
        {"explicit_consent": False},
        {"tab_ids": (101, 101)},
        {"tab_ids": (0, 102)},
        {"tab_ids": (True, 102)},
        {"tab_ids": [101, 102]},
        {"source_language": "en?q=sensitive"},
        {"target_language": "invalid code"},
    ],
)
def test_preflight_fails_without_delegation(changes: dict) -> None:
    bridge = FakeBridge()
    params = {
        "tab_ids": (101, 102),
        "source_language": "en",
        "target_language": "es",
        "explicit_consent": True,
    }
    params.update(changes)
    with pytest.raises(ValueError, match="CAPTURE_C1_"):
        capture_semantic_pair(bridge, **params)
    assert bridge.calls == []


def test_bridge_loss_is_propagated_without_retry() -> None:
    bridge = FakeBridge(
        error=RequestError(
            "BROWSER_NATIVE_BRIDGE_RESPONSE_LOST_AFTER_DELEGATION",
            request_stage="browser_native_bridge",
        )
    )
    with pytest.raises(RequestError, match="RESPONSE_LOST_AFTER_DELEGATION"):
        capture_semantic_pair(
            bridge,
            tab_ids=(101, 102),
            source_language="en",
            target_language="es",
            explicit_consent=True,
        )
    assert len(bridge.calls) == 1


@pytest.mark.parametrize(
    "key,value",
    [
        ("productId", "evil-web"),
        ("captureMode", "AUTO"),
        ("sourceLanguage", "fr"),
        ("targetLanguage", "de"),
        ("selectorProvenance", "LEARNED"),
        ("semanticFinalityProven", True),
        ("canonicalCompletionProven", True),
        ("replayExecutable", True),
        ("newWriteAuthority", True),
        ("automaticRetry", True),
        ("rawContentRetained", True),
    ],
)
def test_tampered_authority_or_identity_is_refused(key: str, value: object) -> None:
    response = _response()
    response[key] = value
    with pytest.raises(ValueError, match="CAPTURE_C1_"):
        _validate(response)


def test_unknown_browser_content_rejected_instead_of_logged() -> None:
    response = _response()
    response["rawText"] = "sensitive content"
    with pytest.raises(ValueError, match="CAPTURE_C1_EXTRA_OR_MISSING_FIELDS"):
        _validate(response)
    response = _response()
    response["observations"][0]["source_input"]["uniqueDescriptor"]["ariaLabel"] = (
        "secret accessibility name"
    )
    with pytest.raises(ValueError, match="CAPTURE_C1_DESCRIPTOR_SHAPE_INVALID"):
        _validate(response)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r["observations"].append(_snapshot()),
        lambda r: r["observations"][0].update({"rawDom": "<html>"}),
        lambda r: r["observations"][0].update({"routeVerified": False}),
        lambda r: r["observations"][0]["source_input"].update({"candidateCount": True}),
        lambda r: r["observations"][0]["source_input"].update({"candidateCount": 9}),
        lambda r: r["observations"][0]["source_input"].update({"candidateCount": 2}),
        lambda r: r["observations"][0]["translated_result"]["uniqueDescriptor"].update(
            {"kind": "textarea"}
        ),
        lambda r: r["observations"][0]["source_input"]["uniqueDescriptor"].update(
            {"region": "unbounded custom string"}
        ),
    ],
)
def test_malformed_observation_rejected(mutator) -> None:
    response = _response()
    mutator(response)
    with pytest.raises(ValueError, match="CAPTURE_C1_"):
        _validate(response)


def test_duplicate_source_candidates_are_ambiguous() -> None:
    response = _response()
    response["observations"][1]["source_input"] = {
        "candidateCount": 2,
        "uniqueDescriptor": None,
    }
    report = _classify(response)
    assert report["observations"]["source_input"]["status"] == "AMBIGUOUS"
    assert report["observations"]["source_input"]["candidate_counts_by_document"] == {
        "A": 1,
        "B": 2,
    }
    assert report["replay_executable"] is False


def test_missing_result_candidate_is_not_silent_success() -> None:
    response = _response()
    response["observations"][1]["translated_result"] = {
        "candidateCount": 0,
        "uniqueDescriptor": None,
    }
    response["observations"][1]["resultFamilyStages"] = {
        "rawFamily": 0,
        "visibleFamily": 0,
        "visibleLeaves": 0,
    }
    report = _classify(response)
    assert report["observations"]["translated_result"]["status"] == "MISSING"
    result_counts = report["observations"]["translated_result"][
        "candidate_counts_by_document"
    ]
    assert result_counts == {
        "A": 1,
        "B": 0,
    }
    assert report["new_write_authority"] is False


def test_region_variation_is_not_called_stable() -> None:
    response = _response()
    response["observations"][1]["translated_result"]["uniqueDescriptor"]["region"] = (
        "center"
    )
    report = _classify(response)
    assert report["observations"]["translated_result"]["status"] == (
        "CHANGED_STRUCTURAL_SIGNATURE"
    )
    assert (
        report["observations"]["translated_result"]["same_signature_in_two_documents"]
        is False
    )


def test_unknown_viewport_region_refuses_stability() -> None:
    response = _response()
    response["observations"][0]["source_input"]["uniqueDescriptor"]["region"] = (
        "unknown"
    )
    assert _classify(response)["observations"]["source_input"]["status"] == (
        "UNRESOLVED_REGION"
    )


def test_node_synthetic_cdp_probe_and_source_syntax() -> None:
    subprocess.run(
        ["node", "--check", str(_JS)], check=True, capture_output=True, text=True
    )
    completed = subprocess.run(
        ["node", str(ROOT / "tools/capability_capture_v0_semantic_dom_fixture.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_missing_both_documents_is_distinct_from_missing_one() -> None:
    response = _response()
    for item in response["observations"]:
        item["translated_result"] = {
            "candidateCount": 0,
            "uniqueDescriptor": None,
        }
        item["resultFamilyStages"] = {
            "rawFamily": 0,
            "visibleFamily": 0,
            "visibleLeaves": 0,
        }
    report = _classify(response)
    slot = report["observations"]["translated_result"]
    assert slot["status"] == "MISSING"
    assert slot["candidate_counts_by_document"] == {"A": 0, "B": 0}
    assert slot["learned_locator_proven"] is False
    assert report["new_write_authority"] is False


def test_missing_in_a_and_ambiguous_in_b_preserves_both_counts() -> None:
    response = _response()
    response["observations"][0]["translated_result"] = {
        "candidateCount": 0,
        "uniqueDescriptor": None,
    }
    response["observations"][0]["resultFamilyStages"] = {
        "rawFamily": 0,
        "visibleFamily": 0,
        "visibleLeaves": 0,
    }
    response["observations"][1]["translated_result"] = {
        "candidateCount": 3,
        "uniqueDescriptor": None,
    }
    response["observations"][1]["resultFamilyStages"] = {
        "rawFamily": 3,
        "visibleFamily": 3,
        "visibleLeaves": 3,
    }
    report = _classify(response)
    slot = report["observations"]["translated_result"]
    assert slot["status"] == "MISSING"
    assert slot["candidate_counts_by_document"] == {"A": 0, "B": 3}
    assert report["replay_executable"] is False
    assert "observedTabId" not in str(report)


def test_selector_family_missing_in_both_documents_is_attributed_to_raw_match() -> None:
    response = _response()
    for item in response["observations"]:
        item["translated_result"] = {
            "candidateCount": 0,
            "uniqueDescriptor": None,
        }
        item["resultFamilyStages"] = {
            "rawFamily": 0,
            "visibleFamily": 0,
            "visibleLeaves": 0,
        }
    result = _classify(response)["observations"]["translated_result"]
    assert result["reference_family_stages_by_document"] == {
        "A": {"rawFamily": 0, "visibleFamily": 0, "visibleLeaves": 0},
        "B": {"rawFamily": 0, "visibleFamily": 0, "visibleLeaves": 0},
    }
    assert result["reference_family_diagnosis_by_document"] == {
        "A": "NO_REFERENCE_SELECTOR_MATCH",
        "B": "NO_REFERENCE_SELECTOR_MATCH",
    }


def test_selector_matches_but_visibility_discards_all() -> None:
    response = _response()
    item = response["observations"][1]
    item["translated_result"] = {
        "candidateCount": 0,
        "uniqueDescriptor": None,
    }
    item["resultFamilyStages"] = {
        "rawFamily": 2,
        "visibleFamily": 0,
        "visibleLeaves": 0,
    }
    result = _classify(response)["observations"]["translated_result"]
    assert result["status"] == "MISSING"
    assert result["reference_family_diagnosis_by_document"] == {
        "A": "VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT",
        "B": "SELECTOR_MATCHES_NOT_VISIBLE",
    }
    assert result["learned_locator_proven"] is False


@pytest.mark.parametrize(
    "stages",
    [
        {"rawFamily": 1, "visibleFamily": 2, "visibleLeaves": 0},
        {"rawFamily": 0, "visibleFamily": 0, "visibleLeaves": 1},
        {"rawFamily": 3, "visibleFamily": 2, "visibleLeaves": 2},
        {"rawFamily": 9, "visibleFamily": 1, "visibleLeaves": 1},
        {"rawFamily": True, "visibleFamily": 1, "visibleLeaves": 1},
        {"rawFamily": 1, "visibleFamily": 1, "visibleLeaves": 1, "text": "secret"},
    ],
)
def test_malformed_or_leaky_result_family_stage_data_fails_closed(
    stages: dict,
) -> None:
    response = _response()
    response["observations"][1]["resultFamilyStages"] = stages
    with pytest.raises(ValueError, match="CAPTURE_C1_RESULT_STAGE"):
        _validate(response)


def test_result_stages_disallow_raw_page_content() -> None:
    response = _response()
    response["observations"][0]["resultFamilyStages"]["rawHtml"] = "<secret>"
    with pytest.raises(ValueError, match="CAPTURE_C1_RESULT_STAGE_SHAPE"):
        _validate(response)
