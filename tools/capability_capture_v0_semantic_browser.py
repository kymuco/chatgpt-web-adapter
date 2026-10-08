"""C1 research: explicit two-tab semantic structure observer; never writes.

Only bounded enums and candidate counts cross the native bridge. Two tab IDs
demonstrate independent page-document observations, not separate OS renderers.
The output cannot establish a unique executable selector or finality.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from typing import Any

from chatgpt_web_adapter.browser_native_provider import BrowserNativeTurnProvider

_OPERATION = "research_capture_translate_semantic_v0"
_RESPONSE = "research_capture_translate_semantic_v0_result"
_LANGUAGE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,19}$")
_SLOTS = ("source_input", "translated_result")
_KINDS = {
    "source_input": {"textarea", "contenteditable"},
    "translated_result": {"span", "div", "other"},
}
_ROLES = {"source_input": "textbox", "translated_result": "result_leaf"}
_REGIONS = {"left", "center", "right", "unknown"}
_RESULT_KEYS = frozenset(
    {
        "schema",
        "productId",
        "captureMode",
        "sourceLanguage",
        "targetLanguage",
        "observations",
        "selectorProvenance",
        "semanticFinalityProven",
        "canonicalCompletionProven",
        "replayExecutable",
        "newWriteAuthority",
        "automaticRetry",
        "rawContentRetained",
    }
)
_OBSERVATION_KEYS = frozenset(
    {"routeVerified", "source_input", "translated_result", "resultFamilyStages"}
)
_STAGE_KEYS = frozenset({"rawFamily", "visibleFamily", "visibleLeaves"})
_SLOT_KEYS = frozenset({"candidateCount", "uniqueDescriptor"})
_DESCRIPTOR_KEYS = frozenset({"role", "kind", "region", "interactable"})


def _lang(value: str) -> str:
    if not isinstance(value, str) or _LANGUAGE.fullmatch(value) is None:
        raise ValueError("CAPTURE_C1_LANGUAGE_INVALID")
    return value


def _slot(value: object, slot: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _SLOT_KEYS:
        raise ValueError("CAPTURE_C1_SLOT_SHAPE_INVALID")
    count = value["candidateCount"]
    descriptor = value["uniqueDescriptor"]
    if type(count) is not int or not 0 <= count <= 8:
        raise ValueError("CAPTURE_C1_CANDIDATE_COUNT_INVALID")
    if count != 1:
        if descriptor is not None:
            raise ValueError("CAPTURE_C1_AMBIGUOUS_DESCRIPTOR_FORBIDDEN")
        return {"candidateCount": count, "uniqueDescriptor": None}
    if not isinstance(descriptor, dict) or set(descriptor) != _DESCRIPTOR_KEYS:
        raise ValueError("CAPTURE_C1_DESCRIPTOR_SHAPE_INVALID")
    if (
        descriptor["role"] != _ROLES[slot]
        or type(descriptor["kind"]) is not str
        or descriptor["kind"] not in _KINDS[slot]
        or type(descriptor["region"]) is not str
        or descriptor["region"] not in _REGIONS
        or type(descriptor["interactable"]) is not bool
        or descriptor["interactable"] is not (slot == "source_input")
    ):
        raise ValueError("CAPTURE_C1_DESCRIPTOR_VALUE_INVALID")
    return {
        "candidateCount": 1,
        "uniqueDescriptor": {
            "role": descriptor["role"],
            "kind": descriptor["kind"],
            "region": descriptor["region"],
            "interactable": descriptor["interactable"],
        },
    }


def _stages(value: object, *, result_count: int) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != _STAGE_KEYS:
        raise ValueError("CAPTURE_C1_RESULT_STAGE_SHAPE_INVALID")
    if any(type(value[k]) is not int or not 0 <= value[k] <= 8 for k in _STAGE_KEYS):
        raise ValueError("CAPTURE_C1_RESULT_STAGE_COUNT_INVALID")
    if not (
        value["rawFamily"] >= value["visibleFamily"] >= value["visibleLeaves"]
        and value["visibleLeaves"] == result_count
    ):
        raise ValueError("CAPTURE_C1_RESULT_STAGE_INCONSISTENT")
    return {name: value[name] for name in ("rawFamily", "visibleFamily", "visibleLeaves")}


def _result_stage_diagnosis(stages: dict[str, int]) -> str:
    if stages["rawFamily"] == 0:
        return "NO_REFERENCE_SELECTOR_MATCH"
    if stages["visibleFamily"] == 0:
        return "SELECTOR_MATCHES_NOT_VISIBLE"
    if stages["visibleLeaves"] == 0:
        return "VISIBLE_FAMILY_WITHOUT_LEAF"
    return "VISIBLE_REFERENCE_FAMILY_LEAF_PRESENT"


def validate_semantic_observation(
    response: dict[str, Any],
    *,
    source_language: str,
    target_language: str,
) -> dict[str, Any]:
    """Require exact bounded evidence; reject arbitrary content/extension fields."""
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise ValueError("CAPTURE_C1_OBSERVATION_FAILED")
    if response.get("type") != _RESPONSE:
        raise ValueError("CAPTURE_C1_RESPONSE_TYPE_INVALID")
    raw = {
        k: v
        for k, v in response.items()
        if k not in {"ok", "type", "request_id", "protocol"}
    }
    if set(raw) != _RESULT_KEYS:
        raise ValueError("CAPTURE_C1_EXTRA_OR_MISSING_FIELDS")
    if (
        raw["schema"] != "CWA_CAPTURE_C1_TWO_DOCUMENT_STRUCTURE_V2"
        or raw["productId"] != "google-translate-web"
        or raw["captureMode"] != "EXPLICIT_TWO_TAB_OBSERVE_ONLY"
        or raw["sourceLanguage"] != _lang(source_language)
        or raw["targetLanguage"] != _lang(target_language)
        or raw["selectorProvenance"] != "HANDWRITTEN_REFERENCE_FAMILIES_NOT_LEARNED"
        or raw["semanticFinalityProven"] is not False
        or raw["canonicalCompletionProven"] is not False
        or raw["replayExecutable"] is not False
        or raw["newWriteAuthority"] is not False
        or raw["automaticRetry"] is not False
        or raw["rawContentRetained"] is not False
    ):
        raise ValueError("CAPTURE_C1_AUTHORITY_OR_IDENTITY_MISMATCH")
    observations = raw["observations"]
    if not isinstance(observations, list) or len(observations) != 2:
        raise ValueError("CAPTURE_C1_TWO_DOCUMENTS_REQUIRED")
    parsed = []
    for value in observations:
        if not isinstance(value, dict) or set(value) != _OBSERVATION_KEYS:
            raise ValueError("CAPTURE_C1_OBSERVATION_SHAPE_INVALID")
        if value["routeVerified"] is not True:
            raise ValueError("CAPTURE_C1_ROUTE_NOT_PROVEN")
        slots = {slot: _slot(value[slot], slot) for slot in _SLOTS}
        parsed.append(
            {
                "routeVerified": True,
                **slots,
                "resultFamilyStages": _stages(
                    value["resultFamilyStages"],
                    result_count=slots["translated_result"]["candidateCount"],
                ),
            }
        )
    return {
        **{k: v for k, v in raw.items() if k != "observations"},
        "observations": parsed,
    }


def classify_semantic_stability(report: dict[str, Any]) -> dict[str, Any]:
    """An observed unique reference-family match is NOT a learned locator."""
    # Revalidate even when invoked independently on a purported sanitized report.
    checked = validate_semantic_observation(
        {"ok": True, "type": _RESPONSE, **report},
        source_language=report.get("sourceLanguage"),
        target_language=report.get("targetLanguage"),
    )
    first, second = checked["observations"]
    comparison = {}
    for slot in _SLOTS:
        a, b = first[slot], second[slot]
        if a["candidateCount"] == 0 or b["candidateCount"] == 0:
            status = "MISSING"
        elif a["candidateCount"] != 1 or b["candidateCount"] != 1:
            status = "AMBIGUOUS"
        elif (
            a["uniqueDescriptor"]["region"] == "unknown"
            or b["uniqueDescriptor"]["region"] == "unknown"
        ):
            status = "UNRESOLVED_REGION"
        elif a["uniqueDescriptor"] != b["uniqueDescriptor"]:
            status = "CHANGED_STRUCTURAL_SIGNATURE"
        else:
            status = "CONSISTENT_REFERENCE_FAMILY_SIGNATURE"
        item = {
            "status": status,
            "candidate_counts_by_document": {
                "A": a["candidateCount"],
                "B": b["candidateCount"],
            },
            "same_signature_in_two_documents": (
                status == "CONSISTENT_REFERENCE_FAMILY_SIGNATURE"
            ),
            "learned_locator_proven": False,
        }
        if slot == "translated_result":
            stages_a = first["resultFamilyStages"]
            stages_b = second["resultFamilyStages"]
            item["reference_family_stages_by_document"] = {
                "A": stages_a,
                "B": stages_b,
            }
            item["reference_family_diagnosis_by_document"] = {
                "A": _result_stage_diagnosis(stages_a),
                "B": _result_stage_diagnosis(stages_b),
            }
        comparison[slot] = item
    return {
        "schema": "CWA_CAPTURE_C1_STRUCTURAL_COMPARISON_V2",
        "observations": comparison,
        "independent_documents_observed": True,
        "independent_renderer_process_proven": False,
        "selector_families_from_capture": False,
        "semantic_finality_proven": False,
        "replay_executable": False,
        "new_write_authority": False,
        "automatic_retry": False,
        "decision": "REPLAY_BLOCKED_NEEDS_INDEPENDENT_LOCATOR_AND_EFFECT_PROOF",
    }


def capture_semantic_pair(
    bridge: BrowserNativeTurnProvider,
    *,
    tab_ids: tuple[int, int],
    source_language: str,
    target_language: str,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    if explicit_consent is not True:
        raise ValueError("CAPTURE_C1_CONSENT_REQUIRED")
    if (
        not isinstance(tab_ids, tuple)
        or len(tab_ids) != 2
        or any(type(t) is not int or t <= 0 for t in tab_ids)
        or tab_ids[0] == tab_ids[1]
    ):
        raise ValueError("CAPTURE_C1_DISTINCT_TAB_IDS_REQUIRED")
    source, target = _lang(source_language), _lang(target_language)
    response = bridge._rpc(  # noqa: SLF001
        {
            "type": _OPERATION,
            "request_id": uuid.uuid4().hex,
            "tabIds": list(tab_ids),
            "sourceLanguage": source,
            "targetLanguage": target,
            "consent": "EXPLICIT_TWO_TAB_OBSERVE_ONLY",
            "timeoutMs": 20000,
        },
        # Broker can spend up to delegated_timeout + 5s awaiting Chrome.
        # Reserve enough time for its explicit timeout response to reach RPC.
        timeout=30.0,
        delegated_timeout_ms_key="timeoutMs",
        delegated_response_margin=10.0,
    )
    checked = validate_semantic_observation(
        response, source_language=source, target_language=target
    )
    return classify_semantic_stability(checked)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Two explicit Google Translate tabs: semantic shape only, no writes"
    )
    parser.add_argument("--tab-id-a", type=int, required=True)
    parser.add_argument("--tab-id-b", type=int, required=True)
    parser.add_argument("--source-language", required=True)
    parser.add_argument("--target-language", required=True)
    parser.add_argument("--i-consent-to-semantic-observation", action="store_true")
    args = parser.parse_args()
    comparison = capture_semantic_pair(
        BrowserNativeTurnProvider(),
        tab_ids=(args.tab_id_a, args.tab_id_b),
        source_language=args.source_language,
        target_language=args.target_language,
        explicit_consent=args.i_consent_to_semantic_observation,
    )
    print(json.dumps(comparison, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
