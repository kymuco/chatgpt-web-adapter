from __future__ import annotations

from typing import Any

from .browser_authority_retained_picker_forensics_pr8_8 import RetainedPickerForensicsProvider

SCHEMA = 1


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_dict(value: Any, limit: int = 32) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _rect(value: Any) -> dict[str, int | None]:
    x = _dict(value)
    return {key: _int(x.get(key)) for key in ("x", "y", "width", "height")}


def _control(value: Any) -> dict[str, Any] | None:
    x = _dict(value)
    if not x:
        return None
    return {
        "tag": _str(x.get("tag")),
        "role": _str(x.get("role")),
        "rect": _rect(x.get("rect")),
        "effort_mode": _str(x.get("effortMode")),
        "dimension": _str(x.get("dimension")),
        "aria_haspopup": _str(x.get("ariaHaspopup")),
        "aria_expanded": _str(x.get("ariaExpanded")),
        "data_state": _str(x.get("dataState")),
        "disabled": x.get("disabled") is True,
        "pointer_events_enabled": x.get("pointerEventsEnabled") is True,
        "child_element_count": _int(x.get("childElementCount")) or 0,
        "nearest_distance_px": _int(x.get("nearestDistancePx")),
    }


def _quick(value: Any) -> dict[str, Any]:
    x = _dict(value)
    sliders = []
    for item in _list_dict(x.get("sliders"), 8):
        sliders.append({
            "index": _int(item.get("index")),
            "tag": _str(item.get("tag")),
            "role": _str(item.get("role")),
            "rect": _rect(item.get("rect")),
            "orientation": _str(item.get("orientation")),
            "aria_value_min": _number(item.get("ariaValueMin")),
            "aria_value_max": _number(item.get("ariaValueMax")),
            "aria_value_now": _number(item.get("ariaValueNow")),
            "aria_value_text_mode": _str(item.get("ariaValueTextMode")),
            "native_min": _number(item.get("nativeMin")),
            "native_max": _number(item.get("nativeMax")),
            "native_value": _number(item.get("nativeValue")),
            "native_step": _number(item.get("nativeStep")),
            "disabled": item.get("disabled") is True,
        })
    marks = []
    for item in _list_dict(x.get("effortMarks"), 16):
        marks.append({
            "mode": _str(item.get("mode")),
            "tag": _str(item.get("tag")),
            "role": _str(item.get("role")),
            "rect": _rect(item.get("rect")),
            "nearest_slider_index": _int(item.get("nearestSliderIndex")),
            "nearest_slider_distance_px": _int(item.get("nearestSliderDistancePx")),
            "normalized_position": _number(item.get("normalizedPosition")),
        })
    mapping = []
    for item in _list_dict(x.get("discreteStepMapping"), 8):
        mapping.append({
            "mode": _str(item.get("mode")),
            "rank": _int(item.get("rank")),
            "normalized_position": _number(item.get("normalizedPosition")),
        })
    surface = _dict(x.get("selectedSurface"))
    return {
        "surface_found": x.get("surfaceFound") is True,
        "generic_surface_count": _int(x.get("genericSurfaceCount")) or 0,
        "mode_bearing_surface_count": _int(x.get("modeBearingSurfaceCount")) or 0,
        "slider_surface_count": _int(x.get("sliderSurfaceCount")) or 0,
        "selected_surface": {
            "tag": _str(surface.get("tag")), "role": _str(surface.get("role")),
            "rect": _rect(surface.get("rect")),
            "recognized_effort_modes": [v for v in surface.get("recognizedEffortModes", []) if isinstance(v, str)],
            "visible_element_count": _int(surface.get("visibleElementCount")) or 0,
        } if surface else None,
        "current_effort_control": _control(x.get("currentEffortControl")),
        "current_effort_candidate_count": _int(x.get("currentEffortCandidateCount")) or 0,
        "sliders": sliders,
        "effort_marks": marks,
        "discrete_step_mapping": mapping,
        "complete_three_step_mapping": x.get("completeThreeStepMapping") is True,
        "advanced_button_count": _int(x.get("advancedButtonCount")) or 0,
        "advanced_button": _control(x.get("advancedButton")),
    }


def _advanced(value: Any) -> dict[str, Any] | None:
    x = _dict(value)
    if not x:
        return None
    surface = _dict(x.get("selectedSurface"))
    controls = []
    for item in _list_dict(x.get("dimensionControls"), 12):
        parsed = _control(item) or {}
        parsed["dimension"] = _str(item.get("dimension"))
        controls.append(parsed)
    return {
        "surface_found": x.get("surfaceFound") is True,
        "candidate_surface_count": _int(x.get("candidateSurfaceCount")) or 0,
        "selected_surface": {
            "tag": _str(surface.get("tag")), "role": _str(surface.get("role")),
            "rect": _rect(surface.get("rect")),
            "visible_element_count": _int(surface.get("visibleElementCount")) or 0,
        } if surface else None,
        "dimension_controls": controls,
        "model_control_count": _int(x.get("modelControlCount")) or 0,
        "effort_control_count": _int(x.get("effortControlCount")) or 0,
        "back_control_count": _int(x.get("backControlCount")) or 0,
        "dimensions_separated": x.get("dimensionsSeparated") is True,
        "visible_model_values": [v for v in x.get("visibleModelValues", []) if isinstance(v, str)],
        "visible_effort_values": [v for v in x.get("visibleEffortValues", []) if isinstance(v, str)],
    }


class ReasoningEffortSliderProvider(RetainedPickerForensicsProvider):
    def reasoning_effort_slider_support(self) -> dict[str, Any]:
        r = self._characterization_rpc(
            {"characterizeReasoningEffortSliderSupport": True, "timeoutMs": 3000},
            timeout=max(1.0, self.connect_timeout),
        )
        return {
            "supported": r.get("reasoningEffortSliderSupported") is True,
            "schema": _int(r.get("reasoningEffortSliderSchemaVersion")),
            "retained_existing_tab_probe_supported": r.get("retainedExistingTabProbeSupported") is True,
            "slider_topology_supported": r.get("sliderTopologySupported") is True,
            "discrete_step_mapping_supported": r.get("discreteStepMappingSupported") is True,
            "quick_advanced_dimension_separation_supported": r.get("quickAdvancedDimensionSeparationSupported") is True,
            "ui_navigation_opt_in_supported": r.get("uiNavigationOptInSupported") is True,
            "selection_control_click_forbidden": r.get("selectionControlClickForbidden") is True,
            "conversation_write_guard_supported": r.get("conversationWriteGuardSupported") is True,
            "raw_text_redaction_supported": r.get("rawTextRedactionSupported") is True,
            "lease_id_exported": r.get("leaseIdExported") is True,
            "zero_product_writes": r.get("zeroProductWrites") is True,
            "automatic_retry": r.get("automaticRetry") is True,
        }

    def reasoning_effort_slider_topology(
        self,
        conversation: str,
        *,
        expected_runtime_tab_id: int,
        open_quick_picker: bool = False,
        inspect_advanced_surface: bool = False,
        allow_ui_navigation: bool = False,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        if not isinstance(conversation, str) or not conversation.strip():
            raise ValueError("conversation is required")
        if not isinstance(expected_runtime_tab_id, int) or isinstance(expected_runtime_tab_id, bool):
            raise ValueError("expected_runtime_tab_id must be int")
        payload = {
            "characterizeReasoningEffortSliderTopology": True,
            "conversationId": conversation.strip(),
            "expectedRuntimeTabId": expected_runtime_tab_id,
            "openQuickPicker": open_quick_picker,
            "inspectAdvancedSurface": inspect_advanced_surface,
            "allowUiNavigation": allow_ui_navigation,
            "timeoutMs": int(timeout * 1000),
        }
        r = self._characterization_rpc(payload, timeout=timeout)
        return {
            "conversation_id": _str(r.get("conversationId")),
            "runtime_tab_id": _int(r.get("runtimeTabId")),
            "runtime_tab_id_after": _int(r.get("runtimeTabIdAfter")),
            "lease_id_present": r.get("leaseIdPresent") is True,
            "raw_url_exported": r.get("rawUrlExported") is True,
            "raw_text_exported": r.get("rawTextExported") is True,
            "raw_html_exported": r.get("rawHtmlExported") is True,
            "lease_id_exported": r.get("leaseIdExported") is True,
            "zero_product_writes": r.get("zeroProductWrites") is True,
            "conversation_write_count": _int(r.get("conversationWriteCount")) or 0,
            "chatgpt_mutation_count": _int(r.get("chatgptMutationCount")) or 0,
            "ui_navigation_acknowledged": r.get("uiNavigationAcknowledged") is True,
            "quick_open_click_performed": r.get("quickOpenClickPerformed") is True,
            "advanced_click_performed": r.get("advancedClickPerformed") is True,
            "selection_control_click_performed": r.get("selectionControlClickPerformed") is True,
            "quick_topology": _quick(r.get("quickTopology")),
            "advanced_topology": _advanced(r.get("advancedTopology")),
        }
