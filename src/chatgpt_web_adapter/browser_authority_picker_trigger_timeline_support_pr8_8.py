from __future__ import annotations

from .browser_authority_instant_failure_forensics_failure_pr8_8 import (
    characterize_failure as _base_characterize_failure,
)
from .browser_authority_instant_failure_forensics_preflight_pr8_8 import (
    run_preflight as _base_run_preflight,
)
from .browser_authority_instant_failure_forensics_support_pr8_8 import (
    InstantFailureForensicsProvider,
    _dict,
    _int,
    _list,
    _require,
    _str,
)

TRIGGER_TIMELINE_SCHEMA = 1


def _rect(value):
    x = _dict(value)
    return {key: _int(x.get(key)) for key in ("x", "y", "width", "height")}


def _control(value):
    x = _dict(value)
    if not x:
        return None
    return {
        "tag": _str(x.get("tag")),
        "role": _str(x.get("role")),
        "direct_modes": _list(x.get("directModes")),
        "subtree_modes": _list(x.get("subtreeModes")),
        "aria_haspopup": _str(x.get("ariaHaspopup")),
        "aria_expanded": _str(x.get("ariaExpanded")),
        "data_state": _str(x.get("dataState")),
        "disabled": x.get("disabled") is True,
        "pointer_events_enabled": x.get("pointerEventsEnabled") is True,
        "child_element_count": _int(x.get("childElementCount")) or 0,
        "rect": _rect(x.get("rect")),
    }


def _surface(value):
    x = _dict(value)
    if not x:
        return None
    return {
        "tag": _str(x.get("tag")),
        "role": _str(x.get("role")),
        "known_mode_descendant_count": _int(x.get("knownModeDescendantCount")) or 0,
        "actionable_descendant_count": _int(x.get("actionableDescendantCount")) or 0,
        "recognized_modes": _list(x.get("recognizedModes")),
        "rect": _rect(x.get("rect")),
    }


def _timeline_sample(value):
    x = _dict(value)
    if not x:
        return None
    return {
        "phase": _str(x.get("phase")),
        "poll_index": _int(x.get("pollIndex")),
        "elapsed_ms": _int(x.get("elapsedMs")),
        "option_found": x.get("optionFound") is True,
        "option_candidate_count": _int(x.get("optionCandidateCount")) or 0,
        "picker_candidate_found": x.get("pickerCandidateFound") is True,
        "picker_candidate": _control(x.get("pickerCandidate")),
        "nearest_menu_trigger_found": x.get("nearestMenuTriggerFound") is True,
        "nearest_menu_trigger_hops": _int(x.get("nearestMenuTriggerHops")),
        "nearest_menu_trigger": _control(x.get("nearestMenuTrigger")),
        "trigger_open_signal": x.get("triggerOpenSignal") is True,
        "generic_popup_surface_count": _int(x.get("genericPopupSurfaceCount")) or 0,
        "generic_menu_surface_count": _int(x.get("genericMenuSurfaceCount")) or 0,
        "mode_bearing_popup_surface_count": _int(x.get("modeBearingPopupSurfaceCount")) or 0,
        "recognized_modes": _list(x.get("recognizedModes")),
        "max_known_mode_descendant_count": _int(x.get("maxKnownModeDescendantCount")) or 0,
        "mode_picker_materialized": x.get("modePickerMaterialized") is True,
        "false_open_generic_only": x.get("falseOpenGenericOnly") is True,
        "selected_mode_surface": _surface(x.get("selectedModeSurface")),
    }


def _trigger_timeline(value):
    x = _dict(value)
    if not x:
        return None
    raw_samples = x.get("timelineSamples")
    samples = []
    if isinstance(raw_samples, list):
        for item in raw_samples[:96]:
            parsed = _timeline_sample(item)
            if parsed is not None:
                samples.append(parsed)
    best = _dict(x.get("bestSeen"))
    return {
        "schema": _int(x.get("schemaVersion")),
        "captured_at_failure": x.get("capturedAtFailure") is True,
        "failure_code": _str(x.get("failureCode")),
        "failure_reason": _str(x.get("failureReason")),
        "capture_status": _str(x.get("captureStatus")),
        "capture_tab_id": _int(x.get("captureTabId")),
        "route_kind": _str(x.get("routeKind")),
        "observed_conversation_id": _str(x.get("observedConversationId")),
        "picker_mode": _str(x.get("pickerMode")),
        "picker_point_available": x.get("pickerPointAvailable") is True,
        "click_dispatch_completed": x.get("clickDispatchCompleted") is True,
        "picker_click_elapsed_ms": _int(x.get("pickerClickElapsedMs")),
        "timeline_sample_count": _int(x.get("timelineSampleCount")) or 0,
        "poll_sample_count": _int(x.get("pollSampleCount")) or 0,
        "timeline_samples": samples,
        "timeline_samples_truncated": x.get("timelineSamplesTruncated") is True,
        "best_seen": {
            "recognized_modes": _list(best.get("recognizedModes")),
            "max_mode_bearing_popup_surface_count": _int(best.get("maxModeBearingPopupSurfaceCount")) or 0,
            "max_known_mode_descendant_count": _int(best.get("maxKnownModeDescendantCount")) or 0,
            "first_mode_bearing_popup_seen_ms": _int(best.get("firstModeBearingPopupSeenMs")),
            "last_mode_bearing_popup_seen_ms": _int(best.get("lastModeBearingPopupSeenMs")),
            "first_trigger_open_signal_ms": _int(best.get("firstTriggerOpenSignalMs")),
            "trigger_state_transition_observed": best.get("triggerStateTransitionObserved") is True,
            "false_open_generic_only_observed": best.get("falseOpenGenericOnlyObserved") is True,
            "best_selected_surface": _surface(best.get("bestSelectedSurface")),
        },
        "materialization_outcome": _str(x.get("materializationOutcome")),
        "raw_url_exported": x.get("rawUrlExported") is True,
        "raw_text_exported": x.get("rawTextExported") is True,
        "raw_html_exported": x.get("rawHtmlExported") is True,
        "lease_id_exported": x.get("leaseIdExported") is True,
        "zero_product_writes": x.get("zeroProductWrites") is True,
        "automatic_retry": x.get("automaticRetry") is True,
    }


class PickerTriggerTimelineForensicsProvider(InstantFailureForensicsProvider):
    """Additive parser for PR8.8 picker-trigger timeline evidence."""

    def instant_failure_forensics_support(self):
        base = super().instant_failure_forensics_support()
        raw = self._characterization_rpc(
            {"characterizeInstantFailureForensicsSupport": True, "timeoutMs": 3000},
            timeout=max(1.0, self.connect_timeout),
        )
        base.update({
            "picker_trigger_identity_supported": raw.get("pickerTriggerIdentitySupported") is True,
            "click_actuation_verification_supported": raw.get("clickActuationVerificationSupported") is True,
            "per_poll_menu_materialization_timeline_supported": raw.get("perPollMenuMaterializationTimelineSupported") is True,
            "false_open_surface_dealiasing_supported": raw.get("falseOpenSurfaceDealiasingSupported") is True,
            "trigger_timeline_persistence_supported": raw.get("triggerTimelinePersistenceSupported") is True,
            "raw_trigger_text_redaction_supported": raw.get("rawTriggerTextRedactionSupported") is True,
        })
        return base

    def instant_failure_forensics_record(self, lease_id, *, timeout=5.0):
        base = super().instant_failure_forensics_record(lease_id, timeout=timeout)
        raw = self._characterization_rpc(
            {
                "characterizeInstantFailureForensicsRecord": True,
                "expectedBrowserAuthorityLeaseId": lease_id.strip(),
                "timeoutMs": int(timeout * 1000),
            },
            timeout=timeout,
        )
        available = raw.get("triggerTimelineRecordAvailable") is True
        base["trigger_timeline_record_available"] = available
        base["trigger_timeline"] = _trigger_timeline(raw.get("triggerTimeline")) if available else None
        return base


