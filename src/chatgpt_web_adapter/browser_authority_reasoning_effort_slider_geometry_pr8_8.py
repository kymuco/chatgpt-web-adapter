from __future__ import annotations

from typing import Any

from .browser_authority_reasoning_effort_slider_pr8_8 import ReasoningEffortSliderProvider

SCHEMA = 1


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_dict(value: Any, limit: int = 32) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rect(value: Any) -> dict[str, int | None]:
    item = _dict(value)
    return {name: _int(item.get(name)) for name in ("x", "y", "width", "height")}


def _control(value: Any) -> dict[str, Any] | None:
    item = _dict(value)
    if not item:
        return None
    return {
        "mode": item.get("mode") if isinstance(item.get("mode"), str) else None,
        "tag": item.get("tag") if isinstance(item.get("tag"), str) else None,
        "role": item.get("role") if isinstance(item.get("role"), str) else None,
        "rect": _rect(item.get("rect")),
        "aria_expanded": item.get("ariaExpanded") if isinstance(item.get("ariaExpanded"), str) else None,
        "data_state": item.get("dataState") if isinstance(item.get("dataState"), str) else None,
    }


def _track(value: Any) -> dict[str, Any] | None:
    item = _dict(value)
    if not item:
        return None
    return {
        "tag": item.get("tag") if isinstance(item.get("tag"), str) else None,
        "role": item.get("role") if isinstance(item.get("role"), str) else None,
        "rect": _rect(item.get("rect")),
        "relation_to_thumb": item.get("relationToThumb") if isinstance(item.get("relationToThumb"), str) else None,
        "axis_length_px": _int(item.get("axisLengthPx")),
        "cross_length_px": _int(item.get("crossLengthPx")),
        "cross_offset_px": _int(item.get("crossOffsetPx")),
        "thumb_center_inside_axis": item.get("thumbCenterInsideAxis") is True,
    }


def _parse_topology(value: Any) -> dict[str, Any]:
    item = _dict(value)
    slider = _dict(item.get("primarySlider"))
    aria = _dict(item.get("ariaRangeSemantics"))
    labels = []
    for label in _list_dict(item.get("effortLabels"), 16):
        labels.append({
            "mode": label.get("mode") if isinstance(label.get("mode"), str) else None,
            "tag": label.get("tag") if isinstance(label.get("tag"), str) else None,
            "role": label.get("role") if isinstance(label.get("role"), str) else None,
            "rect": _rect(label.get("rect")),
            "distance_to_track_px": _int(label.get("distanceToTrackPx")),
            "normalized_position": _number(label.get("normalizedPosition")),
        })
    mapping = []
    for step in _list_dict(item.get("orderedStepMapping"), 8):
        mapping.append({
            "mode": step.get("mode") if isinstance(step.get("mode"), str) else None,
            "rank": _int(step.get("rank")),
            "aria_step_candidate": _number(step.get("ariaStepCandidate")),
            "normalized_position": _number(step.get("normalizedPosition")),
        })
    logical = []
    for group in _list_dict(item.get("advancedLogicalControls"), 8):
        candidates = []
        for candidate in _list_dict(group.get("candidates"), 8):
            candidates.append({
                "index": _int(candidate.get("index")),
                "tag": candidate.get("tag") if isinstance(candidate.get("tag"), str) else None,
                "role": candidate.get("role") if isinstance(candidate.get("role"), str) else None,
                "rect": _rect(candidate.get("rect")),
                "actionable": candidate.get("actionable") is True,
                "disabled": candidate.get("disabled") is True,
                "pointer_events_enabled": candidate.get("pointerEventsEnabled") is True,
            })
        preferred = _dict(group.get("preferredTarget"))
        logical.append({
            "index": _int(group.get("index")),
            "candidate_count": _int(group.get("candidateCount")),
            "actionable_candidate_count": _int(group.get("actionableCandidateCount")),
            "candidates": candidates,
            "preferred_target": {
                "tag": preferred.get("tag") if isinstance(preferred.get("tag"), str) else None,
                "role": preferred.get("role") if isinstance(preferred.get("role"), str) else None,
                "rect": _rect(preferred.get("rect")),
                "actionable": preferred.get("actionable") is True,
            } if preferred else None,
        })
    return {
        "current_effort_control": _control(item.get("currentEffortControl")),
        "slider_candidate_count": _int(item.get("sliderCandidateCount")),
        "primary_slider": {
            "tag": slider.get("tag") if isinstance(slider.get("tag"), str) else None,
            "role": slider.get("role") if isinstance(slider.get("role"), str) else None,
            "rect": _rect(slider.get("rect")),
            "orientation": slider.get("orientation") if isinstance(slider.get("orientation"), str) else None,
            "aria_value_min": _number(slider.get("ariaValueMin")),
            "aria_value_max": _number(slider.get("ariaValueMax")),
            "aria_value_now": _number(slider.get("ariaValueNow")),
            "discrete": slider.get("discrete") is True,
            "step_count": _int(slider.get("stepCount")),
        } if slider else None,
        "thumb_geometry_proven": item.get("thumbGeometryProven") is True,
        "aria_range_semantics": {
            "min": _number(aria.get("min")),
            "max": _number(aria.get("max")),
            "now": _number(aria.get("now")),
            "discrete": aria.get("discrete") is True,
            "step_count": _int(aria.get("stepCount")),
            "current_step_index": _number(aria.get("currentStepIndex")),
        } if aria else None,
        "track_candidate_count": _int(item.get("trackCandidateCount")),
        "track_candidates": [_track(x) for x in _list_dict(item.get("trackCandidates"), 12)],
        "best_track": _track(item.get("bestTrack")),
        "effort_labels": labels,
        "recognized_effort_modes": [x for x in item.get("recognizedEffortModes", []) if isinstance(x, str)] if isinstance(item.get("recognizedEffortModes"), list) else [],
        "ordered_step_mapping": mapping,
        "current_step_consistent": item.get("currentStepConsistent") is True,
        "full_three_step_mapping_proven": item.get("fullThreeStepMappingProven") is True,
        "advanced_dom_candidate_count": _int(item.get("advancedDomCandidateCount")),
        "advanced_logical_control_count": _int(item.get("advancedLogicalControlCount")),
        "advanced_logical_controls": logical,
        "advanced_dealiased": item.get("advancedDealiased") is True,
        "selection_control_click_performed": item.get("selectionControlClickPerformed") is True,
        "ui_navigation_click_performed": item.get("uiNavigationClickPerformed") is True,
    }


class ReasoningEffortSliderGeometryProvider(ReasoningEffortSliderProvider):
    def reasoning_effort_geometry_support(self, *, timeout: float = 5.0) -> dict[str, Any]:
        result = self._characterization_rpc(
            {"characterizeReasoningEffortGeometrySupport": True}, timeout=timeout
        )
        return {
            "supported": result.get("reasoningEffortGeometrySupported") is True,
            "schema": _int(result.get("reasoningEffortGeometrySchemaVersion")),
            "thumb_track_separation_supported": result.get("thumbTrackSeparationSupported") is True,
            "aria_discrete_range_semantics_supported": result.get("ariaDiscreteRangeSemanticsSupported") is True,
            "sibling_tick_association_supported": result.get("siblingTickAssociationSupported") is True,
            "advanced_control_dealiasing_supported": result.get("advancedControlDealiasingSupported") is True,
            "retained_existing_tab_probe_supported": result.get("retainedExistingTabProbeSupported") is True,
            "selection_control_click_forbidden": result.get("selectionControlClickForbidden") is True,
            "ui_navigation_click_forbidden": result.get("uiNavigationClickForbidden") is True,
            "zero_product_writes": result.get("zeroProductWrites") is True,
            "automatic_retry": result.get("automaticRetry") is True,
            "raw_text_redaction_supported": result.get("rawTextRedactionSupported") is True,
            "lease_id_exported": result.get("leaseIdExported") is True,
        }

    def reasoning_effort_geometry(
        self,
        conversation_id: str,
        *,
        expected_runtime_tab_id: int,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        result = self._characterization_rpc(
            {
                "characterizeReasoningEffortGeometry": True,
                "conversationId": conversation_id,
                "expectedRuntimeTabId": expected_runtime_tab_id,
            },
            timeout=timeout,
        )
        return {
            "conversation_id": result.get("conversationId"),
            "runtime_tab_id": _int(result.get("runtimeTabId")),
            "runtime_tab_id_after": _int(result.get("runtimeTabIdAfter")),
            "lease_id_present": result.get("leaseIdPresent") is True,
            "raw_url_exported": result.get("rawUrlExported") is True,
            "raw_text_exported": result.get("rawTextExported") is True,
            "raw_html_exported": result.get("rawHtmlExported") is True,
            "lease_id_exported": result.get("leaseIdExported") is True,
            "zero_product_writes": result.get("zeroProductWrites") is True,
            "conversation_write_count": _int(result.get("conversationWriteCount")),
            "chatgpt_mutation_count": _int(result.get("chatgptMutationCount")),
            "automatic_retry": result.get("automaticRetry") is True,
            "topology": _parse_topology(result.get("topology")),
        }
