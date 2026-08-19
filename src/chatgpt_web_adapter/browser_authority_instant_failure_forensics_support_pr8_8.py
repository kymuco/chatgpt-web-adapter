from __future__ import annotations
from .browser_authority_retained_route_identity_pr8_8 import RetainedRouteIdentityProvider
SCHEMA = 1
POPUP_SUBTREE_SCHEMA = 1

def _int(value):
    return value if isinstance(value, int) and (not isinstance(value, bool)) else None

def _str(value):
    return value if isinstance(value, str) and value else None

def _dict(value):
    return value if isinstance(value, dict) else {}

def _list(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

def _dict_list(value, limit):
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]

def _require(condition, message):
    if not condition:
        raise RuntimeError(message)

def _rect(value):
    x = _dict(value)
    return {key: _int(x.get(key)) for key in ('x', 'y', 'width', 'height')}

def _actionable(value):
    x = _dict(value)
    if not x:
        return None
    return {
        'tag': _str(x.get('tag')),
        'role': _str(x.get('role')),
        'direct_modes': _list(x.get('directModes')),
        'subtree_modes': _list(x.get('subtreeModes')),
        'aria_checked': _str(x.get('ariaChecked')),
        'aria_selected': _str(x.get('ariaSelected')),
        'aria_expanded': _str(x.get('ariaExpanded')),
        'aria_haspopup': _str(x.get('ariaHaspopup')),
        'data_state': _str(x.get('dataState')),
        'disabled': x.get('disabled') is True,
        'pointer_events_enabled': x.get('pointerEventsEnabled') is True,
        'rect': _rect(x.get('rect')),
        'child_element_count': _int(x.get('childElementCount')) or 0,
        'mode_bearing_descendant_modes': _list(x.get('modeBearingDescendantModes')),
        'mode_bearing_descendant_count': _int(x.get('modeBearingDescendantCount')) or 0,
    }

def _popup_subtree(value):
    x = _dict(value)
    if not x:
        return None
    topology = _dict(x.get('topology'))
    selected = _dict(topology.get('selectedSurface'))
    mode_labels = []
    for item in _dict_list(topology.get('modeLabels'), 16):
        mode_labels.append({
            'mode': _str(item.get('mode')),
            'evidence': _str(item.get('evidence')),
            'tag': _str(item.get('tag')),
            'role': _str(item.get('role')),
            'rect': _rect(item.get('rect')),
            'actionable_ancestor_found': item.get('actionableAncestorFound') is True,
            'actionable_ancestor_hops': _int(item.get('actionableAncestorHops')),
            'actionable_ancestor': _actionable(item.get('actionableAncestor')),
        })
    actionables = [_actionable(item) for item in _dict_list(topology.get('actionableDescendants'), 32)]
    actionables = [item for item in actionables if item is not None]
    surfaces = []
    for item in _dict_list(topology.get('candidateSurfaces'), 8):
        surfaces.append({
            'tag': _str(item.get('tag')),
            'role': _str(item.get('role')),
            'known_mode_descendant_count': _int(item.get('knownModeDescendantCount')) or 0,
            'actionable_descendant_count': _int(item.get('actionableDescendantCount')) or 0,
            'rect': _rect(item.get('rect')),
        })
    return {
        'schema': _int(x.get('schemaVersion')),
        'captured_at_failure': x.get('capturedAtFailure') is True,
        'failure_code': _str(x.get('failureCode')),
        'failure_reason': _str(x.get('failureReason')),
        'capture_status': _str(x.get('captureStatus')),
        'capture_tab_id': _int(x.get('captureTabId')),
        'route_kind': _str(x.get('routeKind')),
        'observed_conversation_id': _str(x.get('observedConversationId')),
        'raw_url_exported': x.get('rawUrlExported') is True,
        'raw_text_exported': x.get('rawTextExported') is True,
        'raw_html_exported': x.get('rawHtmlExported') is True,
        'lease_id_exported': x.get('leaseIdExported') is True,
        'zero_product_writes': x.get('zeroProductWrites') is True,
        'automatic_retry': x.get('automaticRetry') is True,
        'candidate_cap_dealiased': x.get('candidateCapDealiased') is True,
        'global_candidate_cap_used': x.get('globalCandidateCapUsed') is True,
        'surface_found': topology.get('surfaceFound') is True,
        'surface_selection_status': _str(topology.get('surfaceSelectionStatus')),
        'candidate_surface_count': _int(topology.get('candidateSurfaceCount')) or 0,
        'candidate_surfaces': surfaces,
        'candidate_surfaces_truncated': topology.get('candidateSurfacesTruncated') is True,
        'selected_surface': {
            'tag': _str(selected.get('tag')),
            'role': _str(selected.get('role')),
            'known_mode_descendant_count': _int(selected.get('knownModeDescendantCount')) or 0,
            'actionable_descendant_count': _int(selected.get('actionableDescendantCount')) or 0,
            'rect': _rect(selected.get('rect')),
        } if selected else None,
        'recognized_modes': _list(topology.get('recognizedModes')),
        'popup_subtree_visible_element_count': _int(topology.get('popupSubtreeVisibleElementCount')) or 0,
        'mode_label_count': _int(topology.get('modeLabelCount')) or 0,
        'mode_labels': mode_labels,
        'mode_labels_truncated': topology.get('modeLabelsTruncated') is True,
        'actionable_descendant_count': _int(topology.get('actionableDescendantCount')) or 0,
        'actionable_descendants': actionables,
        'actionable_descendants_truncated': topology.get('actionableDescendantsTruncated') is True,
    }

class InstantFailureForensicsProvider(RetainedRouteIdentityProvider):

    def instant_failure_forensics_support(self):
        r = self._characterization_rpc({'characterizeInstantFailureForensicsSupport': True, 'timeoutMs': 3000}, timeout=max(1.0, self.connect_timeout))
        return {
            'supported': r.get('instantFailureForensicsSupported') is True,
            'schema': _int(r.get('instantFailureForensicsSchemaVersion')),
            'failure_record_persistence_supported': r.get('failureRecordPersistenceSupported') is True,
            'pre_input_failure_boundary_supported': r.get('preInputFailureBoundarySupported') is True,
            'retained_route_forensics_composition_supported': r.get('retainedRouteForensicsCompositionSupported') is True,
            'retained_picker_forensics_composition_supported': r.get('retainedPickerForensicsCompositionSupported') is True,
            'raw_error_redaction_supported': r.get('rawErrorRedactionSupported') is True,
            'lease_id_exported': r.get('leaseIdExported') is True,
            'zero_product_writes': r.get('zeroProductWrites') is True,
            'automatic_retry': r.get('automaticRetry') is True,
            'popup_subtree_capture_supported': r.get('popupSubtreeCaptureSupported') is True,
            'popup_local_traversal_supported': r.get('popupLocalTraversalSupported') is True,
            'mode_label_actionable_ancestor_mapping_supported': r.get('modeLabelActionableAncestorMappingSupported') is True,
            'candidate_cap_dealiasing_supported': r.get('candidateCapDealiasingSupported') is True,
            'popup_evidence_persistence_supported': r.get('popupEvidencePersistenceSupported') is True,
            'raw_popup_text_redaction_supported': r.get('rawPopupTextRedactionSupported') is True,
        }

    def instant_failure_forensics_record(self, lease_id, *, timeout=5.0):
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError('lease_id is required')
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        r = self._characterization_rpc({'characterizeInstantFailureForensicsRecord': True, 'expectedBrowserAuthorityLeaseId': lease_id.strip(), 'timeoutMs': int(timeout * 1000)}, timeout=timeout)
        selection = _dict(r.get('selection'))
        popup_available = r.get('popupSubtreeRecordAvailable') is True
        return {
            'failure_captured': r.get('failureCaptured') is True,
            'failure_code': _str(r.get('failureCode')),
            'failure_reason': _str(r.get('failureReason')),
            'pre_input_failure_boundary_proven': r.get('preInputFailureBoundaryProven') is True,
            'prompt_insertion_reached': r.get('promptInsertionReached') is True,
            'submit_reached': r.get('submitReached') is True,
            'raw_error_exported': r.get('rawErrorExported') is True,
            'lease_id_exported': r.get('leaseIdExported') is True,
            'zero_product_writes': r.get('zeroProductWrites') is True,
            'automatic_retry': r.get('automaticRetry') is True,
            'popup_subtree_record_available': popup_available,
            'popup_subtree': _popup_subtree(r.get('popupSubtree')) if popup_available else None,
            'selection': {
                'requested_model_mode': _str(selection.get('requestedModelMode')),
                'selected_mode_before_selection': _str(selection.get('selectedModeBeforeSelection')),
                'selected_mode_before_selection_proven': selection.get('selectedModeBeforeSelectionProven') is True,
                'selected_mode_before_selection_proof_kind': _str(selection.get('selectedModeBeforeSelectionProofKind')),
                'selected_mode_before_selection_candidate_count': _int(selection.get('selectedModeBeforeSelectionCandidateCount')) or 0,
                'selection_performed': selection.get('selectionPerformed') is True,
                'selection_elapsed_ms': _int(selection.get('selectionElapsedMs')),
                'selection_mutation_elapsed_ms': _int(selection.get('selectionMutationElapsedMs')),
                'picker_mode_before_click': _str(selection.get('pickerModeBeforeClick')),
                'picker_candidate_count': _int(selection.get('pickerCandidateCount')) or 0,
                'picker_nearest_distance_px': _int(selection.get('pickerNearestDistancePx')),
                'instant_option_candidate_count': _int(selection.get('instantOptionCandidateCount')) or 0,
                'selected_mode_after_selection': _str(selection.get('selectedModeAfterSelection')),
                'selected_mode_after_selection_proven': selection.get('selectedModeAfterSelectionProven') is True,
                'selection_complete': selection.get('selectionComplete') is True,
                'conversation_write_boundary_observed': selection.get('conversationWriteBoundaryObserved') is True,
                'unexpected_conversation_write_before_selection_complete': selection.get('unexpectedConversationWriteBeforeSelectionComplete') is True,
                'conversation_write_count_during_selection': _int(selection.get('conversationWriteCountDuringSelection')) or 0,
                'network_request_count_during_selection': _int(selection.get('networkRequestCountDuringSelection')) or 0,
                'chatgpt_request_count_during_selection': _int(selection.get('chatgptRequestCountDuringSelection')) or 0,
                'chatgpt_mutating_non_conversation_request_count': _int(selection.get('chatgptMutatingNonConversationRequestCount')) or 0,
                'setting_like_mutation_observed': selection.get('settingLikeMutationObserved') is True,
                'request_classes': _list(selection.get('requestClasses')),
                'model_selection_materialization_status': _str(selection.get('modelSelectionMaterializationStatus')),
            },
        }

def _validate_route(record, conversation, tab_id):
    _require(record.get('conversation_id') == conversation, 'PR8_8_FRESH_FORENSICS_ROUTE_CONVERSATION_RECORD_MISMATCH')
    _require(record.get('runtime_tab_id') == tab_id == record.get('runtime_tab_id_after'), 'PR8_8_FRESH_FORENSICS_ROUTE_TAB_CHANGED')
    _require(record.get('runtime_tab_retained') is True, 'PR8_8_FRESH_FORENSICS_ROUTE_TAB_NOT_RETAINED')
    _require(record.get('zero_product_writes') is True, 'PR8_8_FRESH_FORENSICS_ROUTE_ZERO_WRITE_BOUNDARY_VIOLATED')
    _require(record.get('lease_id_present') is True, 'PR8_8_FRESH_FORENSICS_ROUTE_LEASE_METADATA_MISSING')
    _require(record.get('route_identity_stable') is True, 'PR8_8_FRESH_FORENSICS_ROUTE_NOT_STABLE')
    _require(record.get('dom_ax_inspection_performed') is False, 'PR8_8_FRESH_FORENSICS_ROUTE_UNEXPECTED_DOM_AX')
    _require(record.get('conversation_write_guard_observed') is False, 'PR8_8_FRESH_FORENSICS_ROUTE_WRITE_GUARD_INVALID')
    _require(record.get('conversation_write_count') is None, 'PR8_8_FRESH_FORENSICS_ROUTE_WRITE_COUNT_MUST_BE_UNKNOWN')
    _require(record.get('debugger_attached_before') == record.get('debugger_attached_after'), 'PR8_8_FRESH_FORENSICS_ROUTE_DEBUGGER_STATE_CHANGED')
    route = _dict(record.get('route_identity'))
    for key in ('raw_url_exported', 'query_exported', 'fragment_exported'):
        _require(route.get(key) is not True, 'PR8_8_FRESH_FORENSICS_ROUTE_PRIVACY_BOUNDARY_VIOLATED')

def _validate_surface(record, conversation, tab_id):
    _require(record.get('conversation_id') == conversation, 'PR8_8_FRESH_FORENSICS_SURFACE_CONVERSATION_MISMATCH')
    _require(record.get('runtime_tab_id') == tab_id == record.get('runtime_tab_id_after'), 'PR8_8_FRESH_FORENSICS_SURFACE_TAB_CHANGED')
    _require(record.get('runtime_tab_retained') is True, 'PR8_8_FRESH_FORENSICS_SURFACE_TAB_NOT_RETAINED')
    _require(record.get('zero_product_writes') is True, 'PR8_8_FRESH_FORENSICS_SURFACE_ZERO_WRITE_BOUNDARY_VIOLATED')
    _require(record.get('conversation_write_count') == 0, 'PR8_8_FRESH_FORENSICS_SURFACE_WRITE_OBSERVED')
    _require(record.get('debugger_attached_before') is not True, 'PR8_8_FRESH_FORENSICS_SURFACE_DEBUGGER_ALREADY_ATTACHED')
    _require(record.get('debugger_attached_after') is not True, 'PR8_8_FRESH_FORENSICS_SURFACE_DEBUGGER_LEAK')
    _require(record.get('tab_activated_during_probe') is not True, 'PR8_8_FRESH_FORENSICS_SURFACE_FOREGROUND_ACTIVATION')
