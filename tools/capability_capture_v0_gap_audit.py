"""Offline admission audit for one saved structural Google Translate demo trace.

It never attaches to the browser, executes product actions, or synthesizes
write authority from human demonstration evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from tools.capability_capture_v0_browser import validate_capture_trace

_LANGUAGE_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,19}$")

# No structural input counter or result-presence sample establishes these
# product-specific facts. They require separately designed Slice C proofs.
_UNPROVEN_REPLAY_REQUIREMENTS = (
    "capture_bound_to_exact_source_text",
    "translation_text_identity_proven",
    "translation_text_stability_proven",
    "generated_locator_replay_proven",
    "explicit_replay_write_authority",
    "post_effect_lost_ack_reconciliation_proven",
)


def audit_structural_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Reject untrusted trace extensions and report only admitted evidence."""
    if not isinstance(trace, dict):
        raise ValueError("CAPTURE_V0_AUDIT_OBJECT_REQUIRED")
    tab_id = trace.get("observedTabId")
    source = trace.get("sourceLanguage")
    target = trace.get("targetLanguage")
    if type(tab_id) is not int or tab_id <= 0:
        raise ValueError("CAPTURE_V0_AUDIT_TAB_ID_INVALID")
    if (
        not isinstance(source, str)
        or _LANGUAGE_CODE.fullmatch(source) is None
        or not isinstance(target, str)
        or _LANGUAGE_CODE.fullmatch(target) is None
    ):
        raise ValueError("CAPTURE_V0_AUDIT_LANGUAGE_IDENTITY_INVALID")

    admitted = validate_capture_trace(
        {
            "ok": True,
            "type": "research_capture_translate_demo_v0_result",
            **trace,
        },
        tab_id=tab_id,
        source_language=source,
        target_language=target,
    )
    if set(trace) != set(admitted):
        raise ValueError("CAPTURE_V0_AUDIT_UNEXPECTED_FIELDS")

    structural = (
        admitted["candidatePresenceStable"] is True
        and admitted["candidateIdentityResolved"] is True
        and [event["phase"] for event in admitted["events"]]
        == [
            "source_ready",
            "source_input_event",
            "result_candidate_seen",
            "result_candidate_presence_stable",
        ]
    )
    observations = (
        (
            "exact_product_and_language_route",
            "human_source_input_event",
            "stable_structural_result_candidate_presence",
        )
        if structural
        else (
            "exact_product_and_language_route",
            "partial_or_incomplete_observation",
        )
    )
    return {
        "schema": "CWA_CAPTURE_V0_REPLAY_ADMISSION_AUDIT",
        "classification": (
            "STRUCTURAL_DEMONSTRATION_ACCEPTED"
            if structural
            else "OBSERVATION_INCOMPLETE"
        ),
        "observed_requirements": list(observations),
        "unproven_requirements": list(_UNPROVEN_REPLAY_REQUIREMENTS),
        "semantic_finality_proven": False,
        "canonical_completion_proven": False,
        "replay_executable": False,
        "write_authority_granted": False,
        "automatic_retry_authorized": False,
        "source": "HUMAN_CAPTURED_STRUCTURE_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline CWA capture → replay admission audit; never replays"
    )
    parser.add_argument("trace_json", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.trace_json.read_text(encoding="utf-8"))
    report = audit_structural_trace(payload)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
