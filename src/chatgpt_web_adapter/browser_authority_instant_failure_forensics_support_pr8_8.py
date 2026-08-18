from __future__ import annotations
from .browser_authority_retained_route_identity_pr8_8 import RetainedRouteIdentityProvider
SCHEMA = 1

def _int(value):
    return value if isinstance(value, int) and (not isinstance(value, bool)) else None

def _str(value):
    return value if isinstance(value, str) and value else None

def _dict(value):
    return value if isinstance(value, dict) else {}

def _list(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []

def _require(condition, message):
    if not condition:
        raise RuntimeError(message)

class InstantFailureForensicsProvider(RetainedRouteIdentityProvider):

    def instant_failure_forensics_support(self):
        r = self._characterization_rpc({'characterizeInstantFailureForensicsSupport': True, 'timeoutMs': 3000}, timeout=max(1.0, self.connect_timeout))
        return {'supported': r.get('instantFailureForensicsSupported') is True, 'schema': _int(r.get('instantFailureForensicsSchemaVersion')), 'failure_record_persistence_supported': r.get('failureRecordPersistenceSupported') is True, 'pre_input_failure_boundary_supported': r.get('preInputFailureBoundarySupported') is True, 'retained_route_forensics_composition_supported': r.get('retainedRouteForensicsCompositionSupported') is True, 'retained_picker_forensics_composition_supported': r.get('retainedPickerForensicsCompositionSupported') is True, 'raw_error_redaction_supported': r.get('rawErrorRedactionSupported') is True, 'lease_id_exported': r.get('leaseIdExported') is True, 'zero_product_writes': r.get('zeroProductWrites') is True, 'automatic_retry': r.get('automaticRetry') is True}

    def instant_failure_forensics_record(self, lease_id, *, timeout=5.0):
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise ValueError('lease_id is required')
        if timeout <= 0:
            raise ValueError('timeout must be positive')
        r = self._characterization_rpc({'characterizeInstantFailureForensicsRecord': True, 'expectedBrowserAuthorityLeaseId': lease_id.strip(), 'timeoutMs': int(timeout * 1000)}, timeout=timeout)
        selection = _dict(r.get('selection'))
        return {'failure_captured': r.get('failureCaptured') is True, 'failure_code': _str(r.get('failureCode')), 'failure_reason': _str(r.get('failureReason')), 'pre_input_failure_boundary_proven': r.get('preInputFailureBoundaryProven') is True, 'prompt_insertion_reached': r.get('promptInsertionReached') is True, 'submit_reached': r.get('submitReached') is True, 'raw_error_exported': r.get('rawErrorExported') is True, 'lease_id_exported': r.get('leaseIdExported') is True, 'zero_product_writes': r.get('zeroProductWrites') is True, 'automatic_retry': r.get('automaticRetry') is True, 'selection': {'requested_model_mode': _str(selection.get('requestedModelMode')), 'selected_mode_before_selection': _str(selection.get('selectedModeBeforeSelection')), 'selected_mode_before_selection_proven': selection.get('selectedModeBeforeSelectionProven') is True, 'selected_mode_before_selection_proof_kind': _str(selection.get('selectedModeBeforeSelectionProofKind')), 'selected_mode_before_selection_candidate_count': _int(selection.get('selectedModeBeforeSelectionCandidateCount')) or 0, 'selection_performed': selection.get('selectionPerformed') is True, 'selection_elapsed_ms': _int(selection.get('selectionElapsedMs')), 'selection_mutation_elapsed_ms': _int(selection.get('selectionMutationElapsedMs')), 'picker_mode_before_click': _str(selection.get('pickerModeBeforeClick')), 'picker_candidate_count': _int(selection.get('pickerCandidateCount')) or 0, 'picker_nearest_distance_px': _int(selection.get('pickerNearestDistancePx')), 'instant_option_candidate_count': _int(selection.get('instantOptionCandidateCount')) or 0, 'selected_mode_after_selection': _str(selection.get('selectedModeAfterSelection')), 'selected_mode_after_selection_proven': selection.get('selectedModeAfterSelectionProven') is True, 'selection_complete': selection.get('selectionComplete') is True, 'conversation_write_boundary_observed': selection.get('conversationWriteBoundaryObserved') is True, 'unexpected_conversation_write_before_selection_complete': selection.get('unexpectedConversationWriteBeforeSelectionComplete') is True, 'conversation_write_count_during_selection': _int(selection.get('conversationWriteCountDuringSelection')) or 0, 'network_request_count_during_selection': _int(selection.get('networkRequestCountDuringSelection')) or 0, 'chatgpt_request_count_during_selection': _int(selection.get('chatgptRequestCountDuringSelection')) or 0, 'chatgpt_mutating_non_conversation_request_count': _int(selection.get('chatgptMutatingNonConversationRequestCount')) or 0, 'setting_like_mutation_observed': selection.get('settingLikeMutationObserved') is True, 'request_classes': _list(selection.get('requestClasses')), 'model_selection_materialization_status': _str(selection.get('modelSelectionMaterializationStatus'))}}

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
