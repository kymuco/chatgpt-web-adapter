from __future__ import annotations

from chatgpt_web_adapter.browser_authority_picker_trigger_timeline_pr8_8 import PickerTriggerTimelineForensicsProvider

CONVERSATION = "6a82dabf-65b8-83eb-b8d5-5a86c6ba635d"
LEASE = "lease-trigger-timeline"

def test_provider_parses_exact_lease_timeline(monkeypatch):
    p = PickerTriggerTimelineForensicsProvider()
    def rpc(payload, *, timeout):
        if payload.get("characterizeInstantFailureForensicsSupport"):
            return {
                "instantFailureForensicsSupported": True, "instantFailureForensicsSchemaVersion": 1,
                "failureRecordPersistenceSupported": True, "preInputFailureBoundarySupported": True,
                "retainedRouteForensicsCompositionSupported": True, "retainedPickerForensicsCompositionSupported": True,
                "rawErrorRedactionSupported": True, "leaseIdExported": False, "zeroProductWrites": True, "automaticRetry": False,
                "pickerTriggerIdentitySupported": True, "clickActuationVerificationSupported": True,
                "perPollMenuMaterializationTimelineSupported": True, "falseOpenSurfaceDealiasingSupported": True,
                "triggerTimelinePersistenceSupported": True, "rawTriggerTextRedactionSupported": True,
            }
        assert payload["expectedBrowserAuthorityLeaseId"] == LEASE
        return {
            "failureCaptured": True, "failureCode": "OPTION_NOT_FOUND", "failureReason": "instant_option_missing",
            "preInputFailureBoundaryProven": True, "promptInsertionReached": False, "submitReached": False,
            "rawErrorExported": False, "leaseIdExported": False, "zeroProductWrites": True, "automaticRetry": False,
            "selection": {"conversationWriteCountDuringSelection": 0}, "triggerTimelineRecordAvailable": True,
            "triggerTimeline": {
                "schemaVersion": 1, "capturedAtFailure": True, "captureStatus": "TRIGGER_TIMELINE_CAPTURED",
                "routeKind": "CONVERSATION", "observedConversationId": CONVERSATION,
                "pickerPointAvailable": True, "clickDispatchCompleted": True,
                "timelineSampleCount": 3, "pollSampleCount": 1,
                "timelineSamples": [{"phase":"PRE_CLICK"},{"phase":"POST_CLICK_IMMEDIATE"},{"phase":"OPTION_POLL"}],
                "bestSeen": {"falseOpenGenericOnlyObserved": True},
                "materializationOutcome": "CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION",
                "rawUrlExported": False, "rawTextExported": False, "rawHtmlExported": False,
                "leaseIdExported": False, "zeroProductWrites": True, "automaticRetry": False,
            },
        }
    monkeypatch.setattr(p, "_characterization_rpc", rpc)
    support = p.instant_failure_forensics_support()
    assert support["picker_trigger_identity_supported"] is True
    record = p.instant_failure_forensics_record(LEASE)
    timeline = record["trigger_timeline"]
    assert timeline["materialization_outcome"] == "CLICK_DISPATCHED_WITHOUT_OBSERVED_ACTUATION"
    assert timeline["lease_id_exported"] is False

